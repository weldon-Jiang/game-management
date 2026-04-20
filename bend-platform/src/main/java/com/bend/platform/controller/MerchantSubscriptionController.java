package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.VipConfig;
import com.bend.platform.repository.ActivationCodeMapper;
import com.bend.platform.repository.MerchantMapper;
import com.bend.platform.repository.VipConfigMapper;
import com.bend.platform.service.MerchantSubscriptionService;
import com.bend.platform.service.VipConfigService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.util.CollectionUtils;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.stream.Collectors;

/**
 * 商户订阅控制器
 *
 * 功能说明：
 * - 管理商户的VIP订阅状态
 * - 提供激活码激活功能
 *
 * 主要功能：
 * - 激活码激活VIP
 * - 获取订阅状态
 * - 获取可用的VIP配置列表
 * - 获取已激活的VIP列表
 */
@RestController
@RequestMapping("/api/merchant-subscription")
@RequiredArgsConstructor
public class MerchantSubscriptionController {

    private final MerchantSubscriptionService subscriptionService;
    private final MerchantMapper merchantMapper;
    private final ActivationCodeMapper activationCodeMapper;
    private final VipConfigMapper vipConfigMapper;
    private final VipConfigService vipConfigService;

    /**
     * 使用激活码激活VIP
     *
     * @param code 激活码
     * @return 操作结果
     */
    @PostMapping("/activate")
    public ApiResponse<Void> activate(@RequestParam String code) {
        String merchantId = UserContext.getMerchantId();
        String userId = UserContext.getUserId();
        subscriptionService.activateWithCode(merchantId, code, userId);
        return ApiResponse.success("激活成功", null);
    }

    /**
     * 获取商户订阅状态
     * 平台管理员返回特殊状态
     *
     * @return 订阅状态信息
     */
    @GetMapping("/status")
    public ApiResponse<Map<String, Object>> getStatus() {
        String merchantId = UserContext.getMerchantId();
        String role = UserContext.getRole();

        if (UserContext.isPlatformAdmin()) {
            Map<String, Object> adminStatus = new HashMap<>();
            adminStatus.put("status", "active");
            adminStatus.put("vipType", "platform_admin");
            adminStatus.put("expireTime", null);
            adminStatus.put("isAdmin", true);
            return ApiResponse.success(adminStatus);
        }

        Merchant merchant = merchantMapper.selectById(merchantId);
        if (merchant == null) {
            return ApiResponse.error(404, "商户不存在");
        }

        Map<String, Object> status = new HashMap<>();
        String currentStatus = "inactive";
        if ("active".equals(merchant.getStatus()) &&
            merchant.getExpireTime() != null &&
            merchant.getExpireTime().isAfter(LocalDateTime.now())) {
            currentStatus = "active";
        } else if (merchant.getExpireTime() != null &&
                   merchant.getExpireTime().isBefore(LocalDateTime.now())) {
            currentStatus = "expired";
        }
        status.put("status", currentStatus);
        status.put("expireTime", merchant.getExpireTime());
        status.put("merchantName", merchant.getName());

        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCode::getMerchantId, merchantId)
               .eq(ActivationCode::getStatus, "used")
               .orderByDesc(ActivationCode::getUsedAt)
               .last("LIMIT 1");
        ActivationCode lastUsedCode = activationCodeMapper.selectOne(wrapper);
        if (lastUsedCode != null) {
            if (lastUsedCode.getVipConfigId() != null) {
                VipConfig vipConfig = vipConfigMapper.selectById(lastUsedCode.getVipConfigId());
                if (vipConfig != null) {
                    status.put("vipType", vipConfig.getVipType());
                    status.put("vipName", vipConfig.getVipName());
                    status.put("durationDays", vipConfig.getDurationDays());
                }
            } else {
                status.put("vipType", lastUsedCode.getVipType());
            }
            status.put("lastActivatedAt", lastUsedCode.getUsedAt());
            status.put("lastUsedCode", lastUsedCode.getCode());
        }

        status.put("isAdmin", false);
        return ApiResponse.success(status);
    }

    /**
     * 获取可用的VIP配置列表
     *
     * @return VIP配置列表
     */
    @GetMapping("/vip-configs")
    public ApiResponse<List<VipConfig>> getAvailableVipConfigs() {
        List<VipConfig> configs = vipConfigService.findAllActive();
        return ApiResponse.success(configs);
    }

    /**
     * 获取已激活的VIP列表
     * 只返回未过期的VIP
     *
     * @return 已激活的VIP列表
     */
    @GetMapping("/activated")
    public ApiResponse<List<Map<String, Object>>> getActivatedVipList() {
        String merchantId = UserContext.getMerchantId();
        String role = UserContext.getRole();

        if (UserContext.isPlatformAdmin()) {
            return ApiResponse.success(new ArrayList<>());
        }

        LambdaQueryWrapper<ActivationCode> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(ActivationCode::getMerchantId, merchantId)
               .eq(ActivationCode::getStatus, "used")
               .gt(ActivationCode::getExpireTime, LocalDateTime.now())
               .orderByAsc(ActivationCode::getUsedAt);
        List<ActivationCode> codes = activationCodeMapper.selectList(wrapper);

        List<String> vipConfigIds = codes.stream()
                .map(ActivationCode::getVipConfigId)
                .filter(StringUtils::hasText)
                .distinct()
                .collect(Collectors.toList());

        Map<String, VipConfig> vipConfigMap = new HashMap<>();
        if (!CollectionUtils.isEmpty(vipConfigIds)) {
            LambdaQueryWrapper<VipConfig> vipWrapper = new LambdaQueryWrapper<>();
            vipWrapper.in(VipConfig::getId, vipConfigIds);
            vipConfigMapper.selectList(vipWrapper).forEach(v -> vipConfigMap.put(v.getId(), v));
        }

        List<Map<String, Object>> result = new ArrayList<>();
        for (ActivationCode code : codes) {
            Map<String, Object> item = new HashMap<>();
            item.put("code", code.getCode());
            item.put("usedAt", code.getUsedAt());
            item.put("expireTime", code.getExpireTime());
            item.put("usedBy", code.getUsedBy());

            if (code.getVipConfigId() != null && vipConfigMap.containsKey(code.getVipConfigId())) {
                VipConfig vipConfig = vipConfigMap.get(code.getVipConfigId());
                item.put("vipName", vipConfig.getVipName());
                item.put("vipType", vipConfig.getVipType());
                item.put("vipTypeText", getVipTypeText(vipConfig.getVipType()));
                item.put("durationDays", vipConfig.getDurationDays());
                item.put("price", vipConfig.getPrice());
            } else {
                item.put("vipType", code.getVipType());
                item.put("vipTypeText", getVipTypeText(code.getVipType()));
            }
            result.add(item);
        }

        return ApiResponse.success(result);
    }

    /**
     * 获取VIP类型的中文描述
     *
     * @param vipType VIP类型
     * @return 中文描述
     */
    private String getVipTypeText(String vipType) {
        if (vipType == null) return null;
        switch (vipType) {
            case "monthly": return "月卡";
            case "quarterly": return "季卡";
            case "yearly": return "年卡";
            default: return vipType;
        }
    }
}