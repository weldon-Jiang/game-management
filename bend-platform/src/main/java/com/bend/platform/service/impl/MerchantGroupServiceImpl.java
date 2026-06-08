package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.MerchantGroupService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 商户 VIP 分组 CRUD 及与商户 vipLevel 的关联校验。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MerchantGroupServiceImpl implements MerchantGroupService {

    private final MerchantGroupMapper merchantGroupMapper;
    private final MerchantMapper merchantMapper;

    @Override
    public List<MerchantGroup> listAll() {
        return merchantGroupMapper.selectList(null);
    }

    @Override
    public MerchantGroup findById(String id) {
        MerchantGroup group = merchantGroupMapper.selectById(id);
        if (group == null) {
            throw new BusinessException(ResultCode.MerchantGroup.NOT_FOUND);
        }
        return group;
    }

    @Override
    public MerchantGroup findByMerchantId(String merchantId) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        int merchantVipLevel = merchant.getVipLevel() != null ? merchant.getVipLevel() : 0;
        if (merchantVipLevel == 0) {
            return null;
        }

        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getVipLevel, merchantVipLevel)
               .eq(MerchantGroup::getStatus, "active")
               .last("LIMIT 1");
        return merchantGroupMapper.selectOne(wrapper);
    }

    @Override
    public MerchantGroup create(MerchantGroup group) {
        requirePlatformAdmin();
        merchantGroupMapper.insert(group);
        return group;
    }

    @Override
    public void update(String id, MerchantGroup group) {
        requirePlatformAdmin();
        group.setId(id);
        merchantGroupMapper.updateById(group);
    }

    @Override
    public void delete(String id) {
        requirePlatformAdmin();

        MerchantGroup group = findById(id);

        if (group.getVipLevel() == 0) {
            throw new BusinessException(ResultCode.MerchantGroup.CANNOT_DELETE_VIP0);
        }

        LambdaQueryWrapper<MerchantGroup> maxWrapper = new LambdaQueryWrapper<>();
        maxWrapper.orderByDesc(MerchantGroup::getVipLevel).last("LIMIT 1");
        MerchantGroup maxGroup = merchantGroupMapper.selectOne(maxWrapper);
        if (maxGroup == null || !maxGroup.getId().equals(group.getId())) {
            throw new BusinessException(ResultCode.MerchantGroup.NOT_HIGHEST_LEVEL);
        }

        long merchantCount = merchantMapper.selectCount(
                new LambdaQueryWrapper<Merchant>().eq(Merchant::getVipLevel, group.getVipLevel()));
        if (merchantCount > 0) {
            throw new BusinessException(ResultCode.MerchantGroup.HAS_MERCHANT);
        }

        merchantGroupMapper.deleteById(id);
        log.info("删除VIP分组成功 - ID: {}, VIP等级: {}", id, group.getVipLevel());
    }

    private void requirePlatformAdmin() {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
    }
}
