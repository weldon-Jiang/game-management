package com.bend.platform.controller;

import com.bend.platform.config.MasterModeCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.MerchantBalance;
import com.bend.platform.entity.MerchantLicense;
import com.bend.platform.entity.Subscription;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.repository.GameAccountMapper;
import com.bend.platform.repository.MerchantLicenseMapper;
import com.bend.platform.repository.XboxHostMapper;
import com.bend.platform.service.ActivationCodeService;
import com.bend.platform.service.AutomationUsageService;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.SubscriptionService;
import com.bend.platform.util.LicenseSignUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.*;

import com.baomidou.mybatisplus.core.metadata.IPage;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 分控代理总控的计费操作（订阅查询 / 余额 / 自动化校验 / 扣点）。
 *
 * <p>所有接口通过 X-License-Key + X-License-Secret 鉴权。
 */
@Slf4j
@RestController
@RequestMapping("/api/tenant")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class TenantBillingController {

    private final SubscriptionService subscriptionService;
    private final MerchantBalanceService balanceService;
    private final AutomationUsageService automationUsageService;
    private final ActivationCodeService activationCodeService;
    private final GameAccountMapper gameAccountMapper;
    private final XboxHostMapper xboxHostMapper;
    private final MerchantLicenseMapper licenseMapper;
    private final LicenseSignUtil signUtil;
    private final com.bend.platform.service.MerchantService merchantService;
    private final com.bend.platform.repository.AutomationUsageMapper automationUsageMapper;
    private final com.bend.platform.repository.AutomationBillingEventMapper billingEventMapper;

    /** 查询订阅 + 余额 */
    @GetMapping("/billing")
    public ApiResponse<Map<String, Object>> getBillingInfo(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        String mid = lic.getMerchantId();
        List<Subscription> subs = subscriptionService.getActiveSubscriptions(mid);
        MerchantBalance bal = balanceService.getByMerchantId(mid);

        Map<String, Object> data = new HashMap<>();
        data.put("merchantId", mid);
        data.put("subscriptions", subs);
        data.put("balance", bal != null ? bal.getBalance() : 0);
        data.put("totalRecharged", bal != null ? bal.getTotalRecharged() : 0);
        return ApiResponse.success(data);
    }

    /**
     * 查询商户余额 + VIP 等级（分控代理 /api/billing/balance 调用）
     *
     * <p>分控前端订阅管理页的概览卡片（点数余额、VIP等级）依赖此接口。
     * 返回结构与 {@link BillingController#getBalance()} 一致，
     * 按 License 绑定的商户 ID 从总控库查询，确保分控看到的是总控最新数据。
     *
     * @param licenseKey    分控 License Key
     * @param licenseSecret 分控 License Secret
     * @return 商户余额信息（含 balance/totalRecharged/totalConsumed/vipLevel/totalAmount）
     */
    @GetMapping("/balance")
    public ApiResponse<Map<String, Object>> getBalance(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        String mid = lic.getMerchantId();
        MerchantBalance balance = balanceService.getByMerchantId(mid);

        Map<String, Object> result = new HashMap<>();
        if (balance != null) {
            result.put("id", balance.getId());
            result.put("merchantId", balance.getMerchantId());
            result.put("balance", balance.getBalance());
            result.put("totalRecharged", balance.getTotalRecharged());
            result.put("totalConsumed", balance.getTotalConsumed());
            result.put("version", balance.getVersion());
        } else {
            result.put("balance", 0);
            result.put("totalRecharged", 0);
            result.put("totalConsumed", 0);
        }

        // 附带 VIP 等级和累计金额（与 BillingController.getBalance 返回结构一致）
        com.bend.platform.entity.Merchant merchant = merchantService.findById(mid);
        if (merchant != null) {
            result.put("vipLevel", merchant.getVipLevel() != null ? merchant.getVipLevel() : 0);
            result.put("totalAmount", merchant.getTotalAmount());
        } else {
            result.put("vipLevel", 0);
            result.put("totalAmount", 0);
        }

        return ApiResponse.success(result);
    }

    /**
     * 分页查询订阅列表（分控代理 /list 调用）
     *
     * <p>返回前端期望的 {records, total, pageNum, pageSize} 分页结构，
     * 按 License 绑定的商户 ID 过滤，与总控侧普通商户查询逻辑一致。
     *
     * @param licenseKey    分控 License Key
     * @param licenseSecret 分控 License Secret
     * @param pageNum       页码
     * @param pageSize      每页数量
     * @param status        状态筛选（可为 null）
     * @return 订阅分页列表
     */
    @GetMapping("/subscriptions/list")
    public ApiResponse<Map<String, Object>> listSubscriptions(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @RequestParam(value = "pageNum", defaultValue = "1") int pageNum,
            @RequestParam(value = "pageSize", defaultValue = "10") int pageSize,
            @RequestParam(value = "status", required = false) String status) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        String mid = lic.getMerchantId();
        IPage<Subscription> pageResult = subscriptionService.pageSubscriptions(mid, pageNum, pageSize, status);

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
            records.add(item);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("records", records);
        result.put("total", pageResult.getTotal());
        result.put("pageNum", pageResult.getCurrent());
        result.put("pageSize", pageResult.getSize());
        return ApiResponse.success(result);
    }

        /** 自动化启动前校验（验订阅/余额 + 计算需扣点数） */
    @PostMapping("/billing/validate")
    public ApiResponse<Map<String, Object>> validate(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @RequestBody Map<String, Object> request) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        String mid = lic.getMerchantId();
        String streamingAccountId = (String) request.get("streamingAccountId");

        @SuppressWarnings("unchecked")
        List<String> gameAccountIds = (List<String>) request.get("gameAccountIds");

        // 分控传入的 gameAccountIds 是分控库的 ID，总控库不存在；且空列表会导致 selectBatchIds 生成 IN () 语法错误。
        // 分控会同时传 accountCount/hostCount，总控直接用数量构造占位对象，不查总控库的 game_account/xbox_host 表。
        int accountCount = request.get("accountCount") instanceof Number
                ? ((Number) request.get("accountCount")).intValue() : 0;
        int hostCount = request.get("hostCount") instanceof Number
                ? ((Number) request.get("hostCount")).intValue() : 0;

        // 用占位 GameAccount/XboxHost 列表（仅用于 validateAndCalculatePoints 统计数量）
        List<GameAccount> gameAccounts = new ArrayList<>();
        for (int i = 0; i < accountCount; i++) {
            gameAccounts.add(new GameAccount());
        }
        List<XboxHost> hosts = new ArrayList<>();
        for (int i = 0; i < hostCount; i++) {
            hosts.add(new XboxHost());
        }

        Map<String, Object> result = automationUsageService.validateAndCalculatePoints(
                mid, streamingAccountId, gameAccounts, hosts);
        return ApiResponse.success(result);
    }

    /** 赛后扣点 */
    @PostMapping("/billing/deduct")
    public ApiResponse<Map<String, Object>> deduct(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @RequestBody Map<String, Object> request) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        int points = request.get("points") instanceof Number ? ((Number) request.get("points")).intValue() : 0;
        String mid = lic.getMerchantId();
        String taskId = request.getOrDefault("taskId", "").toString();

        if (points > 0) {
            // 使用 deductPoints 而非 addPoints(-points)，确保更新 total_consumed + 写幂等键 + 余额校验
            String idempotentKey = request.getOrDefault("idempotentKey", taskId).toString();
            boolean deducted = balanceService.deductPoints(mid, points, mid,
                    "automation_deduct", idempotentKey, "自动化任务扣点");
            if (!deducted) {
                return ApiResponse.error(400, "扣点失败：余额不足或版本冲突");
            }
        }
        log.info("分控扣点 - merchant: {}, points: {}, task: {}", mid, points, taskId);
        return ApiResponse.success(null);
    }

    /**
     * 查询商户订阅状态（分控代理 /status 调用）。
     *
     * <p>返回当前生效订阅 + 余额 + VIP，与 {@link MerchantSubscriptionController#getStatus} 结构一致。
     */
    @GetMapping("/status")
    public ApiResponse<Map<String, Object>> getStatus(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        String mid = lic.getMerchantId();
        com.bend.platform.entity.Merchant merchant = merchantService.findById(mid);
        Map<String, Object> status = new HashMap<>();
        if (merchant != null) {
            status.put("status", "active".equals(merchant.getStatus()) ? "active" : "inactive");
            status.put("merchantName", merchant.getName());
            status.put("vipLevel", merchant.getVipLevel());
        } else {
            status.put("status", "inactive");
            status.put("vipLevel", 0);
        }
        status.put("isAdmin", false);

        MerchantBalance balance = balanceService.getByMerchantId(mid);
        if (balance != null) {
            status.put("totalRecharged", balance.getTotalRecharged());
            status.put("balance", balance.getBalance());
        }

        Subscription current = subscriptionService.getCurrentActiveSubscription(mid);
        if (current != null) {
            status.put("currentSubscription", current.getSubscriptionType());
            status.put("subscriptionEndTime", current.getEndTime());
        } else {
            status.put("currentSubscription", null);
            status.put("subscriptionEndTime", null);
        }
        return ApiResponse.success(status);
    }

    /**
     * 查询生效中订阅列表（分控代理 /active 调用）。
     */
    @GetMapping("/subscriptions/active")
    public ApiResponse<List<Map<String, Object>>> getActiveSubscriptions(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        String mid = lic.getMerchantId();
        List<Subscription> subs = subscriptionService.getActiveSubscriptions(mid);
        List<Map<String, Object>> result = new ArrayList<>();
        for (Subscription sub : subs) {
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
     * 取消订阅（分控代理 /cancel 调用）。
     */
    @PostMapping("/subscriptions/cancel/{subscriptionId}")
    public ApiResponse<Void> cancelSubscription(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @PathVariable String subscriptionId) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        // 校验订阅归属
        Subscription sub = subscriptionService.getById(subscriptionId);
        if (sub == null) return ApiResponse.error(404, "订阅不存在");
        if (!lic.getMerchantId().equals(sub.getMerchantId())) {
            return ApiResponse.error(403, "订阅不属于当前商户");
        }
        subscriptionService.cancelSubscription(subscriptionId);
        log.info("分控代理取消订阅 - subscriptionId: {}, merchant: {}", subscriptionId, lic.getMerchantId());
        return ApiResponse.success("订阅已取消", null);
    }

    /** 激活码预览 */
    @GetMapping("/preview")
    public ApiResponse<Map<String, Object>> preview(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @RequestParam("code") String code) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        ActivationCode ac = activationCodeService.getByCode(code);
        if (ac == null) return ApiResponse.error(404, "激活码不存在");
        if (!lic.getMerchantId().equals(ac.getMerchantId())) return ApiResponse.error(403, "激活码不属于当前商户");
        if (!"unused".equals(ac.getStatus())) return ApiResponse.error(400, "激活码已被使用");

        Map<String, Object> data = new HashMap<>();
        data.put("subscriptionType", ac.getSubscriptionType());
        data.put("durationDays", ac.getDurationDays());
        data.put("pointsAmount", ac.getPointsAmount());
        data.put("originalPrice", ac.getOriginalPrice());
        data.put("discountPrice", ac.getDiscountPrice());
        return ApiResponse.success(data);
    }

    /**
     * 分控代理：记录自动化启动用量 + 扣点（方案A：计费全归总控）。
     *
     * <p>分控 {@link com.bend.platform.service.impl.AutomationUsageServiceImpl#deductPointsAndRecordUsage}
     * 在 tenant 模式下整体代理到此接口。总控负责：扣点 + 写 automation_usage。
     *
     * @param licenseKey    分控 License Key
     * @param licenseSecret 分控 License Secret
     * @param request       包含 taskId/streamingAccountId/streamingAccountName/gameAccountsCount/hostsCount/totalPoints/chargeType/resourceType/resourceId/resourceName/chargeMode/pointsDeducted
     * @return 扣点结果
     */
    @PostMapping("/automation/usage")
    public ApiResponse<Map<String, Object>> recordAutomationUsage(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @RequestBody Map<String, Object> request) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        String mid = lic.getMerchantId();
        int totalPoints = request.get("totalPoints") instanceof Number
                ? ((Number) request.get("totalPoints")).intValue() : 0;
        String taskId = String.valueOf(request.getOrDefault("taskId", ""));

        // 扣点（带幂等键，防重复扣）
        if (totalPoints > 0) {
            boolean deducted = balanceService.deductPoints(mid, totalPoints, mid,
                    "automation", taskId, "启动自动化任务消耗点数");
            if (!deducted) {
                return ApiResponse.error(400, "扣点失败：余额不足或版本冲突");
            }
        }

        // 写 automation_usage 到总控库
        com.bend.platform.entity.AutomationUsage usage = new com.bend.platform.entity.AutomationUsage();
        usage.setMerchantId(mid);
        usage.setUserId(mid);
        usage.setTaskId(taskId);
        usage.setStreamingAccountId(String.valueOf(request.getOrDefault("streamingAccountId", "")));
        usage.setStreamingAccountName(String.valueOf(request.getOrDefault("streamingAccountName", "")));
        usage.setGameAccountsCount(request.get("gameAccountsCount") instanceof Number
                ? ((Number) request.get("gameAccountsCount")).intValue() : 0);
        usage.setHostsCount(request.get("hostsCount") instanceof Number
                ? ((Number) request.get("hostsCount")).intValue() : 0);
        usage.setResourceType(String.valueOf(request.getOrDefault("resourceType", "")));
        usage.setResourceId(String.valueOf(request.getOrDefault("resourceId", "")));
        usage.setResourceName(String.valueOf(request.getOrDefault("resourceName", "")));
        usage.setPointsDeducted(request.get("pointsDeducted") instanceof Number
                ? ((Number) request.get("pointsDeducted")).intValue() : 0);
        usage.setChargeMode(String.valueOf(request.getOrDefault("chargeMode", "")));
        usage.setUsageTime(java.time.LocalDateTime.now());
        automationUsageMapper.insert(usage);

        log.info("分控代理记录用量 - merchant: {}, task: {}, points: {}, chargeMode: {}",
                mid, taskId, totalPoints, usage.getChargeMode());

        Map<String, Object> result = new HashMap<>();
        result.put("recorded", true);
        result.put("pointsDeducted", totalPoints);
        return ApiResponse.success(result);
    }

    /**
     * 分控代理：记录 Step4 可计费事件 + 扣点（方案A：计费全归总控）。
     *
     * <p>分控 {@link com.bend.platform.service.impl.AutomationUsageServiceImpl#recordBillableEvent}
     * 在 tenant 模式下整体代理到此接口。总控负责：写 billing_event + 扣点（幂等）。
     *
     * @param licenseKey    分控 License Key
     * @param licenseSecret 分控 License Secret
     * @param request       包含 taskId/sessionId/streamingAccountId/gameAccountId/gameActionType/billingUnit/unitIndex/idempotentKey/pointsDeducted/coinsDelta/payload
     * @return 记录结果（含 duplicate 标记）
     */
    @PostMapping("/automation/billing-event")
    public ApiResponse<Map<String, Object>> recordBillingEvent(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @RequestBody Map<String, Object> request) {

        MerchantLicense lic = auth(licenseKey, licenseSecret);
        if (lic == null) return ApiResponse.error(403, "License 无效");

        String mid = lic.getMerchantId();
        String idempotentKey = String.valueOf(request.getOrDefault("idempotentKey", ""));

        // 幂等检查：总控库已有此 idempotentKey 则返回 duplicate
        com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<com.bend.platform.entity.AutomationBillingEvent> wrapper =
                new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<>();
        wrapper.eq(com.bend.platform.entity.AutomationBillingEvent::getIdempotentKey, idempotentKey);
        com.bend.platform.entity.AutomationBillingEvent existing = billingEventMapper.selectOne(wrapper);
        if (existing != null) {
            Map<String, Object> duplicate = new HashMap<>();
            duplicate.put("recorded", true);
            duplicate.put("duplicate", true);
            duplicate.put("idempotentKey", idempotentKey);
            duplicate.put("pointsDeducted", 0);
            return ApiResponse.success(duplicate);
        }

        // 写 billing_event
        com.bend.platform.entity.AutomationBillingEvent event = new com.bend.platform.entity.AutomationBillingEvent();
        event.setMerchantId(mid);
        event.setTaskId(String.valueOf(request.getOrDefault("taskId", "")));
        event.setSessionId(String.valueOf(request.getOrDefault("sessionId", "")));
        event.setStreamingAccountId(String.valueOf(request.getOrDefault("streamingAccountId", "")));
        event.setGameAccountId(String.valueOf(request.getOrDefault("gameAccountId", "")));
        event.setGameActionType(String.valueOf(request.getOrDefault("gameActionType", "")));
        event.setBillingUnit(String.valueOf(request.getOrDefault("billingUnit", "")));
        event.setUnitIndex(request.get("unitIndex") instanceof Number
                ? ((Number) request.get("unitIndex")).intValue() : 0);
        event.setIdempotentKey(idempotentKey);
        int points = request.get("pointsDeducted") instanceof Number
                ? ((Number) request.get("pointsDeducted")).intValue() : 0;
        event.setPointsDeducted(points);
        event.setCoinsDelta(request.get("coinsDelta") instanceof Number
                ? ((Number) request.get("coinsDelta")).intValue() : 0);
        event.setStatus("recorded");
        event.setPayload(String.valueOf(request.getOrDefault("payload", "{}")));
        billingEventMapper.insert(event);

        // 扣点
        if (points > 0) {
            boolean deducted = balanceService.deductPoints(mid, points, mid,
                    "automation_billing", idempotentKey,
                    "自动化计费事件: " + event.getGameActionType() + "/" + event.getBillingUnit());
            if (!deducted) {
                throw new com.bend.platform.exception.BusinessException(
                        com.bend.platform.exception.ResultCode.Balance.DEDUCT_FAILED, "余额不足，无法结算本次计费事件");
            }
        }

        log.info("分控代理计费事件 - merchant: {}, task: {}, points: {}, idempotent: {}",
                mid, event.getTaskId(), points, idempotentKey);

        Map<String, Object> result = new HashMap<>();
        result.put("recorded", true);
        result.put("duplicate", false);
        result.put("idempotentKey", idempotentKey);
        result.put("pointsDeducted", points);
        return ApiResponse.success(result);
    }

    private MerchantLicense auth(String key, String secret) {
        if (key == null || secret == null) return null;
        MerchantLicense lic = licenseMapper.selectByLicenseKey(key);
        if (lic == null) return null;
        if (!signUtil.verifySecret(secret, lic.getLicenseSecret())) return null;
        return lic;
    }
}
