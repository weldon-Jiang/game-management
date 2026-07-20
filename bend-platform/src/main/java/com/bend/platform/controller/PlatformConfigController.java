package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.PlatformConfigVo;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * 平台部署配置查询（总控/分控模式）。
 *
 * <p>前端据此决定菜单可见性，例如注册码管理仅总控展示。
 */
@RestController
@RequestMapping("/api/platform")
public class PlatformConfigController {

    @Value("${license.mode:master}")
    private String licenseMode;

    @GetMapping("/config")
    public ApiResponse<PlatformConfigVo> config() {
        PlatformConfigVo vo = new PlatformConfigVo();
        vo.setMode("tenant".equalsIgnoreCase(licenseMode) ? "tenant" : "master");
        return ApiResponse.success(vo);
    }
}
