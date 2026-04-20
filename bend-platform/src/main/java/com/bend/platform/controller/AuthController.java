package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.dto.LoginRequest;
import com.bend.platform.dto.LoginResponse;
import com.bend.platform.dto.RegisterRequest;
import com.bend.platform.entity.Merchant;
import com.bend.platform.entity.MerchantUser;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.service.MerchantService;
import com.bend.platform.service.MerchantUserService;
import com.bend.platform.util.JwtUtil;
import com.bend.platform.util.UserContext;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;

/**
 * 认证控制器
 *
 * 功能说明：
 * - 处理用户登录、注册、获取当前用户信息等认证相关接口
 * - 提供JWT token的生成
 *
 * 主要功能：
 * - 用户登录：验证用户名密码，生成JWT token
 * - 获取当前用户信息
 * - 用户注册：创建新商户和用户
 */
@RestController
@RequestMapping("/api/auth")
@RequiredArgsConstructor
public class AuthController {

    private final MerchantUserService merchantUserService;
    private final MerchantService merchantService;
    private final JwtUtil jwtUtil;

    /**
     * 用户登录
     *
     * @param request 登录请求（包含登录名和密码）
     * @return 登录结果（包含JWT token和用户信息）
     */
    @PostMapping("/login")
    public ApiResponse<LoginResponse> login(@Valid @RequestBody LoginRequest request) {
        MerchantUser user = merchantUserService.login(request.getLoginKey(), request.getPassword());

        String token = jwtUtil.generateToken(user.getId(), user.getUsername(), user.getMerchantId(), user.getRole());

        LoginResponse response = LoginResponse.builder()
                .token(token)
                .userId(user.getId())
                .username(user.getUsername())
                .merchantId(user.getMerchantId())
                .role(user.getRole())
                .build();

        return ApiResponse.success("登录成功", response);
    }

    /**
     * 获取当前登录用户信息
     *
     * @return 当前用户信息
     */
    @GetMapping("/me")
    public ApiResponse<MerchantUser> getCurrentUser() {
        MerchantUser user = merchantUserService.findById(UserContext.getUserId());
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }
        return ApiResponse.success(user);
    }

    /**
     * 用户注册
     * 注册时自动创建默认商户和owner角色用户
     *
     * @param request 注册请求（包含用户名、密码、商户名、手机号）
     * @return 注册结果（包含JWT token和用户信息）
     */
    @PostMapping("/register")
    public ApiResponse<LoginResponse> register(@Valid @RequestBody RegisterRequest request) {
        Merchant merchant = merchantService.createMerchant(
                request.getMerchantName() != null ? request.getMerchantName() : "默认商户",
                request.getPhone()
        );

        MerchantUser user = merchantUserService.register(
                request.getUsername(),
                request.getPassword(),
                merchant.getId(),
                request.getPhone(),
                "owner"
        );

        String token = jwtUtil.generateToken(user.getId(), user.getUsername(), user.getMerchantId(), user.getRole());

        LoginResponse response = LoginResponse.builder()
                .token(token)
                .userId(user.getId())
                .username(user.getUsername())
                .merchantId(user.getMerchantId())
                .role(user.getRole())
                .build();

        return ApiResponse.success("注册成功", response);
    }
}