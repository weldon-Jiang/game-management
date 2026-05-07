package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantBalance;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.MerchantBalanceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.ObjectProvider;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.stream.Collectors;

/**
 * VIP等级自动升级服务
 * 根据商户累计充值点数，自动计算并升级VIP等级
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class VipLevelService {

    private final MerchantMapper merchantMapper;
    private final VipLevelCalculator vipLevelCalculator;
    private final ObjectProvider<MerchantBalanceService> merchantBalanceServiceProvider;

    /**
     * 根据累计充值点数检查VIP升级
     * 注意：totalPoints应由调用方计算后传入，避免循环依赖
     *
     * @param merchantId 商户ID
     * @param totalPoints 当前累计点数（应在调用前由调用方计算）
     * @return 升级后的VIP等级，如果没有升级则返回null
     */
    @Transactional
    public Integer checkUpgrade(String merchantId, int totalPoints) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        int oldVipLevel = merchant.getVipLevel() != null ? merchant.getVipLevel() : 0;
        int newVipLevel = vipLevelCalculator.calculateVipLevel(totalPoints);

        if (newVipLevel > oldVipLevel) {
            merchant.setVipLevel(newVipLevel);
            merchantMapper.updateById(merchant);
            log.info("商户 {} VIP等级升级: {} -> {}, 累计点数: {}",
                    merchantId, oldVipLevel, newVipLevel, totalPoints);
            return newVipLevel;
        }

        return null;
    }

    /**
     * 根据商户ID检查VIP升级（兼容旧接口，内部获取totalPoints）
     * @deprecated 请使用 checkUpgrade(String merchantId, int totalPoints) 避免循环依赖
     */
    @Transactional
    public Integer checkUpgrade(String merchantId) {
        MerchantBalance balance = merchantBalanceServiceProvider.getObject().getByMerchantId(merchantId);
        int totalPoints = balance != null && balance.getTotalRecharged() != null ? balance.getTotalRecharged() : 0;
        return checkUpgrade(merchantId, totalPoints);
    }

    /**
     * 根据累计点数计算VIP等级
     */
    public int calculateVipLevel(int totalPoints) {
        return vipLevelCalculator.calculateVipLevel(totalPoints);
    }

    /**
     * 获取商户当前VIP信息
     */
    public VipInfo getVipInfo(String merchantId) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        // 优先使用 merchant.totalPoints，如果没有则尝试从 balance 获取
        int totalPoints = merchant.getTotalPoints() != null ? merchant.getTotalPoints() : 0;
        log.info("商户 {} 的 merchant.totalPoints: {}", merchantId, totalPoints);
        
        if (totalPoints == 0) {
            MerchantBalance balance = merchantBalanceServiceProvider.getObject().getByMerchantId(merchantId);
            totalPoints = balance != null && balance.getTotalRecharged() != null ? balance.getTotalRecharged() : 0;
            log.info("商户 {} 的 balance.totalRecharged: {}", merchantId, totalPoints);
        }

        // 根据累计点数计算实际的VIP等级（而不是使用存储的vipLevel字段）
        int currentVipLevel = vipLevelCalculator.calculateVipLevel(totalPoints);
        log.info("商户 {} 的累计点数: {}, 计算的VIP等级: {}", merchantId, totalPoints, currentVipLevel);

        VipInfo info = new VipInfo();
        info.setMerchantId(merchantId);
        info.setTotalPoints(totalPoints);
        info.setCurrentVipLevel(currentVipLevel);
        info.setNextVipLevel(currentVipLevel + 1);

        var nextGroup = vipLevelCalculator.getNextLevelGroup(currentVipLevel, totalPoints);
        if (nextGroup != null) {
            info.setNextVipLevel(nextGroup.getVipLevel());
            info.setPointsToNextLevel(nextGroup.getPointsThreshold() - totalPoints);
        } else {
            info.setNextVipLevel(currentVipLevel);
            info.setPointsToNextLevel(0);
        }

        return info;
    }

    /**
     * 获取所有VIP等级配置
     */
    public java.util.List<VipLevelInfo> getAllVipLevels() {
        return vipLevelCalculator.getAllActiveGroups().stream().map(g -> {
            VipLevelInfo levelInfo = new VipLevelInfo();
            levelInfo.setVipLevel(g.getVipLevel());
            levelInfo.setGroupName(g.getName());
            levelInfo.setPointsThreshold(g.getPointsThreshold() != null ? g.getPointsThreshold() : 0);
            return levelInfo;
        }).collect(Collectors.toList());
    }

    /**
     * VIP信息DTO
     */
    @lombok.Data
    public static class VipInfo {
        private String merchantId;
        private int totalPoints;
        private int currentVipLevel;
        private int nextVipLevel;
        private int pointsToNextLevel;
    }

    @lombok.Data
    public static class VipLevelInfo {
        private int vipLevel;
        private String groupName;
        private int pointsThreshold;
    }
}
