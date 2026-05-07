package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.ActivationCodeBatch;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantBalance;
import com.bend.platform.entity.MerchantGroup;
import com.bend.platform.entity.Subscription;
import com.bend.platform.repository.ActivationCodeBatchMapper;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.repository.MerchantGroupMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.SubscriptionService;
import com.bend.platform.service.impl.VipLevelService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 商户订阅控制器
 */
@RestController
@RequestMapping("/api/merchant-subscription")
@RequiredArgsConstructor
public class MerchantSubscriptionController {

    private final MerchantMapper merchantMapper;
    private final ActivationCodeMapper activationCodeMapper;
    private final ActivationCodeBatchMapper activationCodeBatchMapper;
    private final MerchantGroupMapper merchantGroupMapper;
    private final MerchantBalanceService balanceService;
    private final SubscriptionService subscriptionService;
    private final VipLevelService vipLevelService;

    @GetMapping("/status")
    public ApiResponse<Map<String, Object>> getStatus() {
        String merchantId = UserContext.getMerchantId();

        if (UserContext.isPlatformAdmin()) {
            Map<String, Object> adminStatus = new HashMap<>();
            adminStatus.put("status", "active");
            adminStatus.put("isAdmin", true);
            return ApiResponse.success(adminStatus);
        }

        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            return ApiResponse.error(404, "商户不存在");
        }

