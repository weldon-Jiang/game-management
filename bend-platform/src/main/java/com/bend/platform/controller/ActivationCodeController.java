package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.ActivationCodeBatch;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.repository.ActivationCodeBatchMapper;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.ActivationCodeService;
import com.bend.platform.service.impl.VipLevelService;
import com.bend.platform.util.UserContext;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.*;

/**
 * 激活码管理控制器
 *
 * 功能说明：
 * - 生成激活码（平台管理员可为商户生成）
 * - 查看激活码列表
 * - 预览激活码信息
 * - 获取VIP价格配置
 * - 删除未使用的激活码
 *
 * 订阅类型：
 * - window_account: 流媒体账号包月
 * - account: 游戏账号包月
 * - host: Xbox主机包月
 * - full: 全功能包月
 * - points: 点数充值
 *
 * 价格说明：
 * - 根据商户VIP等级获取对应的原价/折扣价
 * - 生成激活码时记录价格，激活时不再重新计算
 */
@Slf4j
@RestController
@RequestMapping("/api/activation-codes")
@RequiredArgsConstructor
public class ActivationCodeController {

    private final ActivationCodeMapper activationCodeMapper;
    private final ActivationCodeBatchMapper activationCodeBatchMapper;
    private final MerchantMapper merchantMapper;
    private final MerchantGroupMapper merchantGroupMapper;
    private final ActivationCodeService activationCodeService;
    private final VipLevelService vipLevelService;
    private final ObjectMapper objectMapper;

    /**
     * 分页查询激活码列表
     *
     * @param pageNum  页码，默认1
     * @param pageSize 每页数量，默认10
     * @param status   状态筛选，可选：unused/used/expired
     * @return 激活码分页列表
     *
     * 说明：
     * - 平台管理员返回所有激活码
     * - 普通商户只返回自己商户的激活码
     */
    @GetMapping("/list")
    public ApiResponse<IPage<ActivationCode>> listCodes(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize,
            @RequestParam(required = false) String status) {
        String merchantId = UserContext.getMerchantId();
        IPage<ActivationCode> pageResult;
        if (UserContext.isPlatformAdmin()) {
            pageResult = activationCodeService.pageAll(pageNum, pageSize, status);
        } else {
            pageResult = activationCodeService.pageByMerchant(merchantId, pageNum, pageSize, status);
        }
        return ApiResponse.success(pageResult);
    }

    /**
     * 预览激活码信息
     *
     * @param code 激活码
     * @return 激活码详细信息（不含敏感信息）
     *
     * 说明：
     * - 只能预览属于当前商户的激活码
     * - 返回激活码的基本信息和价格
     */
    @GetMapping("/preview")
    public ApiResponse<Map<String, Object>> previewCode(@RequestParam String code) {
        String merchantId = UserContext.getMerchantId();

        ActivationCode activationCode = activationCodeMapper.selectOne(
            new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<ActivationCode>()
                .eq(ActivationCode::getCode, code)
        );

        if (activationCode == null) {
            return ApiResponse.error(404, "激活码不存在");
        }

        if (!merchantId.equals(activationCode.getMerchantId())) {
            return ApiResponse.error(403, "激活码不属于当前商户");
        }

        Map<String, Object> preview = new HashMap<>();
        preview.put("code", activationCode.getCode());
        preview.put("subscriptionType", activationCode.getSubscriptionType());
        preview.put("boundResourceType", activationCode.getBoundResourceType());
        preview.put("boundResourceNames", activationCode.getBoundResourceNames());
        preview.put("durationDays", activationCode.getDurationDays());
        preview.put("originalPrice", activationCode.getOriginalPrice());
        preview.put("discountPrice", activationCode.getDiscountPrice());
        preview.put("status", activationCode.getStatus());

        return ApiResponse.success(preview);
    }

