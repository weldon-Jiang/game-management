package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.*;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.*;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;

/**
 * 收费系统控制器
 */
@RestController
@RequestMapping("/api/billing")
@RequiredArgsConstructor
public class BillingController {

    private final MerchantBalanceService balanceService;
    private final SubscriptionService subscriptionService;
    private final RechargeCardService rechargeCardService;

    @GetMapping("/balance")
    public ApiResponse<MerchantBalance> getBalance() {
        String merchantId = UserContext.getMerchantId();
        MerchantBalance balance = balanceService.getByMerchantId(merchantId);
        return ApiResponse.success(balance);
    }

    @PostMapping("/recharge")
    public ApiResponse<Void> recharge(@RequestParam String cardNo, @RequestParam String cardPwd) {
        rechargeCardService.useCard(cardNo, cardPwd);
        return ApiResponse.success("充值成功", null);
    }

    @PostMapping("/subscriptions")
    public ApiResponse<Subscription> createSubscription(
            @RequestParam String type,
            @RequestParam String targetId,
            @RequestParam String targetName,
            @RequestParam int pointsCost,
            @RequestParam(defaultValue = "30") int durationDays) {
        String merchantId = UserContext.getMerchantId();
        String userId = UserContext.getUserId();
        Subscription subscription = subscriptionService.createSubscription(
                merchantId, userId, type, targetId, targetName, pointsCost, durationDays);
        return ApiResponse.success("订阅创建成功", subscription);
    }

    @PostMapping("/subscriptions/{id}/renew")
    public ApiResponse<Subscription> renewSubscription(
            @PathVariable String id,
            @RequestParam int durationDays,
            @RequestParam int pointsCost) {
        Subscription subscription = subscriptionService.renewSubscription(id, durationDays, pointsCost);
        return ApiResponse.success("续费成功", subscription);
    }

    @DeleteMapping("/subscriptions/{id}")
    public ApiResponse<Void> cancelSubscription(@PathVariable String id) {
        subscriptionService.cancelSubscription(id);
        return ApiResponse.success("订阅已取消", null);
    }

    @GetMapping("/subscriptions")
    public ApiResponse<IPage<Subscription>> listSubscriptions(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize,
            @RequestParam(required = false) String status) {
        String merchantId = UserContext.getMerchantId();
        IPage<Subscription> page = subscriptionService.pageSubscriptions(merchantId, pageNum, pageSize, status);
        return ApiResponse.success(page);
    }

    @GetMapping("/subscriptions/active")
    public ApiResponse<List<Subscription>> listActiveSubscriptions() {
        String merchantId = UserContext.getMerchantId();
        List<Subscription> subscriptions = subscriptionService.getActiveSubscriptions(merchantId);
        return ApiResponse.success(subscriptions);
    }

    @PostMapping("/device/unbind")
    public ApiResponse<Void> unbindDevice(
            @RequestParam String type,
            @RequestParam String deviceId) {
        String merchantId = UserContext.getMerchantId();
        String userId = UserContext.getUserId();
        int unbindCount = subscriptionService.unbindDevice(merchantId, type, deviceId, userId);
        return ApiResponse.success("解绑成功(本月第" + unbindCount + "次)", null);
    }

    @GetMapping("/device/check")
    public ApiResponse<Boolean> checkDeviceBound(
            @RequestParam String type,
            @RequestParam String deviceId) {
        String merchantId = UserContext.getMerchantId();
        boolean bound = subscriptionService.isDeviceBound(merchantId, type, deviceId);
        return ApiResponse.success(bound);
    }
}
