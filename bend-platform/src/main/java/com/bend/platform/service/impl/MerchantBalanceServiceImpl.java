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
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.client.RestTemplate;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 商户点数账户：余额查询、扣减/充值及 point_transaction 流水。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MerchantBalanceServiceImpl implements MerchantBalanceService {

    private final MerchantBalanceMapper balanceMapper;
    private final PointTransactionMapper transactionMapper;
    private final MerchantMapper merchantMapper;
    private final VipLevelService vipLevelService;

    @Value("${license.mode:master}")
    private String licenseMode;
    @Value("${license.master-url:}")
    private String masterUrl;
    @Value("${license.key:${LICENSE_KEY:}}")
    private String licenseKey;
    @Value("${license.secret:${LICENSE_SECRET:}}")
    private String licenseSecret;

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

        // 注意：total_amount 的更新在 MerchantSubscriptionController.activate 方法中处理
        // 使用的是 discount_price（价格），而不是 points（点数数量）
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public boolean deductPoints(String merchantId, int points, String userId, String type, String refId, String description) {
        if ("tenant".equalsIgnoreCase(licenseMode)) {
            return proxyDeductToMaster(merchantId, points, refId);
        }
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
        transaction.setIdempotentKey(refId); // 保存幂等键
        transaction.setDescription(description);
        transactionMapper.insert(transaction);

        log.info("扣除点数 - merchantId: {}, points: {}, oldBalance: {}, newBalance: {}",
                merchantId, points, oldBalance, balance.getBalance());
        return true;
    }

    @Override
    public boolean hasDeductedTransaction(String merchantId, String type, String idempotentKey) {
        if (idempotentKey == null || idempotentKey.isEmpty()) {
            return false;
        }
        PointTransaction existing = transactionMapper.selectOne(
                new LambdaQueryWrapper<PointTransaction>()
                        .eq(PointTransaction::getMerchantId, merchantId)
                        .eq(PointTransaction::getType, type)
                        .eq(PointTransaction::getIdempotentKey, idempotentKey)
        );
        return existing != null;
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

    private boolean proxyDeductToMaster(String merchantId, int points, String taskId) {
        try {
            HttpHeaders headers = new HttpHeaders();
            headers.set("X-License-Key", licenseKey);
            headers.set("X-License-Secret", licenseSecret);
            headers.setContentType(MediaType.APPLICATION_JSON);
            Map<String, Object> body = new HashMap<>();
            body.put("points", points);
            body.put("taskId", taskId != null ? taskId : "");
            String url = masterUrl.replaceAll("/+$", "") + "/api/tenant/billing/deduct";
            ResponseEntity<Map> resp = new RestTemplate().postForEntity(url, new HttpEntity<>(body, headers), Map.class);
            return resp.getBody() != null && Integer.valueOf(200).equals(resp.getBody().get("code"));
        } catch (Exception e) {
            log.warn("分控代理扣点失败", e);
            return false;
        }
    }
}
