package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.ActivationCodeBatch;
import com.bend.platform.entity.Merchant;
import com.bend.platform.repository.ActivationCodeBatchMapper;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.ActivationCodeService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class ActivationCodeServiceImpl implements ActivationCodeService {

    private final ActivationCodeMapper activationCodeMapper;
    private final ActivationCodeBatchMapper activationCodeBatchMapper;
    private final MerchantMapper merchantMapper;
    private final VipLevelService vipLevelService;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public ActivationCode generateCode(String merchantId, String subscriptionType, String boundResourceType,
                                       String boundResourceIds, String boundResourceNames,
                                       Integer durationDays, int originalPrice, int discountPrice, Integer pointsAmount) {
        String code = generateUniqueCode();

        ActivationCode activationCode = new ActivationCode();
        activationCode.setMerchantId(merchantId);
        activationCode.setCode(code);
        activationCode.setSubscriptionType(subscriptionType);
        activationCode.setBoundResourceType(boundResourceType);
        activationCode.setBoundResourceIds(boundResourceIds);
        activationCode.setBoundResourceNames(boundResourceNames);
        activationCode.setDurationDays(durationDays);
        activationCode.setOriginalPrice(originalPrice);
        activationCode.setDiscountPrice(discountPrice);
        activationCode.setPointsAmount(pointsAmount);
        activationCode.setStatus("unused");

        activationCodeMapper.insert(activationCode);

        log.info("生成激活码 - merchantId: {}, code: {}, type: {}", merchantId, code, subscriptionType);

        return activationCode;
    }

    @Override
    public IPage<ActivationCode> pageByMerchant(String merchantId, int pageNum, int pageSize, String status) {
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCode::getMerchantId, merchantId);
        if (status != null && !status.isEmpty()) {
            wrapper.eq(ActivationCode::getStatus, status);
        }
        wrapper.orderByDesc(ActivationCode::getCreatedTime);
        Page<ActivationCode> page = new Page<>(pageNum, pageSize);
        return activationCodeMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<ActivationCode> pageAll(int pageNum, int pageSize, String status) {
        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        if (status != null && !status.isEmpty()) {
            wrapper.eq(ActivationCode::getStatus, status);
        }
        wrapper.orderByDesc(ActivationCode::getCreatedTime);
        Page<ActivationCode> page = new Page<>(pageNum, pageSize);
        return activationCodeMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<ActivationCodeBatch> pageBatchesByMerchant(String merchantId, int pageNum, int pageSize) {
        LambdaQueryWrapper<ActivationCodeBatch> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCodeBatch::getMerchantId, merchantId);
        wrapper.orderByDesc(ActivationCodeBatch::getCreatedTime);
        Page<ActivationCodeBatch> page = new Page<>(pageNum, pageSize);
        return activationCodeBatchMapper.selectPage(page, wrapper);
    }

    @Override
    public ActivationCode getByCode(String code) {
        return activationCodeMapper.selectOne(
            new LambdaQueryWrapper<ActivationCode>()
                .eq(ActivationCode::getCode, code)
        );
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void updateBatchStatus(List<String> ids, String status) {
        for (String id : ids) {
            ActivationCode code = activationCodeMapper.selectById(id);
            if (code != null) {
                code.setStatus(status);
                activationCodeMapper.updateById(code);
            }
        }
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void deleteById(String id) {
        ActivationCode code = activationCodeMapper.selectById(id);
        if (code == null) {
            throw new RuntimeException("激活码不存在");
        }
        if ("used".equals(code.getStatus())) {
            throw new RuntimeException("已使用的激活码无法删除");
        }

        Merchant merchant = merchantMapper.selectById(code.getMerchantId());
        if (merchant == null) {
            throw new RuntimeException("激活码关联的商户不存在");
        }

        int beforeTotalAmount = merchant.getTotalAmount() != null ? merchant.getTotalAmount() : 0;
        int beforeVipLevel = merchant.getVipLevel() != null ? merchant.getVipLevel() : 0;
        int discountPrice = code.getDiscountPrice() != null ? code.getDiscountPrice() : 0;
        int afterTotalAmount = Math.max(0, beforeTotalAmount - discountPrice);
        int afterVipLevel = vipLevelService.calculateVipLevel(afterTotalAmount);

        merchant.setTotalAmount(afterTotalAmount);
        merchant.setVipLevel(afterVipLevel);
        merchantMapper.updateById(merchant);

        activationCodeMapper.deleteById(id);
        log.info("删除激活码 - id: {}, code: {}, merchantId: {}, subscriptionType: {}, discountPrice: {}, totalAmount: {} -> {}, vipLevel: {} -> {}",
                id, code.getCode(), code.getMerchantId(), code.getSubscriptionType(), discountPrice,
                beforeTotalAmount, afterTotalAmount, beforeVipLevel, afterVipLevel);
    }

    private String generateUniqueCode() {
        return UUID.randomUUID().toString().replace("-", "").substring(0, 12).toUpperCase();
    }
}
