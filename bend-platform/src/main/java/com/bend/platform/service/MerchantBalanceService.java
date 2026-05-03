package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.entity.MerchantBalance;

/**
 * 商户点数账户服务接口
 */
public interface MerchantBalanceService {

    /**
     * 获取商户账户余额
     */
    MerchantBalance getByMerchantId(String merchantId);

    /**
     * 初始化商户账户
     */
    void initBalance(String merchantId);

    /**
     * 增加点数
     */
    void addPoints(String merchantId, int points, String userId, String type, String refId, String description);

    /**
     * 扣除点数(带乐观锁)
     */
    boolean deductPoints(String merchantId, int points, String userId, String type, String refId, String description);

    /**
     * 返还点数
     */
    boolean refundPoints(String merchantId, int points, String userId, String subscriptionId, String description);

    /**
     * 检查余额是否充足
     */
    boolean hasEnoughBalance(String merchantId, int points);
}
