package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.ActivationCodeBatch;

import java.util.List;

/**
 * 激活码服务接口
 */
public interface ActivationCodeService {

    /**
     * 生成单个激活码
     */
    ActivationCode generateCode(String merchantId, String subscriptionType, String boundResourceType,
                                String boundResourceIds, String boundResourceNames,
                                int durationDays, int originalPrice, int discountPrice, Integer pointsAmount);

    /**
     * 分页查询激活码
     */
    IPage<ActivationCode> pageByMerchant(String merchantId, int pageNum, int pageSize, String status);

    /**
     * 分页查询所有激活码（平台管理员用）
     */
    IPage<ActivationCode> pageAll(int pageNum, int pageSize, String status);

    /**
     * 分页查询批次
     */
    IPage<ActivationCodeBatch> pageBatchesByMerchant(String merchantId, int pageNum, int pageSize);

    /**
     * 根据激活码查询
     */
    ActivationCode getByCode(String code);

    /**
     * 批量更新状态
     */
    void updateBatchStatus(List<String> ids, String status);

    /**
     * 根据ID删除激活码（仅未使用的可以删除）
     */
    void deleteById(String id);
}
