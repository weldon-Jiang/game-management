package com.bend.platform.config;

import com.bend.platform.dto.LoginUserInfo;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.util.JwtUtil;
import com.bend.platform.util.UserContext;
import io.jsonwebtoken.Claims;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.servlet.HandlerInterceptor;

import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;

/**
 * JWT认证拦截器
 * 在请求处理前解析JWT token，将用户信息存储到上下文
 * 在请求处理后清理上下文，防止内存泄漏
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class JwtAuthInterceptor implements HandlerInterceptor {

    private final JwtUtil jwtUtil;

    private static final String AUTHORIZATION_HEADER = "Authorization";
    private static final String BEARER_PREFIX = "Bearer ";

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) {
        String authHeader = request.getHeader(AUTHORIZATION_HEADER);

        if (!StringUtils.hasText(authHeader)) {
            throw new BusinessException(ResultCode.Auth.TOKEN_MISSING);
        }

        if (!authHeader.startsWith(BEARER_PREFIX)) {
            throw new BusinessException(ResultCode.Auth.TOKEN_INVALID);
        }

        String token = authHeader.substring(BEARER_PREFIX.length());

        if (!jwtUtil.validateToken(token)) {
            throw new BusinessException(ResultCode.Auth.TOKEN_INVALID);
        }

        Claims claims = jwtUtil.parseToken(token);

        LoginUserInfo userInfo = LoginUserInfo.builder()
                .userId(claims.get("userId", String.class))
                .username(claims.getSubject())
                .merchantId(claims.get("merchantId", String.class))
                .role(claims.get("role", String.class))
                .build();

        UserContext.setUserInfo(userInfo);

        log.debug("JWT认证成功，用户: {}, 商户: {}", userInfo.getUsername(), userInfo.getMerchantId());

        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, HttpServletResponse response, Object handler, Exception ex) {
        UserContext.clear();
    }
}