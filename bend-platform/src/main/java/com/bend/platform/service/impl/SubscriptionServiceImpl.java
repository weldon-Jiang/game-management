package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.entity.DeviceBinding;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantBalance;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.entity.Subscription;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.DeviceBindingMapper;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.SubscriptionMapper;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.SubscriptionService;
import com.bend.platform.util.DataSecurityUtil;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.time.temporal.ChronoUnit;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class SubscriptionServiceImpl implements SubscriptionService {

    private final SubscriptionMapper subscriptionMapper;
    private final DeviceBindingMapper deviceBindingMapper;
    private final MerchantGroupMapper merchantGroupMapper;
    private final MerchantMapper merchantMapper;
    private final MerchantBalanceService balanceService;
    private final DataSecurityUtil dataSecurityUtil;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Subscription createSubscription(String merchantId, String userId, String type,
                                           String targetId, String targetName, int pointsCost, int durationDays) {
        if (!balanceService.hasEnoughBalance(merchantId, pointsCost)) {
            throw new BusinessException(ResultCode.Balance.NOT_ENOUGH, "点数余额不足");
        }

        boolean deducted = balanceService.deductPoints(merchantId, pointsCost, userId, "subscription",
                targetId, "开通" + getTypeName(type) + ": " + targetName);
        if (!deducted) {
            throw new BusinessException(ResultCode.Balance.NOT_ENOUGH, "扣点失败");
        }

        Subscription subscription = new Subscription();
        subscription.setMerchantId(merchantId);
        subscription.setUserId(userId);
        subscription.setType(type);
        subscription.setTargetId(targetId);
        subscription.setTargetName(targetName);
        subscription.setPointsCost(pointsCost);
        subscription.setDurationDays(durationDays);
        subscription.setStartTime(LocalDateTime.now());
        subscription.setExpireTime(LocalDateTime.now().plusDays(durationDays));
        subscription.setStatus("active");
        subscription.setAutoRenew(false);
        subscriptionMapper.insert(subscription);

        DeviceBinding binding = new DeviceBinding();
        binding.setMerchantId(merchantId);
        binding.setUserId(userId);
        binding.setType(type);
        binding.setDeviceId(targetId);
        binding.setDeviceName(targetName);
        binding.setBoundSubscriptionId(subscription.getId());
        binding.setBoundTime(LocalDateTime.now());
        binding.setIsActive(true);
        binding.setUnbindCount(0);
        deviceBindingMapper.insert(binding);

        log.info("创建订阅 - id: {}, merchantId: {}, type: {}, targetId: {}, pointsCost: {}",
                subscription.getId(), merchantId, type, targetId, pointsCost);
        return subscription;
    }
    
    @Override
    @Transactional(rollbackFor = Exception.class)
    public Subscription createSubscriptionWithoutDeduction(String merchantId, String userId, String type,
                                                           String targetId, String targetName, int durationDays) {
        // 不检查余额，不扣点
        Subscription subscription = new Subscription();
        subscription.setMerchantId(merchantId);
        subscription.setUserId(userId);
        subscription.setType(type);
        subscription.setTargetId(targetId);
        subscription.setTargetName(targetName);
        subscription.setPointsCost(0); // 激活码不扣点
        subscription.setDurationDays(durationDays);
        subscription.setStartTime(LocalDateTime.now());
        subscription.setExpireTime(LocalDateTime.now().plusDays(durationDays));
        subscription.setStatus("active");
        subscription.setAutoRenew(false);
        subscription.setRemark("激活码兑换");
        subscriptionMapper.insert(subscription);

        DeviceBinding binding = new DeviceBinding();
        binding.setMerchantId(merchantId);
        binding.setUserId(userId);
        binding.setType(type);
        binding.setDeviceId(targetId);
        binding.setDeviceName(targetName);
        binding.setBoundSubscriptionId(subscription.getId());
        binding.setBoundTime(LocalDateTime.now());
        binding.setIsActive(true);
        binding.setUnbindCount(0);
        deviceBindingMapper.insert(binding);

        log.info("创建订阅（激活码） - id: {}, merchantId: {}, type: {}, targetId: {}",
                subscription.getId(), merchantId, type, targetId);
        return subscription;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public Subscription renewSubscription(String subscriptionId, int durationDays, int pointsCost) {
        Subscription subscription = subscriptionMapper.selectById(subscriptionId);
        if (subscription == null) {
            throw new BusinessException(ResultCode.Subscription.NOT_FOUND);
        }

        if (!"active".equals(subscription.getStatus()) && !"expired".equals(subscription.getStatus())) {
            throw new BusinessException(ResultCode.Subscription.INVALID_STATUS, "当前状态不允许续费");
        }

        String merchantId = subscription.getMerchantId();
        String userId = UserContext.getUserId();

        if (!balanceService.hasEnoughBalance(merchantId, pointsCost)) {
            throw new BusinessException(ResultCode.Balance.NOT_ENOUGH, "点数余额不足");
        }

        boolean deducted = balanceService.deductPoints(merchantId, pointsCost, userId, "renew",
                subscriptionId, "续费" + getTypeName(subscription.getType()) + ": " + subscription.getTargetName());
        if (!deducted) {
            throw new BusinessException(ResultCode.Balance.NOT_ENOUGH, "扣点失败");
        }

        LocalDateTime newExpireTime = subscription.getExpireTime();
        if (newExpireTime == null || newExpireTime.isBefore(LocalDateTime.now())) {
            newExpireTime = LocalDateTime.now();
        }
        subscription.setExpireTime(newExpireTime.plusDays(durationDays));
        subscription.setDurationDays(subscription.getDurationDays() + durationDays);
        subscription.setPointsCost(subscription.getPointsCost() + pointsCost);
        subscription.setStatus("active");
        subscriptionMapper.updateById(subscription);

        log.info("续费订阅 - id: {}, newExpireTime: {}", subscriptionId, subscription.getExpireTime());
        return subscription;
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void cancelSubscription(String subscriptionId) {
        Subscription subscription = subscriptionMapper.selectById(subscriptionId);
        if (subscription == null) {
            throw new BusinessException(ResultCode.Subscription.NOT_FOUND);
        }

        subscription.setStatus("cancelled");
        subscription.setUpdatedTime(LocalDateTime.now());
        subscriptionMapper.updateById(subscription);

        LambdaQueryWrapper<DeviceBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DeviceBinding::getBoundSubscriptionId, subscriptionId);
        List<DeviceBinding> bindings = deviceBindingMapper.selectList(wrapper);
        for (DeviceBinding binding : bindings) {
            binding.setIsActive(false);
            binding.setUnboundTime(LocalDateTime.now());
            binding.setUnbindCount(binding.getUnbindCount() + 1);
            binding.setLastUnbindTime(LocalDateTime.now());
            deviceBindingMapper.updateById(binding);
        }

        log.info("取消订阅 - id: {}", subscriptionId);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public int unbindDevice(String merchantId, String type, String deviceId, String userId) {
        LambdaQueryWrapper<DeviceBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DeviceBinding::getMerchantId, merchantId)
                .eq(DeviceBinding::getType, type)
                .eq(DeviceBinding::getDeviceId, deviceId)
                .eq(DeviceBinding::getIsActive, true);
        DeviceBinding binding = deviceBindingMapper.selectOne(wrapper);

        if (binding == null) {
            throw new BusinessException(ResultCode.Subscription.DEVICE_NOT_BOUND, "设备未绑定");
        }

        Merchant merchant = merchantMapper.selectById(merchantId);
        MerchantGroup group = null;
        if (merchant != null && merchant.getVipLevel() != null && merchant.getVipLevel() > 0) {
            LambdaQueryWrapper<MerchantGroup> groupWrapper = new LambdaQueryWrapper<>();
            groupWrapper.eq(MerchantGroup::getVipLevel, merchant.getVipLevel())
                    .eq(MerchantGroup::getStatus, "active")
                    .last("LIMIT 1");
            group = merchantGroupMapper.selectOne(groupWrapper);
        }

        int weekUnbindLimit = group != null ? group.getMaxUnbindPerWeek() : 2;
        long weekUnbindCount = countUnbindsThisWeek(binding.getMerchantId(), binding.getType(), binding.getDeviceId());
        if (weekUnbindCount >= weekUnbindLimit) {
            throw new BusinessException(ResultCode.Subscription.UNBIND_LIMIT_EXCEEDED,
                    "本周解绑次数已达上限(" + weekUnbindLimit + "次)");
        }

        Subscription subscription = subscriptionMapper.selectById(binding.getBoundSubscriptionId());
        if (subscription != null && "active".equals(subscription.getStatus()) && subscription.getExpireTime() != null) {
            long remainingDays = ChronoUnit.DAYS.between(LocalDateTime.now(), subscription.getExpireTime());
            if (remainingDays > 0) {
                double refundRate = group != null ? group.getUnbindRefundRate().doubleValue() : 0.5;
                int refundPoints = (int) (subscription.getPointsCost() * (remainingDays / subscription.getDurationDays()) * refundRate);
                if (refundPoints > 0) {
                    balanceService.refundPoints(merchantId, refundPoints, userId, subscription.getId(),
                            "解绑设备返还: " + binding.getDeviceName());
                    subscription.setRefundPoints(refundPoints);
                }
                subscription.setStatus("unbound");
                subscription.setUnboundTime(LocalDateTime.now());
                subscriptionMapper.updateById(subscription);
            }
        }

        binding.setIsActive(false);
        binding.setUnboundTime(LocalDateTime.now());
        binding.setUnbindCount(binding.getUnbindCount() + 1);
        binding.setLastUnbindTime(LocalDateTime.now());
        deviceBindingMapper.updateById(binding);

        log.info("解绑设备 - merchantId: {}, type: {}, deviceId: {}", merchantId, type, deviceId);
        return binding.getUnbindCount();
    }

    @Override
    public Subscription getById(String subscriptionId) {
        Subscription subscription = subscriptionMapper.selectById(subscriptionId);
        if (subscription != null) {
            dataSecurityUtil.validateMerchantAccess(subscription.getMerchantId(), "Subscription");
        }
        return subscription;
    }

    @Override
    public List<Subscription> getActiveSubscriptions(String merchantId) {
        LambdaQueryWrapper<Subscription> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Subscription::getMerchantId, merchantId)
                .eq(Subscription::getStatus, "active")
                .gt(Subscription::getExpireTime, LocalDateTime.now())
                .orderByDesc(Subscription::getCreatedTime);
        return subscriptionMapper.selectList(wrapper);
    }

    @Override
    public boolean isDeviceBound(String merchantId, String type, String deviceId) {
        LambdaQueryWrapper<DeviceBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DeviceBinding::getMerchantId, merchantId)
                .eq(DeviceBinding::getType, type)
                .eq(DeviceBinding::getDeviceId, deviceId)
                .eq(DeviceBinding::getIsActive, true);
        return deviceBindingMapper.selectCount(wrapper) > 0;
    }

    @Override
    public Subscription getActiveSubscriptionByDevice(String merchantId, String type, String deviceId) {
        LambdaQueryWrapper<DeviceBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DeviceBinding::getMerchantId, merchantId)
                .eq(DeviceBinding::getType, type)
                .eq(DeviceBinding::getDeviceId, deviceId)
                .eq(DeviceBinding::getIsActive, true);
        DeviceBinding binding = deviceBindingMapper.selectOne(wrapper);
        if (binding == null) {
            return null;
        }
        return subscriptionMapper.selectById(binding.getBoundSubscriptionId());
    }

    @Override
    public IPage<Subscription> pageSubscriptions(String merchantId, int pageNum, int pageSize, String status) {
        Page<Subscription> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<Subscription> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(Subscription::getMerchantId, merchantId);
        if (status != null && !status.isEmpty()) {
            wrapper.eq(Subscription::getStatus, status);
        }
        wrapper.orderByDesc(Subscription::getCreatedTime);
        return subscriptionMapper.selectPage(page, wrapper);
    }

    private long countUnbindsThisWeek(String merchantId, String type, String deviceId) {
        LocalDateTime weekAgo = LocalDateTime.now().minusDays(7);
        LambdaQueryWrapper<DeviceBinding> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(DeviceBinding::getMerchantId, merchantId)
                .eq(DeviceBinding::getType, type)
                .eq(DeviceBinding::getDeviceId, deviceId)
                .eq(DeviceBinding::getIsActive, false)
                .ge(DeviceBinding::getLastUnbindTime, weekAgo);
        return deviceBindingMapper.selectCount(wrapper);
    }

    private String getTypeName(String type) {
        return switch (type) {
            case "host" -> "主机";
            case "window" -> "窗口";
            case "account" -> "游戏号";
            default -> type;
        };
    }
}
