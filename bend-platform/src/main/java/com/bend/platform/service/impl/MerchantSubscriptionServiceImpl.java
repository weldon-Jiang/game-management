package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.VipConfig;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.VipConfigMapper;
import com.bend.platform.service.MerchantSubscriptionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;

/**
 * 商户订阅服务实现类
 *
 * 功能说明：
 * - 管理商户的VIP订阅状态
 * - 处理激活码激活VIP
 *
 * 主要功能：
 * - 使用激活码激活VIP
 * - 获取商户订阅状态
 * - 获取已激活的VIP列表
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class MerchantSubscriptionServiceImpl implements MerchantSubscriptionService {

    private final MerchantMapper merchantMapper;
    private final ActivationCodeMapper activationCodeMapper;
    private final VipConfigMapper vipConfigMapper;

    /**
     * 使用激活码激活/续费商户
     * 1. 校验激活码
     * 2. 根据VIP配置计算新的有效期
     * 3. 更新商户状态和有效期
     *
     * @param merchantId      商户ID
     * @param activationCode 激活码
     * @param userId         操作用户ID (merchant_user.id)
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void activateWithCode(String merchantId, String activationCode, String userId) {
        // 查询商户
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        // 查询激活码
        ActivationCode code = findActivationCode(activationCode);
        if (code == null) {
            throw new BusinessException(ResultCode.ActivationCode.NOT_FOUND);
        }

        // 校验激活码是否属于该商户
        if (!merchantId.equals(code.getMerchantId())) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED, "激活码不属于当前商户");
        }

        // 校验激活码状态
        if ("used".equals(code.getStatus())) {
            throw new BusinessException(ResultCode.ActivationCode.ALREADY_USED);
        }

        // 校验激活码是否过期
        if (code.getExpireTime() != null && code.getExpireTime().isBefore(LocalDateTime.now())) {
            throw new BusinessException(ResultCode.ActivationCode.EXPIRED);
        }

        // 查询VIP配置获取时长
        int durationDays = 30; // 默认30天
        if (code.getVipConfigId() != null) {
            VipConfig vipConfig = vipConfigMapper.selectById(code.getVipConfigId());
            if (vipConfig != null && vipConfig.getDurationDays() != null) {
                durationDays = vipConfig.getDurationDays();
            }
        }

        // 计算新的有效期
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime currentExpireTime = merchant.getExpireTime();

        LocalDateTime newExpireTime;
        if (currentExpireTime == null || currentExpireTime.isBefore(now)) {
            // 商户未过期或无有效期，从现在开始计算
            newExpireTime = now.plusDays(durationDays);
        } else {
            // 商户仍在有效期，在当前有效期基础上续期
            newExpireTime = currentExpireTime.plusDays(durationDays);
        }

        // 更新商户状态和有效期
        merchant.setStatus("active");
        merchant.setExpireTime(newExpireTime);
        merchantMapper.updateById(merchant);

        // 标记激活码已使用，used_by存储用户ID
        code.setStatus("used");
        code.setUsedBy(userId);
        code.setUsedAt(now);
        code.setExpireTime(newExpireTime);
        activationCodeMapper.updateById(code);

        log.info("商户激活成功 - 商户ID: {}, 用户ID: {}, 激活码: {}, 新有效期: {}", merchantId, userId, activationCode, newExpireTime);
    }

    /**
     * 更新商户有效期
     *
     * @param merchantId 商户ID
     * @param days       续费天数
     */
    @Override
    @Transactional(rollbackFor = Exception.class)
    public void extendSubscription(String merchantId, int days) {
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            throw new BusinessException(ResultCode.Merchant.NOT_FOUND);
        }

        LocalDateTime now = LocalDateTime.now();
        LocalDateTime currentExpireTime = merchant.getExpireTime();

        LocalDateTime newExpireTime;
        if (currentExpireTime == null || currentExpireTime.isBefore(now)) {
            newExpireTime = now.plusDays(days);
        } else {
            newExpireTime = currentExpireTime.plusDays(days);
        }

        merchant.setExpireTime(newExpireTime);
        merchant.setStatus("active");
        merchantMapper.updateById(merchant);

        log.info("商户续费成功 - 商户ID: {}, 续费天数: {}, 新有效期: {}", merchantId, days, newExpireTime);
    }

    private ActivationCode findActivationCode(String code) {
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCode::getCode, code);
        return activationCodeMapper.selectOne(wrapper);
    }
}