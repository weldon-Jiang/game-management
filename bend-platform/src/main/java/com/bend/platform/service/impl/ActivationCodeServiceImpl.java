package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.ActivationCodeBatchCodesPageRequest;
import com.bend.platform.dto.ActivationCodeBatchPageRequest;
import com.bend.platform.dto.ActivationCodePageRequest;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.ActivationCodeBatch;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.VipConfig;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.ActivationCodeBatchMapper;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.VipConfigMapper;
import com.bend.platform.service.ActivationCodeService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * 激活码服务实现类
 *
 * 功能说明：
 * - 管理VIP激活码的生成和使用
 * - 支持单个和批量生成激活码
 *
 * 主要功能：
 * - 生成单个激活码
 * - 批量生成激活码
 * - 查询激活码
 * - 使用激活码
 * - 删除激活码
 * - 查询激活码批次
 * - 删除批次
 *
 * 依赖注入：
 * - 使用Lombok的@RequiredArgsConstructor注解
 * - 为所有 final字段生成构造器进行依赖注入
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ActivationCodeServiceImpl implements ActivationCodeService {

    private final ActivationCodeMapper activationCodeMapper;
    private final ActivationCodeBatchMapper activationCodeBatchMapper;
    private final VipConfigMapper vipConfigMapper;
    private final MerchantMapper merchantMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ActivationCodeBatch generateBatch(String merchantId, String batchName, String vipType, int count, LocalDateTime expireTime) {
        // 查询VIP配置，获取vipConfigId
        LambdaQueryWrapper<VipConfig> vipWrapper = new LambdaQueryWrapper<>();
        vipWrapper.eq(VipConfig::getVipType, vipType)
                  .eq(VipConfig::getStatus, "active")
                  .last("LIMIT 1");
        VipConfig vipConfig = vipConfigMapper.selectOne(vipWrapper);

        if (vipConfig == null) {
            throw new BusinessException(ResultCode.VipConfig.NOT_FOUND);
        }

        // 创建批次
        ActivationCodeBatch batch = new ActivationCodeBatch();
        batch.setMerchantId(merchantId);
        batch.setBatchName(batchName);
        batch.setVipType(vipType);
        batch.setVipConfigId(vipConfig.getId());
        batch.setTotalCount(count);
        batch.setUsedCount(0);
        batch.setRemainingCount(count);
        batch.setExpireTime(expireTime);
        batch.setStatus("active");

        activationCodeBatchMapper.insert(batch);

        // 生成激活码
        List<ActivationCode> codes = new ArrayList<>();
        String prefix = generatePrefix(vipType);
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyyMMdd");

        for (int i = 0; i < count; i++) {
            ActivationCode code = new ActivationCode();
            code.setMerchantId(merchantId);
            code.setBatchId(batch.getId());
            code.setCode(generateCode(prefix, formatter));
            code.setStatus("unused");
            code.setExpireTime(expireTime);
            codes.add(code);
        }

        // 批量插入
        for (ActivationCode code : codes) {
            activationCodeMapper.insert(code);
        }

        log.info("生成激活码批次成功 - 批次ID: {}, 数量: {}, VIP类型: {}", batch.getId(), count, vipType);
        return batch;
    }

    @Override
    public ActivationCode findById(String id) {
        return activationCodeMapper.selectById(id);
    }

    @Override
    public ActivationCode findByCode(String code) {
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCode::getCode, code);
        return activationCodeMapper.selectOne(wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ActivationCode useCode(String codeStr, String userId) {
        ActivationCode code = findByCode(codeStr);
        if (code == null) {
            throw new BusinessException(ResultCode.ActivationCode.NOT_FOUND);
        }

        if ("used".equals(code.getStatus())) {
            throw new BusinessException(ResultCode.ActivationCode.ALREADY_USED);
        }

        if (code.getExpireTime() != null && code.getExpireTime().isBefore(LocalDateTime.now())) {
            throw new BusinessException(ResultCode.ActivationCode.EXPIRED);
        }

        // 计算新的到期时间：商户当前到期时间 + VIP配置的天数
        LocalDateTime now = LocalDateTime.now();
        LocalDateTime newExpireTime = now;
        LocalDateTime usedTime = now;

        // 获取批次信息
        ActivationCodeBatch batch = activationCodeBatchMapper.selectById(code.getBatchId());

        if (batch != null && batch.getVipConfigId() != null) {
            VipConfig vipConfig = vipConfigMapper.selectById(batch.getVipConfigId());
            if (vipConfig != null && vipConfig.getDurationDays() != null) {
                // 获取商户信息
                Merchant merchant = merchantMapper.selectById(code.getMerchantId());
                LocalDateTime baseTime = now;
                if (merchant != null && merchant.getExpireTime() != null && merchant.getExpireTime().isAfter(now)) {
                    // 如果商户已有到期时间且未过期，以商户到期时间为基础累加
                    baseTime = merchant.getExpireTime();
                }
                newExpireTime = baseTime.plusDays(vipConfig.getDurationDays());
                usedTime = baseTime;
            }
        }

        code.setStatus("used");
        code.setUsedBy(userId);
        code.setUsedTime(usedTime);
        code.setExpireTime(newExpireTime);
        activationCodeMapper.updateById(code);

        // 更新批次统计
        if (batch != null) {
            batch.setUsedCount(batch.getUsedCount() + 1);
            batch.setRemainingCount(batch.getRemainingCount() - 1);
            if (batch.getRemainingCount() <= 0) {
                batch.setStatus("completed");
            }
            activationCodeBatchMapper.updateById(batch);
        }

        log.info("激活码使用成功 - 激活码: {}, 用户ID: {}, 新到期时间: {}", codeStr, userId, newExpireTime);
        return code;
    }

    @Override
    public IPage<ActivationCode> findByBatchId(String batchId, ActivationCodeBatchCodesPageRequest request) {
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCode::getBatchId, batchId)
               .orderByDesc(ActivationCode::getCreatedTime);
        Page<ActivationCode> page = new Page<>(request.getPageNum(), request.getPageSize());
        return activationCodeMapper.selectPage(page, wrapper);
    }

    @Override
    public List<ActivationCodeBatch> findAllBatchesByMerchantId(String merchantId) {
        LambdaQueryWrapper<ActivationCodeBatch> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(ActivationCodeBatch::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(ActivationCodeBatch::getCreatedTime);
        return activationCodeBatchMapper.selectList(wrapper);
    }

    @Override
    public IPage<ActivationCodeBatch> findBatchesByMerchantId(String merchantId, ActivationCodeBatchPageRequest request) {
        LambdaQueryWrapper<ActivationCodeBatch> wrapper = new LambdaQueryWrapper<>();
        if (merchantId != null) {
            wrapper.eq(ActivationCodeBatch::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(ActivationCodeBatch::getCreatedTime);
        Page<ActivationCodeBatch> page = new Page<>(request.getPageNum(), request.getPageSize());
        return activationCodeBatchMapper.selectPage(page, wrapper);
    }

    @Override
    public ActivationCodeBatch findBatchById(String batchId) {
        return activationCodeBatchMapper.selectById(batchId);
    }

    @Override
    public IPage<ActivationCode> findByMerchantId(String merchantId, ActivationCodePageRequest request) {
        return findByMerchantId(merchantId, null, request);
    }

    @Override
    public IPage<ActivationCode> findByMerchantId(String merchantId, String keyword, ActivationCodePageRequest request) {
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(merchantId)) {
            wrapper.eq(ActivationCode::getMerchantId, merchantId);
        }
        if (StringUtils.hasText(keyword)) {
            wrapper.like(ActivationCode::getCode, keyword);
        }
        wrapper.orderByDesc(ActivationCode::getCreatedTime);
        Page<ActivationCode> page = new Page<>(request.getPageNum(), request.getPageSize(), true);
        return activationCodeMapper.selectPage(page, wrapper);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteByIds(List<String> ids) {
        for (String id : ids) {
            activationCodeMapper.deleteById(id);
        }
        log.info("批量删除激活码成功 - 数量: {}", ids.size());
    }

    private String generatePrefix(String vipType) {
        return "VIP-" + vipType.toUpperCase().substring(0, Math.min(3, vipType.length()));
    }

    private String generateCode(String prefix, DateTimeFormatter formatter) {
        String date = LocalDateTime.now().format(formatter);
        String uuid = UUID.randomUUID().toString().replace("-", "").substring(0, 8).toUpperCase();
        return prefix + "-" + date + "-" + uuid;
    }
}