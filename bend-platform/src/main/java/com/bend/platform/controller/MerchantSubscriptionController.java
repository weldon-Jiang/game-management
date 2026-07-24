package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantBalance;
import com.bend.platform.entity.Subscription;
import com.bend.platform.service.ActivationCodeService;
import com.bend.platform.service.AutomationUsageService;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.SubscriptionService;
import com.bend.platform.service.impl.VipLevelService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.client.RestTemplate;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;

/**
 * 商户订阅管理控制器
 *
 * 功能说明：
 * - 获取订阅状态
 * - 预览激活码激活效果
 * - 激活订阅（根据激活码）
 * - 查询订阅列表
 * - 取消订阅
 * - 获取订阅类型列表
 *
 * 订阅类型：
 * - window_account: 流媒体账号包月
 * - account: 游戏账号包月
 * - host: Xbox主机包月
 * - full: 全功能包月
 * - points: 点数充值
 *
 * 激活规则：
 * - 点数类型：立即增加余额，无有效期
 * - 包月类型：从当前最晚到期的订阅结束日期+1天开始顺延30天
 * - 同一时间只能有一个生效中的包月订阅
 */
@Slf4j
@RestController
@RequestMapping("/api/merchant-subscription")
@RequiredArgsConstructor
public class MerchantSubscriptionController {

    private final ActivationCodeService activationCodeService;
    private final MerchantService merchantService;
    private final MerchantBalanceService balanceService;
    private final SubscriptionService subscriptionService;
    private final VipLevelService vipLevelService;
    private final AutomationUsageService automationUsageService;

    /**
     * 获取商户订阅状态
     *
     * @return 商户状态信息
     *
     * 说明：
     * - 平台管理员返回简化状态
     * - 普通商户返回详细信息，包括VIP等级、当前订阅等
     */
    @GetMapping("/status")
    public ApiResponse<Map<String, Object>> getStatus() {
        // 分控模式：代理到总控获取订阅状态（VIP/余额/订阅数据仅在总控维护）
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return callMasterGet("/api/tenant/status");
        }
        String merchantId = UserContext.getMerchantId();

        if (UserContext.isPlatformAdmin()) {
            Map<String, Object> adminStatus = new HashMap<>();
            adminStatus.put("status", "active");
            adminStatus.put("isAdmin", true);
            return ApiResponse.success(adminStatus);
        }

        Merchant merchant = merchantService.findById(merchantId);
        if (merchant == null) {
            return ApiResponse.error(404, "商户不存在");
        }

        Map<String, Object> status = new HashMap<>();
        status.put("status", "active".equals(merchant.getStatus()) ? "active" : "inactive");
        status.put("merchantName", merchant.getName());
        status.put("vipLevel", merchant.getVipLevel());
        status.put("isAdmin", false);

        // 获取商户余额信息
        MerchantBalance balance = balanceService.getByMerchantId(merchantId);
        if (balance != null) {
            status.put("totalRecharged", balance.getTotalRecharged());
            status.put("balance", balance.getBalance());
        }

        // 获取当前生效中的包月订阅
        Subscription currentSubscription = subscriptionService.getCurrentActiveSubscription(merchantId);
        if (currentSubscription != null) {
            status.put("currentSubscription", currentSubscription.getSubscriptionType());
            status.put("subscriptionEndTime", currentSubscription.getEndTime());
        } else {
            status.put("currentSubscription", null);
            status.put("subscriptionEndTime", null);
        }

