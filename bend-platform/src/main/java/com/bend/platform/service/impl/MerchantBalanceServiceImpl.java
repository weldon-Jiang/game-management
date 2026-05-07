package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.conditions.update.LambdaUpdateWrapper;
import com.bend.platform.entity.MerchantBalance;
import com.bend.platform.entity.PointTransaction;
import com.bend.platform.entity.Merchant;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantBalanceMapper;
import com.bend.platform.repository.PointTransactionMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.MerchantBalanceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

@Slf4j
@Service
@RequiredArgsConstructor
public class MerchantBalanceServiceImpl implements MerchantBalanceService {

    private final MerchantBalanceMapper balanceMapper;
    private final PointTransactionMapper transactionMapper;
    private final MerchantMapper merchantMapper;
    private final VipLevelService vipLevelService;

    @Override
    public MerchantBalance getByMerchantId(String merchantId) {
        LambdaQueryWrapper<MerchantBalance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantBalance::getMerchantId, merchantId);
        MerchantBalance balance = balanceMapper.selectOne(wrapper);
        if (balance == null) {
            balance = new MerchantBalance();
            balance.setMerchantId(merchantId);
            balance.setBalance(0);
            balance.setTotalRecharged(0);
            balance.setTotalConsumed(0);
            balance.setVersion(0);
            balanceMapper.insert(balance);
        }
        return balance;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void initBalance(String merchantId) {
        LambdaQueryWrapper<MerchantBalance> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantBalance::getMerchantId, merchantId);
        if (balanceMapper.selectOne(wrapper) == null) {
            MerchantBalance balance = new MerchantBalance();
            balance.setMerchantId(merchantId);
            balance.setBalance(0);
            balance.setTotalRecharged(0);
            balance.setTotalConsumed(0);
            balance.setVersion(0);
            balanceMapper.insert(balance);
            log.info("初始化商户点数账户 - merchantId: {}", merchantId);
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void addPoints(String merchantId, int points, String userId, String type, String refId, String description) {
        MerchantBalance balance = getByMerchantId(merchantId);
        int oldBalance = balance.getBalance();

        LambdaUpdateWrapper<MerchantBalance> updateWrapper = new LambdaUpdateWrapper<>();
        updateWrapper.eq(MerchantBalance::getId, balance.getId());
        updateWrapper.eq(MerchantBalance::getVersion, balance.getVersion());
        updateWrapper.set(balance.getBalance() + points > 0, MerchantBalance::getBalance, oldBalance + points);
        if ("recharge".equals(type) || "activation_code".equals(type)) {
            updateWrapper.set(MerchantBalance::getTotalRecharged, balance.getTotalRecharged() + points);
        }
        updateWrapper.set(MerchantBalance::getVersion, balance.getVersion() + 1);
        int rows = balanceMapper.update(null, updateWrapper);

        if (rows == 0) {
            throw new BusinessException(ResultCode.System.UNKNOWN_ERROR, "更新失败，请重试");
        }

        balance.setBalance(oldBalance + points);
        if ("recharge".equals(type) || "activation_code".equals(type)) {
            balance.setTotalRecharged(balance.getTotalRecharged() + points);
        }
        balance.setVersion(balance.getVersion() + 1);

        PointTransaction transaction = new PointTransaction();
        transaction.setMerchantId(merchantId);
        transaction.setUserId(userId);
        transaction.setType(type);
        transaction.setPoints(points);
        transaction.setBalanceBefore(oldBalance);
        transaction.setBalanceAfter(balance.getBalance());
        transaction.setRefSubscriptionId("subscription".equals(type) ? refId : null);
        transaction.setRefRechargeRecordId("recharge".equals(type) ? refId : null);
        transaction.setRefRechargeCardId("card".equals(type) ? refId : null);
        transaction.setDescription(description);
        transactionMapper.insert(transaction);

        log.info("增加点数 - merchantId: {}, points: {}, oldBalance: {}, newBalance: {}",
                merchantId, points, oldBalance, balance.getBalance());

        if (("recharge".equals(type) || "activation_code".equals(type)) && points > 0) {
            // 同步更新 merchant 表的 totalPoints（作为缓存字段）
            LambdaUpdateWrapper<Merchant> merchantUpdateWrapper = new LambdaUpdateWrapper<>();
            merchantUpdateWrapper.eq(Merchant::getId, merchantId)
                    .setSql("total_points = COALESCE(total_points, 0) + " + points);
            merchantMapper.update(null, merchantUpdateWrapper);

            // 计算新的累计点数并传入，避免循环依赖
            int newTotalRecharged = (balance.getTotalRecharged() != null ? balance.getTotalRecharged() : 0) + points;
            Integer newVipLevel = vipLevelService.checkUpgrade(merchantId, newTotalRecharged);
            if (newVipLevel != null) {
                log.info("商户 {} VIP等级已升级到 {}", merchantId, newVipLevel);
            }
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void recordActivationCodeValueForVipUpgrade(String merchantId, int points) {
        if (points <= 0) {
            return;
        }

        // 获取当前累计点数
        MerchantBalance balance = getByMerchantId(merchantId);
        int oldTotalRecharged = balance != null && balance.getTotalRecharged() != null ? balance.getTotalRecharged() : 0;
        int newTotalRecharged = oldTotalRecharged + points;

        // 将激活码点数价值计入 totalRecharged（用于VIP升级判定）
        // 但不增加实际余额（因为订阅类型激活码是直接创建订阅，不涉及余额变动）
        LambdaUpdateWrapper<MerchantBalance> balanceUpdateWrapper = new LambdaUpdateWrapper<>();
        balanceUpdateWrapper.eq(MerchantBalance::getMerchantId, merchantId)
                .setSql("total_recharged = COALESCE(total_recharged, 0) + " + points);
        balanceMapper.update(null, balanceUpdateWrapper);

        // 同步更新 merchant 表的 total_points
        LambdaUpdateWrapper<Merchant> merchantUpdateWrapper = new LambdaUpdateWrapper<>();
        merchantUpdateWrapper.eq(Merchant::getId, merchantId)
                .setSql("total_points = COALESCE(total_points, 0) + " + points);
        merchantMapper.update(null, merchantUpdateWrapper);

        // 检查VIP升级，传入新的累计点数避免循环依赖
        Integer newVipLevel = vipLevelService.checkUpgrade(merchantId, newTotalRecharged);
        if (newVipLevel != null) {
            log.info("商户 {} 激活码消费 {} 点，VIP等级已升级到 {}", merchantId, points, newVipLevel);
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean deductPoints(String merchantId, int points, String userId, String type, String refId, String description) {
        MerchantBalance balance = getByMerchantId(merchantId);
        int oldBalance = balance.getBalance();

        if (oldBalance < points) {
            log.warn("余额不足 - merchantId: {}, required: {}, actual: {}", merchantId, points, oldBalance);
            return false;
        }

        LambdaUpdateWrapper<MerchantBalance> updateWrapper = new LambdaUpdateWrapper<>();
        updateWrapper.eq(MerchantBalance::getId, balance.getId());
        updateWrapper.eq(MerchantBalance::getVersion, balance.getVersion());
        updateWrapper.set(MerchantBalance::getBalance, oldBalance - points);
        updateWrapper.set(MerchantBalance::getTotalConsumed, balance.getTotalConsumed() + points);
        updateWrapper.set(MerchantBalance::getVersion, balance.getVersion() + 1);
        int rows = balanceMapper.update(null, updateWrapper);

        if (rows == 0) {
            log.warn("扣减点数失败，版本冲突 - merchantId: {}", merchantId);
            return false;
        }

        balance.setBalance(oldBalance - points);
        balance.setTotalConsumed(balance.getTotalConsumed() + points);
        balance.setVersion(balance.getVersion() + 1);

        PointTransaction transaction = new PointTransaction();
        transaction.setMerchantId(merchantId);
        transaction.setUserId(userId);
        transaction.setType(type);
        transaction.setPoints(-points);
        transaction.setBalanceBefore(oldBalance);
        transaction.setBalanceAfter(balance.getBalance());
        transaction.setRefSubscriptionId("subscription".equals(type) ? refId : null);
        transaction.setDescription(description);
        transactionMapper.insert(transaction);

        log.info("扣除点数 - merchantId: {}, points: {}, oldBalance: {}, newBalance: {}",
                merchantId, points, oldBalance, balance.getBalance());
        return true;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean refundPoints(String merchantId, int points, String userId, String subscriptionId, String description) {
        if (points <= 0) {
            log.warn("退款点数必须为正数 - merchantId: {}, points: {}", merchantId, points);
            return false;
        }

        MerchantBalance balance = getByMerchantId(merchantId);
        int oldBalance = balance.getBalance();

        LambdaUpdateWrapper<MerchantBalance> updateWrapper = new LambdaUpdateWrapper<>();
        updateWrapper.eq(MerchantBalance::getId, balance.getId());
        updateWrapper.eq(MerchantBalance::getVersion, balance.getVersion());
        updateWrapper.set(MerchantBalance::getBalance, oldBalance + points);
        updateWrapper.set(MerchantBalance::getVersion, balance.getVersion() + 1);
        int rows = balanceMapper.update(null, updateWrapper);

        if (rows == 0) {
            log.warn("退款点数失败，版本冲突 - merchantId: {}", merchantId);
            return false;
        }

        balance.setBalance(oldBalance + points);
        balance.setVersion(balance.getVersion() + 1);

        PointTransaction transaction = new PointTransaction();
        transaction.setMerchantId(merchantId);
        transaction.setUserId(userId);
        transaction.setType("refund");
        transaction.setPoints(points);
        transaction.setBalanceBefore(oldBalance);
        transaction.setBalanceAfter(balance.getBalance());
        transaction.setRefSubscriptionId(subscriptionId);
        transaction.setDescription(description);
        transactionMapper.insert(transaction);

        log.info("退款点数 - merchantId: {}, points: {}, oldBalance: {}, newBalance: {}",
                merchantId, points, oldBalance, balance.getBalance());
        return true;
    }

    @Override
    public boolean hasEnoughBalance(String merchantId, int points) {
        MerchantBalance balance = getByMerchantId(merchantId);
        return balance.getBalance() >= points;
    }
}
