package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.MerchantBalance;
import com.bend.platform.entity.PointTransaction;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.MerchantBalanceMapper;
import com.bend.platform.repository.PointTransactionMapper;
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

        balance.setBalance(oldBalance + points);
        if ("recharge".equals(type)) {
            balance.setTotalRecharged(balance.getTotalRecharged() + points);
        }
        balanceMapper.updateById(balance);

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

        balance.setBalance(oldBalance - points);
        balance.setTotalConsumed(balance.getTotalConsumed() + points);
        balanceMapper.updateById(balance);

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

        balance.setBalance(oldBalance + points);
        balanceMapper.updateById(balance);

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