        return ApiResponse.success(status);
    }

    /**
     * 预览激活码激活效果
     *
     * @param code 激活码
     * @return 激活后的效果预览
     *
     * 说明：
     * - 点数类型：显示"立即生效/永久有效"
     * - 包月类型：计算并显示生效时间和到期时间
     * - 如果与现有订阅时间冲突会显示警告信息
     */
    @GetMapping("/preview")
    public ApiResponse<Map<String, Object>> previewActivation(@RequestParam("code") String code) {
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return callMasterGet("/api/tenant/preview?code=" + code);
        }
        String merchantId = UserContext.getMerchantId();

        ActivationCode activationCode = activationCodeService.getByCode(code);

        if (activationCode == null) {
            return ApiResponse.error(404, "激活码不存在");
        }

        if (!merchantId.equals(activationCode.getMerchantId())) {
            return ApiResponse.error(403, "激活码不属于当前商户");
        }

        if (!"unused".equals(activationCode.getStatus())) {
            return ApiResponse.error(400, "激活码已被使用");
        }

        Map<String, Object> preview = new HashMap<>();
        preview.put("subscriptionType", activationCode.getSubscriptionType());
        preview.put("boundResourceType", activationCode.getBoundResourceType());
        preview.put("boundResourceIds", activationCode.getBoundResourceIds());
        preview.put("boundResourceNames", activationCode.getBoundResourceNames());
        preview.put("originalPrice", activationCode.getOriginalPrice());
        preview.put("discountPrice", activationCode.getDiscountPrice());
        preview.put("durationDays", activationCode.getDurationDays());

        if ("points".equals(activationCode.getSubscriptionType())) {
            preview.put("calculatedStartTime", "立即生效");
            preview.put("calculatedEndTime", "永久有效");
            preview.put("conflictMessage", null);
        } else {
            Subscription latestSubscription = subscriptionService.getLatestActiveNonPointsSubscription(merchantId);
            LocalDate calculatedStartTime;
            LocalDate calculatedEndTime;

            // 如果没有生效中的订阅，或者现有订阅已到期，从今天开始
            if (latestSubscription == null || latestSubscription.getEndTime().toLocalDate().isBefore(LocalDate.now())) {
                calculatedStartTime = LocalDate.now();
            } else {
                // 从现有订阅到期日的下一天开始
                calculatedStartTime = latestSubscription.getEndTime().toLocalDate().plusDays(1);
            }
            calculatedEndTime = calculatedStartTime.plusDays(activationCode.getDurationDays() - 1);

            preview.put("calculatedStartTime", calculatedStartTime.format(DateTimeFormatter.ISO_DATE));
            preview.put("calculatedEndTime", calculatedEndTime.format(DateTimeFormatter.ISO_DATE));

            if (latestSubscription != null && latestSubscription.getEndTime().toLocalDate().isAfter(calculatedStartTime)) {
                preview.put("conflictMessage", "与当前订阅时间冲突，当前订阅到期时间为 " + latestSubscription.getEndTime().format(DateTimeFormatter.ISO_DATE));
            } else {
                preview.put("conflictMessage", null);
            }
        }

        return ApiResponse.success(preview);
    }

    /**
     * 激活订阅
     *
     * @param code 激活码
     * @return 激活结果
     *
     * 说明：
     * - 点数类型：直接增加商户余额，记录交易流水
     * - 包月类型：创建订阅记录，根据现有订阅时间顺延
     * - 包月类型同一时间只能有一个生效，新激活会顺延
     * - 激活时不更新VIP等级（VIP在生成激活码时已更新）
     */
    @Value("${license.mode:master}")
    private String licenseMode;

    @Value("${license.master-url:}")
    private String masterUrl;

    @Value("${license.key:${LICENSE_KEY:}}")
    private String licenseKey;

    @Value("${license.secret:${LICENSE_SECRET:}}")
    private String licenseSecret;

    @PostMapping("/activate")
    public ApiResponse<Map<String, Object>> activate(@RequestParam("code") String code) {
        // 分控模式：代理到总控执行激活
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return proxyActivateToMaster(code);
        }

        String merchantId = UserContext.getMerchantId();
        String userId = UserContext.getUserId();

        log.info("开始激活激活码 - code: {}, merchantId: {}, userId: {}", code, merchantId, userId);

        ActivationCode activationCode = activationCodeService.getByCode(code);

        if (activationCode == null) {
            log.warn("激活码不存在 - code: {}", code);
            return ApiResponse.error(404, "激活码不存在");
        }

        if (!merchantId.equals(activationCode.getMerchantId())) {
            log.warn("激活码不属于当前商户 - code: {}, merchantId: {}, activationCodeMerchantId: {}",
                    code, merchantId, activationCode.getMerchantId());
            return ApiResponse.error(403, "激活码不属于当前商户");
        }

        if (!"unused".equals(activationCode.getStatus())) {
            log.warn("激活码已被使用 - code: {}, status: {}", code, activationCode.getStatus());
            return ApiResponse.error(400, "激活码已被使用");
        }

        log.info("激活码信息 - code: {}, type: {}, pointsAmount: {}, durationDays: {}",
                code, activationCode.getSubscriptionType(), activationCode.getPointsAmount(), activationCode.getDurationDays());

        Map<String, Object> result = new HashMap<>();
        result.put("subscriptionType", activationCode.getSubscriptionType());

        // 点数类型：直接增加余额
        if ("points".equals(activationCode.getSubscriptionType())) {
            log.info("点数类型激活码 - code: {}, points: {}", code, activationCode.getPointsAmount());
            balanceService.addPoints(merchantId,
                    activationCode.getPointsAmount() != null ? activationCode.getPointsAmount() : 0,
                    userId, "activation_code", activationCode.getId(), "激活码充值点数");
            result.put("pointsAdded", activationCode.getPointsAmount());
            result.put("startTime", "立即生效");
            result.put("endTime", "永久有效");
        } else {
            // 包月类型：计算顺延时间
            log.info("包月类型激活码 - code: {}, 开始计算顺延时间", code);
            Subscription latestSubscription = subscriptionService.getLatestActiveNonPointsSubscription(merchantId);
            LocalDate calculatedStartTime;
            LocalDate calculatedEndTime;

            if (latestSubscription == null) {
                calculatedStartTime = LocalDate.now();
                log.info("无现有订阅，从今天开始 - code: {}, startTime: {}", code, calculatedStartTime);
            } else {
                calculatedStartTime = latestSubscription.getEndTime().toLocalDate().plusDays(1);
                log.info("有现有订阅，从订阅到期日+1天开始 - code: {}, latestEndTime: {}, calculatedStartTime: {}",
                        code, latestSubscription.getEndTime(), calculatedStartTime);
            }
            calculatedEndTime = calculatedStartTime.plusDays(activationCode.getDurationDays() - 1);

            if (latestSubscription != null && latestSubscription.getEndTime().toLocalDate().isAfter(calculatedStartTime)) {
                log.warn("与当前订阅时间冲突 - code: {}, latestEndTime: {}, calculatedStartTime: {}",
                        code, latestSubscription.getEndTime(), calculatedStartTime);
                return ApiResponse.error(400, "与当前订阅时间冲突，无法激活");
            }

            LocalDateTime startDateTime = calculatedStartTime.atStartOfDay();
            LocalDateTime endDateTime = calculatedEndTime.atTime(23, 59, 59);

            log.info("创建订阅记录 - merchantId: {}, type: {}, startTime: {}, endTime: {}",
                    merchantId, activationCode.getSubscriptionType(), startDateTime, endDateTime);

            // 创建订阅记录
            subscriptionService.createSubscription(
                merchantId,
                userId,
                activationCode.getId(),
                activationCode.getSubscriptionType(),
                activationCode.getBoundResourceType(),
                activationCode.getBoundResourceIds(),
                activationCode.getBoundResourceNames(),
                startDateTime,
                endDateTime,
                activationCode.getOriginalPrice(),
                activationCode.getDiscountPrice()
            );
            activationCode.setStartTime(startDateTime);
            activationCode.setEndTime(endDateTime);
            result.put("startTime", startDateTime);
            result.put("endTime", endDateTime);
        }
        // 更新激活码状态
        activationCode.setStatus("used");
        activationCode.setUsedBy(userId);
        activationCode.setUsedTime(LocalDateTime.now());
        activationCodeService.updateActivationCode(activationCode);
        log.info("更新激活码状态 - code: {}, updated", code);
        // 返回商户当前信息
        Merchant merchant = merchantService.findById(merchantId);
        result.put("totalAmount", merchant.getTotalAmount());
        result.put("vipLevel", merchant.getVipLevel());

        log.info("激活成功 - code: {}, result: {}", code, result);
        return ApiResponse.success("激活成功", result);
    }

    /**
     * 获取当前生效的订阅列表
     *
     * @return 生效中的订阅列表（包括待生效的）
     */
    @GetMapping("/active")
    public ApiResponse<List<Map<String, Object>>> getActiveSubscriptions() {
        // 分控模式：代理到总控
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return callMasterGetList("/api/tenant/subscriptions/active");
        }
        String merchantId = UserContext.getMerchantId();
        List<Subscription> subscriptions = subscriptionService.getActiveSubscriptions(merchantId);

        List<Map<String, Object>> result = new ArrayList<>();
        for (Subscription sub : subscriptions) {
            Map<String, Object> item = new HashMap<>();
            item.put("id", sub.getId());
            item.put("subscriptionType", sub.getSubscriptionType());
            item.put("boundResourceType", sub.getBoundResourceType());
            item.put("boundResourceIds", sub.getBoundResourceIds());
            item.put("boundResourceNames", sub.getBoundResourceNames());
            item.put("startTime", sub.getStartTime());
            item.put("endTime", sub.getEndTime());
            item.put("status", sub.getStatus());
            result.add(item);
        }

        return ApiResponse.success(result);
    }

    /**
     * 分页查询订阅历史
     *
     * @param pageNum  页码
     * @param pageSize 每页数量
     * @param status   状态筛选
     * @return 订阅分页列表
     *
     * 说明：
     * - 分控模式：代理到总控的 /api/tenant/subscriptions/list（返回 {records,total} 分页结构）
     * - 平台管理员：查询所有商户的订阅，附带 merchantName 字段便于区分归属
     * - 普通商户：仅查询当前商户的订阅
     */
    @GetMapping("/list")
    public ApiResponse<Map<String, Object>> listSubscriptions(
            @RequestParam(value = "pageNum", defaultValue = "1") int pageNum,
            @RequestParam(value = "pageSize", defaultValue = "10") int pageSize,
            @RequestParam(value = "status", required = false) String status) {
        // 分控模式：代理到总控分页接口（非 /billing 概览接口）
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            String path = "/api/tenant/subscriptions/list?pageNum=" + pageNum + "&pageSize=" + pageSize;
            if (status != null && !status.isEmpty()) {
                path += "&status=" + status;
            }
            return callMasterGet(path);
        }

        // 平台管理员：查看所有商户订阅；普通商户：仅查自己
        boolean isAdmin = UserContext.isPlatformAdmin();
        com.baomidou.mybatisplus.core.metadata.IPage<Subscription> pageResult;
        Map<String, String> merchantNameMap = Collections.emptyMap();

        if (isAdmin) {
            pageResult = subscriptionService.pageAllSubscriptions(pageNum, pageSize, status);
            // 批量查询商户名，用于前端展示归属
            if (!pageResult.getRecords().isEmpty()) {
                java.util.Set<String> merchantIds = new java.util.HashSet<>();
                for (Subscription sub : pageResult.getRecords()) {
                    merchantIds.add(sub.getMerchantId());
                }
                List<Merchant> merchants = merchantService.findByIds(merchantIds);
                merchantNameMap = new HashMap<>();
                for (Merchant m : merchants) {
                    merchantNameMap.put(m.getId(), m.getName());
                }
            }
        } else {
            String merchantId = UserContext.getMerchantId();
            pageResult = subscriptionService.pageSubscriptions(merchantId, pageNum, pageSize, status);
        }

        List<Map<String, Object>> records = new ArrayList<>();
        for (Subscription sub : pageResult.getRecords()) {
            Map<String, Object> item = new HashMap<>();
            item.put("id", sub.getId());
            item.put("subscriptionType", sub.getSubscriptionType());
            item.put("boundResourceType", sub.getBoundResourceType());
            item.put("boundResourceNames", sub.getBoundResourceNames());
            item.put("startTime", sub.getStartTime());
            item.put("endTime", sub.getEndTime());
            item.put("originalPrice", sub.getOriginalPrice());
            item.put("discountPrice", sub.getDiscountPrice());
            item.put("status", sub.getStatus());
            // 平台管理员视角附带商户信息
            if (isAdmin) {
                item.put("merchantId", sub.getMerchantId());
                item.put("merchantName", merchantNameMap.getOrDefault(sub.getMerchantId(), "未知商户"));
            }
            records.add(item);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("records", records);
        result.put("total", pageResult.getTotal());
        result.put("pageNum", pageResult.getCurrent());
        result.put("pageSize", pageResult.getSize());

        return ApiResponse.success(result);
    }

    /**
     * 取消订阅
     *
     * @param subscriptionId 订阅ID
     * @return 操作结果
     */
    @PostMapping("/cancel/{subscriptionId}")
    public ApiResponse<Void> cancelSubscription(@PathVariable String subscriptionId) {
        // 分控模式：代理到总控（订阅数据在总控，分控本地无记录）
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return callMasterPostVoid("/api/tenant/subscriptions/cancel/" + subscriptionId);
        }
        subscriptionService.cancelSubscription(subscriptionId);
        return ApiResponse.success("订阅已取消", null);
    }

    /**
     * 获取订阅类型列表
     *
     * @return 支持的订阅类型
     */
    @GetMapping("/subscription-types")
    public ApiResponse<List<Map<String, String>>> getSubscriptionTypes() {
        List<Map<String, String>> types = new ArrayList<>();
        types.add(Map.of("value", "window_account", "label", "流媒体账号包月"));
        types.add(Map.of("value", "account", "label", "游戏账号包月"));
        types.add(Map.of("value", "host", "label", "Xbox主机包月"));
        types.add(Map.of("value", "full", "label", "全功能包月"));
        types.add(Map.of("value", "points", "label", "点数充值"));
        return ApiResponse.success(types);
    }

    /**
     * 验证自动化启动条件
     *
     * @param request 包含流媒体账号ID和游戏账号ID列表
     * @return 验证结果
     */
    @PostMapping("/validate-automation")
    public ApiResponse<Map<String, Object>> validateAutomation(@RequestBody Map<String, Object> request) {
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return callMasterPost("/api/tenant/billing/validate", request);
        }
        String merchantId = UserContext.getMerchantId();
        String streamingAccountId = (String) request.get("streamingAccountId");
        @SuppressWarnings("unchecked")
        List<String> gameAccountIds = (List<String>) request.get("gameAccountIds");

        log.info("验证自动化启动条件 - merchantId: {}, streamingAccountId: {}, gameAccountIds: {}",
                merchantId, streamingAccountId, gameAccountIds);

        Map<String, Object> result = new HashMap<>();
        List<String> errors = new ArrayList<>();

        if (streamingAccountId == null || streamingAccountId.isEmpty()) {
            errors.add("流媒体账号ID不能为空");
        }

        if (gameAccountIds == null || gameAccountIds.isEmpty()) {
            errors.add("游戏账号列表不能为空");
        }

        if (!errors.isEmpty()) {
            result.put("canStart", false);
            result.put("errors", errors);
            return ApiResponse.success(result);
        }

        try {
            List<Subscription> activeSubscriptions = subscriptionService.getActiveSubscriptions(merchantId);
            
            boolean hasValidSubscription = false;
            String subscriptionType = null;

            for (Subscription sub : activeSubscriptions) {
                if ("active".equals(sub.getStatus())) {
                    hasValidSubscription = true;
                    subscriptionType = sub.getSubscriptionType();
                    break;
                }
            }

            if (hasValidSubscription) {
                result.put("canStart", true);
                result.put("errors", new ArrayList<>());
                result.put("subscriptionType", subscriptionType);
                result.put("chargeType", "subscription");
                log.info("自动化验证通过 - merchantId: {}, subscriptionType: {}", merchantId, subscriptionType);
            } else {
                MerchantBalance merchantBalance = balanceService.getByMerchantId(merchantId);
                Integer balance = merchantBalance != null ? merchantBalance.getBalance() : 0;
                if (balance != null && balance > 0) {
                    result.put("canStart", true);
                    result.put("errors", new ArrayList<>());
                    result.put("subscriptionType", null);
                    result.put("chargeType", "per_use");
                    result.put("balance", balance);
                    log.info("自动化验证通过 - 使用点数余额 - merchantId: {}, balance: {}", merchantId, balance);
                } else {
                    errors.add("当前没有生效中的订阅且余额不足，请先激活订阅或充值点数");
                    result.put("canStart", false);
                    result.put("errors", errors);
                    log.warn("自动化验证失败 - 没有生效中的订阅且余额不足 - merchantId: {}", merchantId);
                }
            }

            return ApiResponse.success(result);
        } catch (Exception e) {
            log.error("验证自动化条件失败 - merchantId: {}, error: {}", merchantId, e.getMessage(), e);
            errors.add("验证失败：" + e.getMessage());
            result.put("canStart", false);
            result.put("errors", errors);
            return ApiResponse.success(result);
        }
    }

    // ---- 分控代理到总控 ----

    private HttpHeaders licenseHeaders() {
        HttpHeaders h = new HttpHeaders();
        h.set("X-License-Key", licenseKey);
        h.set("X-License-Secret", licenseSecret);
        return h;
    }

    @SuppressWarnings("unchecked")
    private ApiResponse<Map<String, Object>> callMasterGet(String path) {
        try {
            String url = masterUrl.replaceAll("/+$", "") + path;
            ResponseEntity<Map> resp = new RestTemplate().exchange(url, HttpMethod.GET,
                    new HttpEntity<>(licenseHeaders()), Map.class);
            Map<String, Object> body = resp.getBody();
            if (body == null) return ApiResponse.error(500, "总控无响应");
            int code = body.get("code") instanceof Number ? ((Number) body.get("code")).intValue() : 500;
            if (code == 200) return ApiResponse.success((Map<String, Object>) body.get("data"));
            return ApiResponse.error(code, String.valueOf(body.getOrDefault("message", "error")));
        } catch (Exception e) {
            return ApiResponse.error(500, "总控请求失败: " + e.getMessage());
        }
    }

    @SuppressWarnings("unchecked")
    private ApiResponse<Map<String, Object>> callMasterPost(String path, Map<String, Object> reqBody) {
        try {
            HttpHeaders h = licenseHeaders();
            h.setContentType(MediaType.APPLICATION_JSON);
            String url = masterUrl.replaceAll("/+$", "") + path;
            ResponseEntity<Map> resp = new RestTemplate().postForEntity(url, new HttpEntity<>(reqBody, h), Map.class);
            Map<String, Object> body = resp.getBody();
            if (body == null) return ApiResponse.error(500, "总控无响应");
            int code = body.get("code") instanceof Number ? ((Number) body.get("code")).intValue() : 500;
            if (code == 200) return ApiResponse.success((Map<String, Object>) body.get("data"));
            return ApiResponse.error(code, String.valueOf(body.getOrDefault("message", "error")));
        } catch (Exception e) {
            return ApiResponse.error(500, "总控请求失败: " + e.getMessage());
        }
    }

    private ApiResponse<Map<String, Object>> proxyActivateToMaster(String code) {
        Map<String, Object> body = new HashMap<>();
        body.put("code", code);
        return callMasterPost("/api/tenant/activate", body);
    }

    /** GET 代理到总控（返回 List 结构） */
    @SuppressWarnings("unchecked")
    private <T> ApiResponse<T> callMasterGetList(String path) {
        try {
            String url = masterUrl.replaceAll("/+$", "") + path;
            ResponseEntity<Map> resp = new RestTemplate().exchange(url, HttpMethod.GET,
                    new HttpEntity<>(licenseHeaders()), Map.class);
            Map<String, Object> body = resp.getBody();
            if (body == null) return ApiResponse.error(500, "总控无响应");
            int code = body.get("code") instanceof Number ? ((Number) body.get("code")).intValue() : 500;
            if (code == 200) return ApiResponse.success((T) body.get("data"));
            return ApiResponse.error(code, String.valueOf(body.getOrDefault("message", "error")));
        } catch (Exception e) {
            return ApiResponse.error(500, "总控请求失败: " + e.getMessage());
        }
    }

    /** POST 代理到总控（无返回体） */
    private ApiResponse<Void> callMasterPostVoid(String path) {
        try {
            HttpHeaders h = licenseHeaders();
            h.setContentType(MediaType.APPLICATION_JSON);
            String url = masterUrl.replaceAll("/+$", "") + path;
            ResponseEntity<Map> resp = new RestTemplate().postForEntity(url, new HttpEntity<>(null, h), Map.class);
            Map<String, Object> body = resp.getBody();
            if (body == null) return ApiResponse.error(500, "总控无响应");
            int code = body.get("code") instanceof Number ? ((Number) body.get("code")).intValue() : 500;
            if (code == 200) return ApiResponse.success(String.valueOf(body.getOrDefault("message", "成功")), null);
            return ApiResponse.error(code, String.valueOf(body.getOrDefault("message", "error")));
        } catch (Exception e) {
            return ApiResponse.error(500, "总控请求失败: " + e.getMessage());
        }
    }
}
