package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.*;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.*;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 计费管理控制器
 *
 * 功能说明：
 * - 商户余额查询
 * - 充值卡充值
 * - 订阅管理（创建、续费、取消、查询）
 * - 设备绑定管理
 *
 * 注意：
 * - 推荐使用激活码方式管理订阅（本控制器中的订阅方法是为兼容旧流程保留）
 * - 新流程：通过 MerchantSubscriptionController 使用激活码激活订阅
 *
 * 分控模式说明：
 * - /balance 接口在分控模式下代理到总控 /api/tenant/balance（VIP/余额数据仅在总控维护）
 */
@Slf4j
@RestController
@RequestMapping("/api/billing")
@RequiredArgsConstructor
public class BillingController {

    private final MerchantBalanceService balanceService;
    private final SubscriptionService subscriptionService;
    private final RechargeCardService rechargeCardService;
    private final MerchantService merchantService;

    /** License 模式：master（总控）/ tenant（分控） */
    @Value("${license.mode:master}")
    private String licenseMode;

    @Value("${license.master-url:}")
    private String masterUrl;

    @Value("${license.key:${LICENSE_KEY:}}")
    private String licenseKey;

    @Value("${license.secret:${LICENSE_SECRET:}}")
    private String licenseSecret;

    /**
     * 获取商户余额信息
     *
     * @return 商户余额（包含累计充值、当前余额、累计消耗、VIP等级）
     *
     * 说明：
     * - 分控模式：代理到总控 /api/tenant/balance（VIP/余额数据仅在总控维护）
     * - 总控模式：直接查本地库
     */
    @GetMapping("/balance")
    public ApiResponse<Map<String, Object>> getBalance() {
        // 分控模式：代理到总控获取余额+VIP
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return callMasterGet("/api/tenant/balance");
        }
        String merchantId = UserContext.getMerchantId();
        MerchantBalance balance = balanceService.getByMerchantId(merchantId);

        Map<String, Object> result = new HashMap<>();
        result.put("id", balance.getId());
        result.put("merchantId", balance.getMerchantId());
        result.put("balance", balance.getBalance());
        result.put("totalRecharged", balance.getTotalRecharged());
        result.put("totalConsumed", balance.getTotalConsumed());
        result.put("version", balance.getVersion());

        Merchant merchant = merchantService.findById(merchantId);
        if (merchant != null) {
            result.put("vipLevel", merchant.getVipLevel() != null ? merchant.getVipLevel() : 0);
            result.put("totalAmount", merchant.getTotalAmount());
        } else {
            result.put("vipLevel", 0);
            result.put("totalAmount", 0);
        }