    /**
     * 生成激活码
     *
     * @param request 请求参数
     *               - merchantId: 商户ID（平台管理员可选，普通商户不传）
     *               - subscriptionType: 订阅类型
     *               - boundResourceIds: 绑定资源ID列表
     *               - boundResourceNames: 绑定资源名称列表
     *               - pointsAmount: 点数数量（仅points类型）
     * @return 生成的激活码信息
     *
     * 说明：
     * - 根据商户VIP等级计算价格
     * - 生成激活码时累加商户累计消费，更新VIP等级
     * - 激活码生成时不设置生效时间，激活时才计算
     */
    @SuppressWarnings("unchecked")
    @PostMapping
    public ApiResponse<Map<String, Object>> createCode(@RequestBody Map<String, Object> request) {
        String merchantId = UserContext.getMerchantId();

        String subscriptionType = (String) request.get("subscriptionType");
        List<String> boundResourceIds = (List<String>) request.get("boundResourceIds");
        List<String> boundResourceNames = (List<String>) request.get("boundResourceNames");
        Integer pointsAmount = request.get("pointsAmount") != null
            ? ((Number) request.get("pointsAmount")).intValue() : null;

        if (request.get("merchantId") != null && !((String) request.get("merchantId")).isEmpty()) {
            merchantId = (String) request.get("merchantId");
        }

        Merchant merchant = merchantMapper.selectById(merchantId);
        int vipLevel = merchant != null && merchant.getVipLevel() != null ? merchant.getVipLevel() : 0;

        MerchantGroup group = merchantGroupMapper.selectOne(
            new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<MerchantGroup>()
                .eq(MerchantGroup::getVipLevel, vipLevel)
                .eq(MerchantGroup::getStatus, "active")
                .last("LIMIT 1")
        );

        int originalPrice = 0;
        int discountPrice = 0;
        String boundResourceType = null;

        switch (subscriptionType) {
            case "window_account":
                boundResourceType = "streaming_account";
                originalPrice = group != null ? group.getWindowOriginalPrice() : 10000;
                discountPrice = group != null ? group.getWindowDiscountPrice() : 10000;
                break;
            case "account":
                boundResourceType = "game_account";
                originalPrice = group != null ? group.getAccountOriginalPrice() : 5000;
                discountPrice = group != null ? group.getAccountDiscountPrice() : 5000;
                break;
            case "host":
                boundResourceType = "xbox_host";
                originalPrice = group != null ? group.getHostOriginalPrice() : 20000;
                discountPrice = group != null ? group.getHostDiscountPrice() : 20000;
                break;
            case "full":
                boundResourceType = "all";
                originalPrice = group != null ? group.getFullOriginalPrice() : 30000;
                discountPrice = group != null ? group.getFullDiscountPrice() : 30000;
                break;
            case "points":
                boundResourceType = null;
                int unitOriginalPrice = group != null ? group.getPointsOriginalPrice() : 500;
                int unitDiscountPrice = group != null ? group.getPointsDiscountPrice() : 500;
                if (pointsAmount != null && pointsAmount > 0) {
                    originalPrice = unitOriginalPrice * pointsAmount;
                    discountPrice = unitDiscountPrice * pointsAmount;
                } else {
                    originalPrice = unitOriginalPrice;
                    discountPrice = unitDiscountPrice;
                }
                break;
            default:
                return ApiResponse.error(400, "不支持的订阅类型");
        }

        String boundResourceIdsJson = null;
        String boundResourceNamesJson = null;
        if (boundResourceIds != null && !boundResourceIds.isEmpty()) {
            try {
                boundResourceIdsJson = objectMapper.writeValueAsString(boundResourceIds);
                boundResourceNamesJson = objectMapper.writeValueAsString(boundResourceNames != null ? boundResourceNames : boundResourceIds);
            } catch (JsonProcessingException e) {
                log.error("序列化绑定资源失败", e);
            }
        }

        ActivationCode activationCode = activationCodeService.generateCode(
            merchantId,
            subscriptionType,
            boundResourceType,
            boundResourceIdsJson,
            boundResourceNamesJson,
            30,
            originalPrice,
            discountPrice,
            null
        );

        if (originalPrice > 0) {
            int newTotalAmount = (merchant.getTotalAmount() != null ? merchant.getTotalAmount() : 0) + originalPrice;
            merchant.setTotalAmount(newTotalAmount);

            int newVipLevel = vipLevelService.calculateVipLevel(newTotalAmount);
            if (newVipLevel != merchant.getVipLevel()) {
                merchant.setVipLevel(newVipLevel);
            }
            merchantMapper.updateById(merchant);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("id", activationCode.getId());
        result.put("code", activationCode.getCode());
        result.put("subscriptionType", activationCode.getSubscriptionType());
        result.put("originalPrice", activationCode.getOriginalPrice());
        result.put("discountPrice", activationCode.getDiscountPrice());
        result.put("durationDays", activationCode.getDurationDays());

        return ApiResponse.success(result);
    }

    /**
     * 查询激活码批次列表
     *
     * @param pageNum  页码
     * @param pageSize 每页数量
     * @return 批次分页列表
     */
    @GetMapping("/batch/list")
    public ApiResponse<IPage<ActivationCodeBatch>> listBatches(
            @RequestParam(defaultValue = "1") int pageNum,
            @RequestParam(defaultValue = "10") int pageSize) {
        String merchantId = UserContext.getMerchantId();
        var pageResult = activationCodeService.pageBatchesByMerchant(merchantId, pageNum, pageSize);
        return ApiResponse.success(pageResult);
    }

    /**
     * 获取商户VIP价格配置
     *
     * @param merchantId 商户ID（可选，不传则取当前商户）
     * @return 各订阅类型的原价和折扣价
     *
     * 说明：
     * - 根据商户的VIP等级获取对应的价格配置
     * - 返回流媒体账号、游戏账号、Xbox主机、全功能包月及点数的原价和折后价
     */
    @GetMapping("/prices")
    public ApiResponse<Map<String, Object>> getPrices(
            @RequestParam(required = false) String merchantId) {
        String currentMerchantId = merchantId != null ? merchantId : UserContext.getMerchantId();
        Merchant merchant = merchantMapper.selectById(currentMerchantId);
        int vipLevel = merchant != null && merchant.getVipLevel() != null ? merchant.getVipLevel() : 0;

        MerchantGroup group = merchantGroupMapper.selectOne(
            new com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper<MerchantGroup>()
                .eq(MerchantGroup::getVipLevel, vipLevel)
                .eq(MerchantGroup::getStatus, "active")
                .last("LIMIT 1")
        );

        Map<String, Object> prices = new HashMap<>();
        if (group != null) {
            prices.put("windowOriginalPrice", group.getWindowOriginalPrice());
            prices.put("windowDiscountPrice", group.getWindowDiscountPrice());
            prices.put("accountOriginalPrice", group.getAccountOriginalPrice());
            prices.put("accountDiscountPrice", group.getAccountDiscountPrice());
            prices.put("hostOriginalPrice", group.getHostOriginalPrice());
            prices.put("hostDiscountPrice", group.getHostDiscountPrice());
            prices.put("fullOriginalPrice", group.getFullOriginalPrice());
            prices.put("fullDiscountPrice", group.getFullDiscountPrice());
            prices.put("pointsOriginalPrice", group.getPointsOriginalPrice());
            prices.put("pointsDiscountPrice", group.getPointsDiscountPrice());
        } else {
            prices.put("windowOriginalPrice", 10000);
            prices.put("windowDiscountPrice", 10000);
            prices.put("accountOriginalPrice", 5000);
            prices.put("accountDiscountPrice", 5000);
            prices.put("hostOriginalPrice", 20000);
            prices.put("hostDiscountPrice", 20000);
            prices.put("fullOriginalPrice", 30000);
            prices.put("fullDiscountPrice", 30000);
            prices.put("pointsOriginalPrice", 500);
            prices.put("pointsDiscountPrice", 500);
        }

        return ApiResponse.success(prices);
    }

    /**
     * 删除激活码
     *
     * @param id 激活码ID
     * @return 操作结果
     *
     * 说明：
     * - 只能删除未使用的激活码
     * - 已使用或已过期的激活码无法删除
     */
    @DeleteMapping("/{id}")
    public ApiResponse<Void> deleteCode(@PathVariable String id) {
        activationCodeService.deleteById(id);
        return ApiResponse.success("激活码删除成功", null);
    }
}
