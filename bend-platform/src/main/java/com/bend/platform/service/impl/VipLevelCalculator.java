package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.repository.MerchantGroupMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * VIP等级计算器
 * 纯计算逻辑，不依赖任何可能产生循环依赖的Service
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class VipLevelCalculator {

    private final MerchantGroupMapper merchantGroupMapper;

    /**
     * 根据累计消费金额计算VIP等级
     * 查找 amountThreshold <= totalAmount 的最高VIP等级
     *
     * @param totalAmount 累计消费金额
     * @return VIP等级（0表示无等级）
     */
    public int calculateVipLevel(int totalAmount) {
        log.info("计算VIP等级，累计消费金额: {}", totalAmount);

        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getStatus, "active")
                .le(MerchantGroup::getAmountThreshold, totalAmount)
                .orderByDesc(MerchantGroup::getVipLevel)
                .last("LIMIT 1");

        MerchantGroup group = merchantGroupMapper.selectOne(wrapper);

        if (group == null) {
            log.info("未找到匹配的VIP分组，返回0");
            return 0;
        }

        log.info("找到VIP分组: {}, VIP等级: {}, 阈值: {}", group.getName(), group.getVipLevel(), group.getAmountThreshold());
        return group.getVipLevel();
    }

    /**
     * 获取所有VIP等级配置
     */
    public List<MerchantGroup> getAllActiveGroups() {
        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getStatus, "active")
                .orderByAsc(MerchantGroup::getVipLevel);
        return merchantGroupMapper.selectList(wrapper);
    }

    /**
     * 获取下一级VIP等级信息
     *
     * @param currentVipLevel 当前VIP等级
     * @param currentTotalAmount 当前累计消费金额
     * @return 下一级分组，如果没有更高等级则返回null
     */
    public MerchantGroup getNextLevelGroup(int currentVipLevel, int currentTotalAmount) {
        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getStatus, "active")
                .gt(MerchantGroup::getVipLevel, currentVipLevel)
                .orderByAsc(MerchantGroup::getAmountThreshold)
                .last("LIMIT 1");
        return merchantGroupMapper.selectOne(wrapper);
    }
}
