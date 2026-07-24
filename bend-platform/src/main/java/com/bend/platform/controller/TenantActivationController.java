package com.bend.platform.controller;

import com.bend.platform.config.MasterModeCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.ActivationCode;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantLicense;
import com.bend.platform.entity.Subscription;
import com.bend.platform.repository.MerchantLicenseMapper;
import com.bend.platform.service.ActivationCodeService;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.SubscriptionService;
import com.bend.platform.util.LicenseSignUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.Map;

/**
 * 总控侧接收分控代理激活请求。
 *
 * <p>分控前端激活码 → 分控代理 → 本接口在总控库执行激活（创建 subscription 或充值点数）。
 * 逻辑与 {@link MerchantSubscriptionController#activate} 对齐，确保总控/分控激活结果一致。
 */
@Slf4j
@RestController
@RequestMapping("/api/tenant")
@RequiredArgsConstructor
@Conditional(MasterModeCondition.class)
public class TenantActivationController {

    private final ActivationCodeService activationCodeService;
    private final MerchantBalanceService balanceService;
    private final SubscriptionService subscriptionService;
    private final MerchantService merchantService;
    private final MerchantLicenseMapper licenseMapper;
    private final LicenseSignUtil signUtil;

    @PostMapping("/activate")
    public ApiResponse<Map<String, Object>> activate(
            @RequestHeader("X-License-Key") String licenseKey,
            @RequestHeader("X-License-Secret") String licenseSecret,
            @RequestBody Map<String, String> body) {

        String code = body.get("code");
        if (code == null || code.isEmpty()) return ApiResponse.error(400, "激活码不能为空");

        MerchantLicense lic = licenseMapper.selectByLicenseKey(licenseKey);
        if (lic == null) return ApiResponse.error(404, "License 不存在");
        if (!signUtil.verifySecret(licenseSecret, lic.getLicenseSecret()))
            return ApiResponse.error(403, "License 密钥错误");

        String mid = lic.getMerchantId();
        ActivationCode ac = activationCodeService.getByCode(code);
        if (ac == null) return ApiResponse.error(404, "激活码不存在");
        if (!mid.equals(ac.getMerchantId())) return ApiResponse.error(403, "激活码不属于当前商户");
        if (!"unused".equals(ac.getStatus())) return ApiResponse.error(400, "激活码已被使用");

        log.info("分控代理激活 - code: {}, merchant: {}, type: {}", code, mid, ac.getSubscriptionType());

        Map<String, Object> result = new HashMap<>();
        result.put("subscriptionType", ac.getSubscriptionType());

        if ("points".equals(ac.getSubscriptionType())) {
            // 点数类型：直接增加余额
            balanceService.addPoints(mid,
                    ac.getPointsAmount() != null ? ac.getPointsAmount() : 0,
                    mid, "activation_code", ac.getId(), "激活码充值点数");
            result.put("pointsAdded", ac.getPointsAmount());
            result.put("startTime", "立即生效");
            result.put("endTime", "永久有效");
        } else {
            // 包月类型：计算顺延时间，创建订阅记录（与 MerchantSubscriptionController.activate 逻辑一致）
            Subscription latest = subscriptionService.getLatestActiveNonPointsSubscription(mid);
            LocalDate calculatedStartTime;
            if (latest == null || latest.getEndTime().toLocalDate().isBefore(LocalDate.now())) {
                calculatedStartTime = LocalDate.now();
            } else {
                calculatedStartTime = latest.getEndTime().toLocalDate().plusDays(1);
            }
            int days = ac.getDurationDays() != null ? ac.getDurationDays() : 30;
            LocalDate calculatedEndTime = calculatedStartTime.plusDays(days - 1);

            LocalDateTime startDateTime = calculatedStartTime.atStartOfDay();
            LocalDateTime endDateTime = calculatedEndTime.atTime(23, 59, 59);

            subscriptionService.createSubscription(
                    mid, mid, ac.getId(),
                    ac.getSubscriptionType(),
                    ac.getBoundResourceType(),
                    ac.getBoundResourceIds(),
                    ac.getBoundResourceNames(),
                    startDateTime, endDateTime,
                    ac.getOriginalPrice(), ac.getDiscountPrice());

            ac.setStartTime(startDateTime);
            ac.setEndTime(endDateTime);
            result.put("startTime", startDateTime);
            result.put("endTime", endDateTime);
        }

        // 更新激活码状态
        ac.setStatus("used");
        ac.setUsedBy(mid);
        ac.setUsedTime(LocalDateTime.now());
        activationCodeService.updateActivationCode(ac);

        // 返回商户当前信息（VIP 等级等）
        Merchant merchant = merchantService.findById(mid);
        if (merchant != null) {
            result.put("totalAmount", merchant.getTotalAmount());
            result.put("vipLevel", merchant.getVipLevel());
        }

        log.info("分控代理激活成功 - code: {}, merchant: {}, type: {}", code, mid, ac.getSubscriptionType());
        return ApiResponse.success("激活成功", result);
    }
}
