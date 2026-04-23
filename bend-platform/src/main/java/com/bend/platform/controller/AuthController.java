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
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

/**
 * 认证控制器
 *
 * <p>提供用户认证相关的所有接口，包括登录、注册、Token刷新等。
 *
 * <p>接口列表：
 * <ul>
 *   <li>POST /api/auth/login - 用户登录</li>
 *   <li>GET /api/auth/me - 获取当前用户信息</li>
 *   <li>POST /api/auth/register - 用户注册</li>
 *   <li>POST /api/auth/refresh - 刷新Token</li>
 * </ul>
 *
 * <p>认证机制：
 * <ul>
 *   <li>使用JWT进行无状态认证</li>
 *   <li>登录成功后返回Token，客户端需在后续请求的Header中携带</li>
 *   <li>Token格式：Authorization: Bearer {token}</li>
 * </ul>
 *
 * @see com.bend.platform.util.JwtUtil
 * @see com.bend.platform.util.UserContext
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
     * <p>验证用户凭据，有效则生成JWT Token返回。
     *
     * <p>请求示例：
     * <pre>
     * POST /api/auth/login
     * {
     *   "loginKey": "username or phone",
     *   "password": "password"
     * }
     * </pre>
     *
     * <p>响应示例：
     * <pre>
     * {
     *   "code": 0,
     *   "message": "登录成功",
     *   "data": {
     *     "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
     *     "userId": "user-001",
     *     "username": "admin",
     *     "merchantId": "merchant-001",
     *     "role": "owner"
     *   }
     * }
     * </pre>
     *
     * @param request 登录请求（loginKey支持用户名或手机号）
     * @return 登录结果（包含JWT Token和用户基本信息）
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
     * <p>从请求Header中的Token解析用户信息并返回。
     * 需要请求携带有效的JWT Token。
     *
     * @return 当前用户完整信息
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
     *
     * <p>创建新用户账号，同时自动创建对应商户。
     *
     * <p>处理流程：
     * <ol>
     *   <li>创建新商户（如果未指定名称则使用"默认商户"）</li>
     *   <li>创建用户并关联到商户，角色默认为owner</li>
     *   <li>生成JWT Token返回</li>
     * </ol>
     *
     * <p>请求示例：
     * <pre>
     * POST /api/auth/register
     * {
     *   "username": "admin",
     *   "password": "password123",
     *   "merchantName": "我的商户",
     *   "phone": "13800138000"
     * }
     * </pre>
     *
     * @param request 注册请求
     * @return 注册结果（包含JWT Token和新用户信息）
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

    /**
     * 刷新JWT Token
     *
     * <p>使用当前有效的Token换取新的Token，避免用户频繁重新登录。
     * 刷新后的Token会生成新的过期时间。
     *
     * <p>请求示例：
     * <pre>
     * POST /api/auth/refresh
     * Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
     * </pre>
     *
     * <p>注意：
     * <ul>
     *   <li>旧Token必须有效，已过期的Token无法刷新</li>
     *   <li>刷新后旧Token仍然有效（建议客户端及时更新）</li>
     *   <li>建议在Token过期前调用刷新接口</li>
     * </ul>
     *
     * @param authHeader Authorization Header（Bearer Token格式）
     * @return 新的Token和用户信息
     */
    @PostMapping("/refresh")
    public ApiResponse<LoginResponse> refreshToken(@RequestHeader("Authorization") String authHeader) {
        if (authHeader == null || !authHeader.startsWith("Bearer ")) {
            throw new BusinessException(400, "无效的Token");
        }

        String oldToken = authHeader.substring(7);

        if (!jwtUtil.validateToken(oldToken)) {
            throw new BusinessException(401, "Token无效或已过期");
        }

        String newToken = jwtUtil.refreshToken(oldToken);

        String userId = jwtUtil.getUserIdFromToken(newToken);
        MerchantUser user = merchantUserService.findById(userId);
        if (user == null) {
            throw new BusinessException(ResultCode.MerchantUser.NOT_FOUND);
        }

        LoginResponse response = LoginResponse.builder()
                .token(newToken)
                .userId(user.getId())
                .username(user.getUsername())
                .merchantId(user.getMerchantId())
                .role(user.getRole())
                .build();

        return ApiResponse.success("Token刷新成功", response);
    }
}