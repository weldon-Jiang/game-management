package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.entity.Subscription;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

/**
 * 订阅服务接口
 */
public interface SubscriptionService {

    /**
     * 创建订阅记录（从激活码激活）
     */
    Subscription createSubscription(String merchantId, String userId, String activationCodeId,
                                   String subscriptionType, String boundResourceType,
                                   String boundResourceIds, String boundResourceNames,
                                   LocalDateTime startTime, LocalDateTime endTime,
                                   Integer originalPrice, Integer discountPrice);

    /**
     * 获取商户当前有效的订阅
     */
    Subscription getCurrentActiveSubscription(String merchantId);

    /**
     * 获取商户当前有效的非点数类订阅（用于包月顺延计算）
     */
    Subscription getLatestActiveNonPointsSubscription(String merchantId);

    /**
     * 获取商户所有有效订阅（当前时间在开始和结束时间之间）
     */
    List<Subscription> getActiveSubscriptions(String merchantId);

    /**
     * 获取订阅详情
     */
    Subscription getById(String subscriptionId);

    /**
     * 续费订阅
     */
    Subscription renewSubscription(String subscriptionId, LocalDateTime newEndTime);

    /**
     * 取消订阅
     */
    void cancelSubscription(String subscriptionId);

    /**
     * 分页查询订阅
     */
    IPage<Subscription> pageSubscriptions(String merchantId, int pageNum, int pageSize, String status);

    /**
     * 校验流媒体账号是否可以用于启动自动化
     */
    List<String> validateStreamingAccountForAutomation(String merchantId, String streamingAccountId);

    /**
     * 校验游戏账号列表是否可以用于启动自动化
     */
    List<String> validateGameAccountsForAutomation(String merchantId, List<String> gameAccountIds);

    /**
     * 校验Xbox主机是否可以用于启动自动化
     */
    List<String> validateXboxHostForAutomation(String merchantId, String xboxHostId);

    /**
     * 综合校验启动自动化请求
     */
    Map<String, Object> validateAutomationRequest(String merchantId, String streamingAccountId,
                                                  List<String> gameAccountIds, String xboxHostId);

    /**
     * 获取可用的游戏账号列表
     */
    List<String> getAvailableGameAccounts(String merchantId, String streamingAccountId);

    /**
     * 获取可用的Xbox主机列表
     */
    List<String> getAvailableXboxHosts(String merchantId, String streamingAccountId);

    /**
     * 解绑设备
     */
    int unbindDevice(String merchantId, String type, String deviceId, String userId);

    /**
     * 检查设备是否已绑定
     */
    boolean isDeviceBound(String merchantId, String type, String deviceId);
}
