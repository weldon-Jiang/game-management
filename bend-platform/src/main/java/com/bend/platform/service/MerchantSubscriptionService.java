package com.bend.platform.service;

/**
 * 商户订阅服务接口
 * 处理商户订阅相关的业务操作
 */
public interface MerchantSubscriptionService {

    /**
     * 使用激活码激活/续费商户
     *
     * @param merchantId 商户ID
     * @param activationCode 激活码
     * @param userId 操作用户ID (merchant_user.id)
     */
    void activateWithCode(String merchantId, String activationCode, String userId);

    /**
     * 更新商户有效期
     *
     * @param merchantId 商户ID
     * @param days 续费天数
     */
    void extendSubscription(String merchantId, int days);
}