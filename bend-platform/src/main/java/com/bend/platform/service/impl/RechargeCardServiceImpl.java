package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.core.metadata.IPage;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.bend.platform.entity.MerchantBalance;
import com.bend.platform.entity.RechargeCard;
import com.bend.platform.entity.RechargeCardBatch;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.RechargeCardMapper;
import com.bend.platform.repository.RechargeCardBatchMapper;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.RechargeCardService;
import com.bend.platform.util.AesUtil;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class RechargeCardServiceImpl implements RechargeCardService {

    private final RechargeCardMapper rechargeCardMapper;
    private final RechargeCardBatchMapper rechargeCardBatchMapper;
    private final MerchantBalanceService balanceService;
    private final AesUtil aesUtil;

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void useCard(String cardNo, String cardPwd) {
        RechargeCard card = rechargeCardMapper.selectOne(
                new LambdaQueryWrapper<RechargeCard>().eq(RechargeCard::getCardNo, cardNo));

        if (card == null) {
            throw new BusinessException(ResultCode.RechargeCard.NOT_FOUND, "充值卡不存在");
        }

        if (!"unused".equals(card.getStatus())) {
            if ("used".equals(card.getStatus())) {
                throw new BusinessException(ResultCode.RechargeCard.ALREADY_USED, "充值卡已被使用");
            }
            throw new BusinessException(ResultCode.RechargeCard.INVALID, "充值卡状态无效");
        }

        if (card.getExpireTime() != null && card.getExpireTime().isBefore(LocalDateTime.now())) {
            throw new BusinessException(ResultCode.RechargeCard.EXPIRED, "充值卡已过期");
        }

        String decryptedPwd = aesUtil.decrypt(card.getCardPwd());
        if (!decryptedPwd.equals(cardPwd)) {
            throw new BusinessException(ResultCode.RechargeCard.PASSWORD_ERROR, "卡密错误");
        }

        String merchantId = UserContext.getMerchantId();
        String userId = UserContext.getUserId();

        card.setStatus("used");
        card.setUsedByMerchantId(merchantId);
        card.setUsedByUserId(userId);
        card.setUsedTime(LocalDateTime.now());
        rechargeCardMapper.updateById(card);

        balanceService.addPoints(merchantId, card.getPointsToGrant(), userId, "card",
                card.getId(), "使用充值卡: " + cardNo);

        RechargeCardBatch batch = rechargeCardBatchMapper.selectById(card.getBatchId());
        if (batch != null) {
            batch.setUsedCount(batch.getUsedCount() + 1);
            rechargeCardBatchMapper.updateById(batch);
        }

        log.info("使用充值卡成功 - cardNo: {}, merchantId: {}, points: {}",
                cardNo, merchantId, card.getPointsToGrant());
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public RechargeCardBatch createBatch(String name, String cardType, String targetMerchantId,
                                        int count, int denomination, int bonusPoints, int price, int validDays) {
        RechargeCardBatch batch = new RechargeCardBatch();
        batch.setId(UUID.randomUUID().toString());
        batch.setName(name);
        batch.setCardType(cardType);
        batch.setTargetMerchantId(targetMerchantId);
        batch.setTotalCount(count);
        batch.setDenomination(denomination);
        batch.setBonusPoints(bonusPoints);
        batch.setPointsToGrant(denomination + bonusPoints);
        batch.setPrice(java.math.BigDecimal.valueOf(price));
        batch.setValidDays(validDays);
        batch.setStatus("generating");
        batch.setGeneratedCount(0);
        batch.setSoldCount(0);
        batch.setUsedCount(0);
        batch.setCreatedBy(UserContext.getUserId());
        rechargeCardBatchMapper.insert(batch);

        log.info("创建充值卡批次 - batchId: {}, count: {}", batch.getId(), count);
        return batch;
    }

    @Override
    public IPage<RechargeCardBatch> pageBatches(int pageNum, int pageSize) {
        Page<RechargeCardBatch> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<RechargeCardBatch> wrapper = new LambdaQueryWrapper<>();
        wrapper.orderByDesc(RechargeCardBatch::getCreatedTime);
        return rechargeCardBatchMapper.selectPage(page, wrapper);
    }

    @Override
    public IPage<RechargeCard> pageCards(String batchId, String status, int pageNum, int pageSize) {
        Page<RechargeCard> page = new Page<>(pageNum, pageSize);
        LambdaQueryWrapper<RechargeCard> wrapper = new LambdaQueryWrapper<>();
        if (batchId != null && !batchId.isEmpty()) {
            wrapper.eq(RechargeCard::getBatchId, batchId);
        }
        if (status != null && !status.isEmpty()) {
            wrapper.eq(RechargeCard::getStatus, status);
        }
        wrapper.orderByDesc(RechargeCard::getCreatedTime);
        return rechargeCardMapper.selectPage(page, wrapper);
    }

    @Override
    public RechargeCard getByCardNo(String cardNo) {
        return rechargeCardMapper.selectOne(
                new LambdaQueryWrapper<RechargeCard>().eq(RechargeCard::getCardNo, cardNo));
    }

    @Override
    public List<RechargeCard> getByBatchId(String batchId) {
        return rechargeCardMapper.selectList(
                new LambdaQueryWrapper<RechargeCard>().eq(RechargeCard::getBatchId, batchId));
    }

    @Override
    @Transactional(rollbackFor = Exception.class)
    public void activateCard(String cardNo, String merchantId) {
        RechargeCard card = rechargeCardMapper.selectOne(
                new LambdaQueryWrapper<RechargeCard>().eq(RechargeCard::getCardNo, cardNo));

        if (card == null) {
            throw new BusinessException(ResultCode.RechargeCard.NOT_FOUND);
        }

        if (!"unused".equals(card.getStatus())) {
            throw new BusinessException(ResultCode.RechargeCard.INVALID, "卡密状态无效");
        }

        card.setStatus("sold");
        card.setSoldToMerchantId(merchantId);
        card.setSoldByUserId(UserContext.getUserId());
        card.setSoldTime(LocalDateTime.now());
        rechargeCardMapper.updateById(card);

        RechargeCardBatch batch = rechargeCardBatchMapper.selectById(card.getBatchId());
        if (batch != null) {
            batch.setSoldCount(batch.getSoldCount() + 1);
            rechargeCardBatchMapper.updateById(batch);
        }

        log.info("激活卡密 - cardNo: {}, merchantId: {}", cardNo, merchantId);
    }

    @Override
    public List<RechargeCard> exportCards(String batchId) {
        return rechargeCardMapper.selectList(
                new LambdaQueryWrapper<RechargeCard>()
                        .eq(RechargeCard::getBatchId, batchId)
                        .orderByAsc(RechargeCard::getCardNo));
    }
}
