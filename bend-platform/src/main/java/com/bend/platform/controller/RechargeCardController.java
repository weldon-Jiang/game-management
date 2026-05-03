package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.RechargeCard;
import com.bend.platform.entity.RechargeCardBatch;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.RechargeCardService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.math.BigDecimal;
import java.util.List;
import java.util.UUID;

/**
 * 充值卡管理控制器
 */
@RestController
@RequestMapping("/api/recharge-cards")
@RequiredArgsConstructor
public class RechargeCardController {

    private final RechargeCardService rechargeCardService;

    @PostMapping("/batches")
    public ApiResponse<RechargeCardBatch> createBatch(
            @RequestParam String name,
            @RequestParam(defaultValue = "platform_card") String cardType,
            @RequestParam(required = false) String targetMerchantId,
            @RequestParam int count,
            @RequestParam int denomination,
            @RequestParam(defaultValue = "0") int bonusPoints,
            @RequestParam(required = false) BigDecimal price,
            @RequestParam(defaultValue = "365") int validDays) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        RechargeCardBatch batch = rechargeCardService.createBatch(
                name, cardType, targetMerchantId, count, denomination, bonusPoints,
                price != null ? price.intValue() : denomination, validDays);
        return ApiResponse.success("批次创建成功", batch);
    }

    @GetMapping("/batches")
    public ApiResponse<IPage<RechargeCardBatch>> listBatches(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize) {
        IPage<RechargeCardBatch> page = rechargeCardService.pageBatches(pageNum, pageSize);
        return ApiResponse.success(page);
    }

    @GetMapping
    public ApiResponse<IPage<RechargeCard>> listCards(
            @RequestParam(required = false) String batchId,
            @RequestParam(required = false) String status,
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "20") int pageSize) {
        IPage<RechargeCard> page = rechargeCardService.pageCards(batchId, status, pageNum, pageSize);
        return ApiResponse.success(page);
    }

    @GetMapping("/{cardNo}")
    public ApiResponse<RechargeCard> getCard(@PathVariable String cardNo) {
        RechargeCard card = rechargeCardService.getByCardNo(cardNo);
        if (card == null) {
            throw new BusinessException(ResultCode.RechargeCard.NOT_FOUND);
        }
        return ApiResponse.success(card);
    }

    @GetMapping("/batches/{batchId}/export")
    public ApiResponse<List<RechargeCard>> exportCards(@PathVariable String batchId) {
        if (!UserContext.isPlatformAdmin()) {
            throw new BusinessException(ResultCode.Auth.PERMISSION_DENIED);
        }
        List<RechargeCard> cards = rechargeCardService.exportCards(batchId);
        return ApiResponse.success(cards);
    }

    @PostMapping("/use")
    public ApiResponse<Void> useCard(
            @RequestParam String cardNo,
            @RequestParam String cardPwd) {
        rechargeCardService.useCard(cardNo, cardPwd);
        return ApiResponse.success("充值成功", null);
    }
}
