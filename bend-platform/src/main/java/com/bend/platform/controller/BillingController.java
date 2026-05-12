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

import java.time.LocalDateTime;
import java.util.List;

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
 */
@RestController
@RequestMapping("/api/billing")
@RequiredArgsConstructor
public class BillingController {

    private final MerchantBalanceService balanceService;
    private final SubscriptionService subscriptionService;
    private final RechargeCardService rechargeCardService;

    /**
     * 获取商户余额信息
     *
     * @return 商户余额（包含累计充值、当前余额、累计消耗）
     */
    @GetMapping("/balance")
    public ApiResponse<MerchantBalance> getBalance() {
        String merchantId = UserContext.getMerchantId();
        MerchantBalance balance = balanceService.getByMerchantId(merchantId);
        return ApiResponse.success(balance);
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
