package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.service.CredentialTokenService;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/agent/credentials")
@RequiredArgsConstructor
public class AgentCredentialController {

    private final CredentialTokenService credentialTokenService;

    @PostMapping("/exchange")
    public ApiResponse<String> exchangeToken(@RequestParam String token) {
        if (token.startsWith("DISABLED:")) {
            return ApiResponse.error(503, "Redis未启用，凭证功能不可用");
        }
        String credential = credentialTokenService.getAndInvalidate(token);
        if (credential == null) {
            return ApiResponse.error(404, "令牌不存在或已过期");
        }
        return ApiResponse.success("凭证获取成功", credential);
    }
}