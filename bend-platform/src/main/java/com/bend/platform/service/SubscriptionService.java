package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.entity.Subscription;

import java.time.LocalDateTime;
import java.util.List;

/**
 * 订阅服务接口
 */
public interface SubscriptionService {

    /**
     * 创建订阅
     */
    Subscription createSubscription(String merchantId, String userId, String type, String targetId,
                                    String targetName, int pointsCost, int durationDays);

    /**
     * 续费订阅
     */
    Subscription renewSubscription(String subscriptionId, int durationDays, int pointsCost);

    /**
     * 取消订阅
     */
    void cancelSubscription(String subscriptionId);

    /**
     * 解绑设备
     */
    int unbindDevice(String merchantId, String type, String deviceId, String userId);

    /**
     * 获取订阅详情
     */
    Subscription getById(String subscriptionId);

    /**
     * 获取商户的有效订阅
     */
    List<Subscription> getActiveSubscriptions(String merchantId);

    /**
     * 检查设备是否已绑定
     */
    boolean isDeviceBound(String merchantId, String type, String deviceId);

    /**
     * 获取设备的有效订阅
     */
    Subscription getActiveSubscriptionByDevice(String merchantId, String type, String deviceId);

    /**
     * 分页查询订阅
     */
    IPage<Subscription> pageSubscriptions(String merchantId, int pageNum, int pageSize, String status);
}