        Map<String, Object> status = new HashMap<>();
        // 点数制：只要商户存在且状态正常就是 active
        String currentStatus = "active".equals(merchant.getStatus()) ? "active" : "inactive";
        status.put("status", currentStatus);
        status.put("merchantName", merchant.getName());
        status.put("totalPoints", merchant.getTotalPoints());
        status.put("vipLevel", merchant.getVipLevel());
        status.put("isAdmin", false);
        return ApiResponse.success(status);
    }

    @GetMapping("/activated")
    public ApiResponse<Map<String, Object>> getActivatedInfo() {
        String merchantId = UserContext.getMerchantId();
        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            return ApiResponse.error(404, "商户不存在");
        }

        Map<String, Object> info = new HashMap<>();
        info.put("totalPoints", merchant.getTotalPoints());
        info.put("vipLevel", merchant.getVipLevel());
        info.put("status", merchant.getStatus());
        return ApiResponse.success(info);
    }

    @GetMapping("/preview")
    public ApiResponse<Map<String, Object>> previewActivation(@RequestParam String code) {
        String merchantId = UserContext.getMerchantId();

        ActivationCode activationCode = activationCodeMapper.selectOne(
            new LambdaQueryWrapper<ActivationCode>()
                .eq(ActivationCode::getCode, code)
        );

        if (activationCode == null) {
            return ApiResponse.error(404, "激活码不存在");
        }

        ActivationCodeBatch batch = activationCodeBatchMapper.selectById(activationCode.getBatchId());

        Map<String, Object> preview = new HashMap<>();
        String subscriptionType = activationCode.getSubscriptionType();
        if (subscriptionType == null) {
            subscriptionType = "points";
        }
        preview.put("subscriptionType", subscriptionType);
        // 兼容 points 和 pointsAmount 两个字段
        Integer pointsValue = 0;
        if (batch != null) {
            pointsValue = batch.getPointsAmount() != null ? batch.getPointsAmount() : batch.getPoints();
            if (pointsValue == null) {
                pointsValue = 0;
            }
        }
        preview.put("points", pointsValue);
        preview.put("targetId", activationCode.getTargetId());
        preview.put("targetName", activationCode.getTargetName());
        preview.put("durationDays", batch != null && batch.getDurationDays() != null ? batch.getDurationDays() : 0);
        preview.put("status", activationCode.getStatus());
        preview.put("expireTime", activationCode.getExpireTime());

        // 检查商户是否有活跃订阅（用于前端显示警告）
        if (!"points".equals(subscriptionType)) {
            List<Subscription> activeSubscriptions = subscriptionService.getActiveSubscriptions(merchantId);
            if (!activeSubscriptions.isEmpty()) {
                Subscription activeSub = activeSubscriptions.get(0);
                preview.put("hasActiveSubscription", true);
                preview.put("activeSubscriptionConflict", true);
                preview.put("activeSubscriptionType", activeSub.getType());
                preview.put("activeSubscriptionTypeName", getTypeName(activeSub.getType()));
                preview.put("activeSubscriptionTargetName", activeSub.getTargetName());
                preview.put("conflictMessage", "您已有" + getTypeName(activeSub.getType()) + "「" + activeSub.getTargetName() + "」的订阅在有效期内，无法激活此激活码");
            } else {
                preview.put("hasActiveSubscription", false);
                preview.put("activeSubscriptionConflict", false);
            }
        } else {
            preview.put("hasActiveSubscription", false);
            preview.put("activeSubscriptionConflict", false);
        }

        // VIP升级预览信息
        Merchant merchant = merchantMapper.selectById(merchantId);
        int currentVipLevel = merchant != null && merchant.getVipLevel() != null ? merchant.getVipLevel() : 0;
        MerchantBalance balance = balanceService.getByMerchantId(merchantId);
        int currentTotalPoints = balance != null && balance.getTotalRecharged() != null ? balance.getTotalRecharged() : 0;
        int newTotalPoints = currentTotalPoints + pointsValue;
        int newVipLevel = vipLevelService.calculateVipLevel(newTotalPoints);

        preview.put("currentVipLevel", currentVipLevel);
        preview.put("currentTotalPoints", currentTotalPoints);
        preview.put("newTotalPointsAfterActivation", newTotalPoints);
        preview.put("newVipLevelAfterActivation", newVipLevel);
        if (newVipLevel > currentVipLevel) {
            preview.put("willUpgradeVip", true);
            preview.put("vipUpgradeMessage", "激活后将升级到 VIP" + newVipLevel);
        } else {
            preview.put("willUpgradeVip", false);
            preview.put("vipUpgradeMessage", null);
        }

        // 计算距离下一级还需多少点
        LambdaQueryWrapper<MerchantGroup> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(MerchantGroup::getStatus, "active")
                .gt(MerchantGroup::getVipLevel, currentVipLevel)
                .orderByAsc(MerchantGroup::getPointsThreshold)
                .last("LIMIT 1");
        MerchantGroup nextGroup = merchantGroupMapper.selectOne(wrapper);
        if (nextGroup != null && nextGroup.getPointsThreshold() != null) {
            preview.put("pointsToNextVipLevel", nextGroup.getPointsThreshold() - currentTotalPoints);
            preview.put("nextVipLevelName", "VIP" + nextGroup.getVipLevel());
        } else {
            preview.put("pointsToNextVipLevel", 0);
            preview.put("nextVipLevelName", null);
        }

        return ApiResponse.success(preview);
    }

    @PostMapping("/activate")
    public ApiResponse<Map<String, Object>> activate(@RequestParam String code) {
        String merchantId = UserContext.getMerchantId();
        String userId = UserContext.getUserId();

        ActivationCode activationCode = activationCodeMapper.selectOne(
            new LambdaQueryWrapper<ActivationCode>()
                .eq(ActivationCode::getCode, code)
        );

        if (activationCode == null) {
            return ApiResponse.error(404, "激活码不存在");
        }

        if (!"unused".equals(activationCode.getStatus())) {
            return ApiResponse.error(400, "激活码已被使用");
        }

        if (activationCode.getExpireTime() != null &&
            activationCode.getExpireTime().isBefore(LocalDateTime.now())) {
            return ApiResponse.error(400, "激活码已过期");
        }

        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            return ApiResponse.error(404, "商户不存在");
        }

        ActivationCodeBatch batch = activationCodeBatchMapper.selectById(activationCode.getBatchId());
        String subscriptionType = activationCode.getSubscriptionType();
        if (subscriptionType == null) {
            subscriptionType = "points";
        }

        Map<String, Object> result = new HashMap<>();
        int pointsAdded = 0;
        Object subscriptionResult = null;

        if ("points".equals(subscriptionType)) {
            // 点数模式：增加余额
            if (batch != null) {
                // 兼容 points 和 pointsAmount 两个字段
                Integer pointsValue = batch.getPointsAmount() != null ? batch.getPointsAmount() : batch.getPoints();
                if (pointsValue != null) {
                    pointsAdded = pointsValue;
                    balanceService.addPoints(merchantId, pointsAdded, userId, "activation_code", activationCode.getId(), "激活码充值");
                }
            }
            result.put("type", "points");
            result.put("pointsAdded", pointsAdded);
        } else {
            // 订阅模式：创建订阅记录（game_account -> account, window -> window, host -> host）
            String mappedType = mapSubscriptionType(subscriptionType);

            // 完全互斥检查：检查商户是否有任何活跃订阅
            List<Subscription> activeSubscriptions = subscriptionService.getActiveSubscriptions(merchantId);
            if (!activeSubscriptions.isEmpty()) {
                Subscription activeSub = activeSubscriptions.get(0);
                String activeTypeName = getTypeName(activeSub.getType());
                return ApiResponse.error(400, "您已有" + activeTypeName + "「" + activeSub.getTargetName() + "」的订阅在有效期内，请等待当前订阅到期或取消后再试");
            }

            if (batch != null) {
                int durationDays = batch.getDurationDays() != null ? batch.getDurationDays() : 30;

                // 创建订阅（激活码不扣点，因为是用激活码购买的）
                subscriptionResult = subscriptionService.createSubscriptionWithoutDeduction(
                        merchantId,
                        userId,
                        mappedType,
                        activationCode.getTargetId(),
                        activationCode.getTargetName(),
                        durationDays
                );

                // 将激活码点数价值计入VIP累计（用于VIP升级判定）
                Integer pointsValue = batch.getPointsAmount() != null ? batch.getPointsAmount() : batch.getPoints();
                if (pointsValue != null && pointsValue > 0) {
                    balanceService.recordActivationCodeValueForVipUpgrade(merchantId, pointsValue);
                }
            }
            result.put("type", subscriptionType);
            result.put("targetName", activationCode.getTargetName());
            result.put("durationDays", batch != null && batch.getDurationDays() != null ? batch.getDurationDays() : 0);
            result.put("subscription", subscriptionResult);
        }

        activationCode.setStatus("used");
        activationCode.setUsedBy(userId);
        activationCode.setUsedTime(LocalDateTime.now());
        activationCodeMapper.updateById(activationCode);

        // 重新从数据库获取最新的数据（包括VIP等级可能的变化）
        merchant = merchantMapper.selectById(merchantId);
        result.put("totalPoints", merchant.getTotalPoints());
        result.put("vipLevel", merchant.getVipLevel());
        return ApiResponse.success("激活成功", result);
    }
    
    /**
     * 映射激活码订阅类型到内部订阅类型
     */
    private String mapSubscriptionType(String type) {
        return switch (type) {
            case "game_account" -> "account";
            case "window" -> "window";
            case "host" -> "host";
            default -> type;
        };
    }
    
    /**
     * 获取订阅类型的中文名称
     */
    private String getTypeName(String type) {
        return switch (type) {
            case "host" -> "主机";
            case "window" -> "窗口";
            case "account" -> "游戏号";
            default -> type;
        };
    }

    @PostMapping("/batch")
    @Deprecated
    public ApiResponse<String> createBatch(@RequestBody Map<String, Object> request) {
        return ApiResponse.error(501, "该接口已废弃，请使用激活码功能");
    }
}
