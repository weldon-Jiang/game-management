package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.service.impl.VipLevelService;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.List;

@RestController
@RequestMapping("/api/vip")
@RequiredArgsConstructor
public class VipController {

    private final VipLevelService vipLevelService;

    @GetMapping("/info/{merchantId}")
    public ApiResponse<VipLevelService.VipInfo> getVipInfo(@PathVariable String merchantId) {
        return ApiResponse.success(vipLevelService.getVipInfo(merchantId));
    }

    @GetMapping("/levels")
    public ApiResponse<List<VipLevelService.VipLevelInfo>> getAllVipLevels() {
        return ApiResponse.success(vipLevelService.getAllVipLevels());
    }

    @GetMapping("/my-info")
    public ApiResponse<VipLevelService.VipInfo> getMyVipInfo() {
        String merchantId = UserContext.getMerchantId();
        return ApiResponse.success(vipLevelService.getVipInfo(merchantId));
    }

    @GetMapping("/my-levels")
    public ApiResponse<List<VipLevelService.VipLevelInfo>> getMyVipLevels() {
        return ApiResponse.success(vipLevelService.getAllVipLevels());
    }
}
