package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.dto.ActivationCodeBatchCodesPageRequest;
import com.bend.platform.dto.ActivationCodeBatchPageRequest;
import com.bend.platform.dto.ActivationCodePageRequest;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.ActivationCodeBatch;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.ActivationCodeBatchMapper;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.service.ActivationCodeService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

/**
 * 激活码服务实现类
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class ActivationCodeServiceImpl implements ActivationCodeService {

    private final ActivationCodeMapper activationCodeMapper;
    private final ActivationCodeBatchMapper activationCodeBatchMapper;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ActivationCodeBatch generateBatch(String merchantId, String batchName, Integer points, int count, LocalDateTime expireTime) {
        return generateBatch(merchantId, batchName, "points", null, null, points, null, null, count, expireTime);
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ActivationCodeBatch generateBatch(String merchantId, String batchName, String subscriptionType,
                                            String targetId, String targetName, Integer points,
                                            Integer durationDays, BigDecimal dailyPrice,
                                            int count, LocalDateTime expireTime) {
        String subType = subscriptionType != null ? subscriptionType : "points";
        if ("points".equals(subType) && (points == null || points <= 0)) {
            throw new BusinessException(ResultCode.System.PARAM_INVALID, "点数类型激活码必须设置点数");
        }

        ActivationCodeBatch batch = new ActivationCodeBatch();
        batch.setMerchantId(merchantId);
        batch.setBatchName(batchName);
        batch.setSubscriptionType(subType);
        batch.setTargetId(targetId);
        batch.setTargetName(targetName);
        batch.setPoints(points);
        batch.setPointsAmount(points);
        batch.setDurationDays(durationDays);
        batch.setDailyPrice(dailyPrice);
        batch.setTotalCount(count);
        batch.setUsedCount(0);
        batch.setRemainingCount(count);
        batch.setExpireTime(expireTime);
        batch.setStatus("active");

        activationCodeBatchMapper.insert(batch);

        List<ActivationCode> codes = new ArrayList<>();
        String prefix = "ACT";
        DateTimeFormatter formatter = DateTimeFormatter.ofPattern("yyyyMMdd");

        for (int i = 0; i < count; i++) {
            ActivationCode code = new ActivationCode();
            code.setMerchantId(merchantId);
            code.setBatchId(batch.getId());
            code.setCode(generateCode(prefix, formatter));
            code.setStatus("unused");
            code.setExpireTime(expireTime);
            code.setSubscriptionType(batch.getSubscriptionType());
            code.setTargetId(batch.getTargetId());
            code.setTargetName(batch.getTargetName());
            code.setDurationDays(batch.getDurationDays());
            code.setDailyPrice(batch.getDailyPrice());
            code.setPointsAmount(batch.getPointsAmount());
            codes.add(code);
        }

        for (ActivationCode code : codes) {
            activationCodeMapper.insert(code);
        }

        log.info("生成激活码批次 - batchId: {}, merchantId: {}, count: {}, type: {}",
                batch.getId(), merchantId, count, subType);
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
    public ActivationCode useCode(String code, String userId) {
        ActivationCode activationCode = findByCode(code);
        if (activationCode == null) {
            throw new BusinessException(ResultCode.ActivationCode.NOT_FOUND);
        }

        if (!"unused".equals(activationCode.getStatus())) {
            throw new BusinessException(ResultCode.ActivationCode.ALREADY_USED);
        }

        if (activationCode.getExpireTime() != null && activationCode.getExpireTime().isBefore(LocalDateTime.now())) {
            throw new BusinessException(ResultCode.ActivationCode.EXPIRED);
        }

        activationCode.setStatus("used");
        activationCode.setUsedBy(userId);
        activationCode.setUsedTime(LocalDateTime.now());
        activationCodeMapper.updateById(activationCode);

        log.info("使用激活码 - codeId: {}, userId: {}", activationCode.getId(), userId);
        return activationCode;
    }

    @Override
    public IPage<ActivationCode> findByBatchId(String batchId, ActivationCodeBatchCodesPageRequest request) {
        Page<ActivationCode> page = new Page<>(request.getPageNum(), request.getPageSize());
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCode::getBatchId, batchId);

        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(ActivationCode::getStatus, request.getStatus());
        }

        wrapper.orderByDesc(ActivationCode::getCreatedTime);
        return activationCodeMapper.selectPage(page, wrapper);
    }

    @Override
    public List<ActivationCodeBatch> findAllBatchesByMerchantId(String merchantId) {
        LambdaQueryWrapper<ActivationCodeBatch> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(merchantId)) {
            wrapper.eq(ActivationCodeBatch::getMerchantId, merchantId);
        }
        wrapper.orderByDesc(ActivationCodeBatch::getCreatedTime);
        return activationCodeBatchMapper.selectList(wrapper);
    }

    @Override
    public IPage<ActivationCodeBatch> findBatchesByMerchantId(String merchantId, ActivationCodeBatchPageRequest request) {
        Page<ActivationCodeBatch> page = new Page<>(request.getPageNum(), request.getPageSize());
        LambdaQueryWrapper<ActivationCodeBatch> wrapper = new LambdaQueryWrapper<>();
        if (StringUtils.hasText(merchantId)) {
            wrapper.eq(ActivationCodeBatch::getMerchantId, merchantId);
        }
        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(ActivationCodeBatch::getStatus, request.getStatus());
        }
        wrapper.orderByDesc(ActivationCodeBatch::getCreatedTime);
        return activationCodeBatchMapper.selectPage(page, wrapper);
    }

    @Override
    public ActivationCodeBatch findBatchById(String batchId) {
        return activationCodeBatchMapper.selectById(batchId);
    }

    @Override
    public IPage<ActivationCode> findByMerchantId(String merchantId, ActivationCodePageRequest request) {
        Page<ActivationCode> page = new Page<>(request.getPageNum(), request.getPageSize());
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(merchantId)) {
            wrapper.eq(ActivationCode::getMerchantId, merchantId);
        }

        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(ActivationCode::getStatus, request.getStatus());
        }

        if (StringUtils.hasText(request.getSubscriptionType())) {
            wrapper.eq(ActivationCode::getSubscriptionType, request.getSubscriptionType());
        }

        wrapper.orderByDesc(ActivationCode::getCreatedTime);
        return activationCodeMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<ActivationCode> findByMerchantId(String merchantId, String keyword, ActivationCodePageRequest request) {
        Page<ActivationCode> page = new Page<>(request.getPageNum(), request.getPageSize());
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();

        if (StringUtils.hasText(merchantId)) {
            wrapper.eq(ActivationCode::getMerchantId, merchantId);
        }

        if (StringUtils.hasText(request.getStatus())) {
            wrapper.eq(ActivationCode::getStatus, request.getStatus());
        }

        if (StringUtils.hasText(request.getSubscriptionType())) {
            wrapper.eq(ActivationCode::getSubscriptionType, request.getSubscriptionType());
        }

        if (StringUtils.hasText(keyword)) {
            wrapper.and(w -> w.like(ActivationCode::getCode, keyword)
                    .or().like(ActivationCode::getTargetName, keyword));
        }

        wrapper.orderByDesc(ActivationCode::getCreatedTime);
        return activationCodeMapper.selectPage(page, wrapper);
    }

    @Override
    public void deleteByIds(List<String> ids) {
        if (ids == null || ids.isEmpty()) {
            return;
        }
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.in(ActivationCode::getId, ids)
                .eq(ActivationCode::getStatus, "unused");
        activationCodeMapper.delete(wrapper);
        log.info("批量删除激活码 - count: {}", ids.size());
    }

    private String generateCode(String prefix, DateTimeFormatter formatter) {
        return prefix + "-" +
                LocalDateTime.now().format(formatter) + "-" +
                UUID.randomUUID().toString().substring(0, 8).toUpperCase();
    }
}
