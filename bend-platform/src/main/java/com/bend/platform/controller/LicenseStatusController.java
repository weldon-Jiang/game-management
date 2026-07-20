package com.bend.platform.controller;

import com.bend.platform.config.LicenseClientCondition;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.service.LicenseClientService;
import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Conditional;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 分控授权状态查询接口
 *
 * <p>仅 tenant 模式装配。供分控后台前端展示当前授权状态/到期时间/离线宽限。
 */
@RestController
@RequestMapping("/api/license-status")
@RequiredArgsConstructor
@Conditional(LicenseClientCondition.class)
public class LicenseStatusController {

    private final LicenseClientService licenseClientService;

    @GetMapping
    public ApiResponse<LicenseClientService.LicenseStatus> status() {
        return ApiResponse.success(licenseClientService.getStatus());
    }

    /**
     * Agent 专用：查询当前分控授权是否有效。
     * 走 X-Agent-Id/X-Agent-Secret 鉴权(AgentAuthFilter)，不走 JWT。
     * Agent 可配置 require_license_check=true 来启用此校验。
     */
    @GetMapping("/agent")
    public ApiResponse<LicenseClientService.LicenseStatus> agentStatus() {
        LicenseClientService.LicenseStatus st = licenseClientService.getStatus();
        return ApiResponse.success(st);
    }

    /** 手动触发一次校验(分控后台"立即校验"按钮)。 */
    @PostMapping("/verify-now")
    public ApiResponse<LicenseClientService.LicenseStatus> verifyNow() {
        licenseClientService.verifyNow();
        return ApiResponse.success(licenseClientService.getStatus());
    }
}