        return ApiResponse.success(result);
    }

    // ---- 分控代理到总控 ----

    /** GET 代理到总控（返回 List<Subscription>） */
    @SuppressWarnings("unchecked")
    private ApiResponse<List<Subscription>> callMasterGetListActive(String path) {
        try {
            String url = masterUrl.replaceAll("/+$", "") + path;
            ResponseEntity<Map> resp = new RestTemplate().exchange(url, HttpMethod.GET,
                    new HttpEntity<>(licenseHeaders()), Map.class);
            Map<String, Object> body = resp.getBody();
            if (body == null) return ApiResponse.error(500, "总控无响应");
            int code = body.get("code") instanceof Number ? ((Number) body.get("code")).intValue() : 500;
            if (code == 200) {
                Object data = body.get("data");
                if (data instanceof List) {
                    return ApiResponse.success((List<Subscription>) data);
                }
                return ApiResponse.success(List.of());
            }
            return ApiResponse.error(code, String.valueOf(body.getOrDefault("message", "error")));
        } catch (Exception e) {
            log.error("分控代理总控失败 - path: {}, error: {}", path, e.getMessage());
            return ApiResponse.error(500, "总控请求失败: " + e.getMessage());
        }
    }

    /** 构建 License 鉴权请求头 */
    private HttpHeaders licenseHeaders() {
        HttpHeaders h = new HttpHeaders();
        h.set("X-License-Key", licenseKey);
        h.set("X-License-Secret", licenseSecret);
        return h;
    }

    /** GET 代理到总控 */
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
            log.error("分控代理总控失败 - path: {}, error: {}", path, e.getMessage());
            return ApiResponse.error(500, "总控请求失败: " + e.getMessage());
        }
    }

    /**
     * 使用充值卡充值
     *
     * @param cardNo  卡号
     * @param cardPwd 卡密
     * @return 充值结果
     */
    @PostMapping("/recharge")
    public ApiResponse<Void> recharge(@RequestParam String cardNo, @RequestParam String cardPwd) {
        rechargeCardService.useCard(cardNo, cardPwd);
        return ApiResponse.success("充值成功", null);
    }

    /**
     * 直接创建订阅（旧流程，建议使用激活码方式）
     *
     * @param type        订阅类型
     * @param targetId    目标ID
     * @param targetName  目标名称
     * @param pointsCost  点数消耗
     * @param durationDays 时长（天），默认30
     * @return 创建的订阅信息
     *
     * @deprecated 推荐使用 MerchantSubscriptionController 的激活码方式
     */
    @Deprecated
    @PostMapping("/subscriptions")
    public ApiResponse<Subscription> createSubscription(
            @RequestParam String type,
            @RequestParam String targetId,
            @RequestParam String targetName,
            @RequestParam int pointsCost,
            @RequestParam(defaultValue = "30") int durationDays) {
        String merchantId = UserContext.getMerchantId();
        String userId = UserContext.getUserId();

        LocalDateTime startTime = LocalDateTime.now();
        LocalDateTime endTime = startTime.plusDays(durationDays);

        Subscription subscription = subscriptionService.createSubscription(
                merchantId, userId, null, type, type,
                "[\"" + targetId + "\"]", "[\"" + targetName + "\"]",
                startTime, endTime, pointsCost, pointsCost);
        return ApiResponse.success("订阅创建成功", subscription);
    }

    /**
     * 续费订阅
     *
     * @param id           订阅ID
     * @param durationDays 续费时长（天）
     * @param pointsCost   续费点数
     * @return 续费后的订阅信息
     */
    @PostMapping("/subscriptions/{id}/renew")
    public ApiResponse<Subscription> renewSubscription(
            @PathVariable String id,
            @RequestParam int durationDays,
            @RequestParam int pointsCost) {
        Subscription existing = subscriptionService.getById(id);
        if (existing == null) {
            throw new BusinessException(ResultCode.System.NOT_FOUND, "订阅不存在");
        }
        LocalDateTime newEndTime = existing.getEndTime().plusDays(durationDays);
        Subscription subscription = subscriptionService.renewSubscription(id, newEndTime);
        return ApiResponse.success("续费成功", subscription);
    }

    /**
     * 取消订阅
     *
     * @param id 订阅ID
     * @return 操作结果
     */
    @DeleteMapping("/subscriptions/{id}")
    public ApiResponse<Void> cancelSubscription(@PathVariable String id) {
        subscriptionService.cancelSubscription(id);
        return ApiResponse.success("订阅已取消", null);
    }

    /**
     * 分页查询订阅列表
     *
     * @param pageNum  页码
     * @param pageSize 每页数量
     * @param status   状态筛选
     * @return 订阅分页列表
     */
    @GetMapping("/subscriptions")
    public ApiResponse<IPage<Subscription>> listSubscriptions(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize,
            @RequestParam(required = false) String status) {
        // 分控模式：订阅数据在总控，分控本地为陈旧快照，直接返回空（前端用 /api/merchant-subscription/list 代理查询）
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return ApiResponse.success(new Page<>(pageNum, pageSize, 0));
        }
        String merchantId = UserContext.getMerchantId();
        IPage<Subscription> page = subscriptionService.pageSubscriptions(merchantId, pageNum, pageSize, status);
        return ApiResponse.success(page);
    }

    /**
     * 获取生效中的订阅列表
     *
     * @return 生效中的订阅列表
     */
    @GetMapping("/subscriptions/active")
    public ApiResponse<List<Subscription>> listActiveSubscriptions() {
        // 分控模式：代理到总控
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return callMasterGetListActive("/api/tenant/subscriptions/active");
        }
        String merchantId = UserContext.getMerchantId();
        List<Subscription> subscriptions = subscriptionService.getActiveSubscriptions(merchantId);
        return ApiResponse.success(subscriptions);
    }

    /**
     * 设备解绑
     *
     * @param type     设备类型
     * @param deviceId 设备ID
     * @return 解绑结果
     */
    @PostMapping("/device/unbind")
    public ApiResponse<Void> unbindDevice(
            @RequestParam String type,
            @RequestParam String deviceId) {
        String merchantId = UserContext.getMerchantId();
        String userId = UserContext.getUserId();
        int unbindCount = subscriptionService.unbindDevice(merchantId, type, deviceId, userId);
        return ApiResponse.success("解绑成功(本月第" + unbindCount + "次)", null);
    }

    /**
     * 检查设备是否已绑定
     *
     * @param type     设备类型
     * @param deviceId 设备ID
     * @return 是否已绑定
     */
    @GetMapping("/device/check")
    public ApiResponse<Boolean> checkDeviceBound(
            @RequestParam String type,
            @RequestParam String deviceId) {
        String merchantId = UserContext.getMerchantId();
        boolean bound = subscriptionService.isDeviceBound(merchantId, type, deviceId);
        return ApiResponse.success(bound);
    }
}
