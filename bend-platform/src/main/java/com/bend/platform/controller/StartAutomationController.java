package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.StartAutomationRequest;
import com.bend.platform.service.AutomationService;
import com.bend.platform.util.UserContext;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api/automation")
@RequiredArgsConstructor
public class StartAutomationController {

    private final AutomationService automationService;

    @PostMapping("/start")
    public ApiResponse<Map<String, Object>> startAutomation(@Valid @RequestBody StartAutomationRequest request) {
        String userId = UserContext.getUserId();
        String merchantId = UserContext.getMerchantId();

        if (merchantId == null) {
            return ApiResponse.error(400, "无法获取商户信息");
        }

        Map<String, Object> result = automationService.startAutomation(request, userId, merchantId);
        return ApiResponse.success("已创建" + result.get("total") + "个自动化任务", result);
    }

    @PostMapping("/stop/{streamingAccountId}")
    public ApiResponse<Void> stopAutomation(@PathVariable String streamingAccountId) {
        String merchantId = UserContext.getMerchantId();
        if (merchantId == null) {
            return ApiResponse.error(400, "无法获取商户信息");
        }

        automationService.stopAutomation(streamingAccountId, merchantId);
        return ApiResponse.success("已停止自动化任务", null);
    }

    @GetMapping("/status/{streamingAccountId}")
    public ApiResponse<Map<String, Object>> getAutomationStatus(@PathVariable String streamingAccountId) {
        String merchantId = UserContext.getMerchantId();
        if (merchantId == null) {
            return ApiResponse.error(400, "无法获取商户信息");
        }

        Map<String, Object> status = automationService.getAutomationStatus(streamingAccountId, merchantId);
        return ApiResponse.success(status);
    }
}