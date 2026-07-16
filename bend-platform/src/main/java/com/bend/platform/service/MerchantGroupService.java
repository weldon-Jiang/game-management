package com.bend.platform.service;

import com.bend.platform.entity.MerchantGroup;

import java.util.List;

/**
 * VIP merchant group (pricing tier) management.
 */
public interface MerchantGroupService {

    List<MerchantGroup> listAll();

    MerchantGroup findById(String id);

    MerchantGroup findByMerchantId(String merchantId);

    /**
     * 根据 VIP 等级查询定价组。
     */
    MerchantGroup getByVipLevel(int vipLevel);

    MerchantGroup create(MerchantGroup group);

    void update(String id, MerchantGroup group);

    void delete(String id);
}
