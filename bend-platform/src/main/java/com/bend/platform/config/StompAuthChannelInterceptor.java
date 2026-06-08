package com.bend.platform.config;

import com.bend.platform.dto.LoginUserInfo;
import com.bend.platform.util.JwtUtil;
import io.jsonwebtoken.Claims;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.lang.Nullable;
import org.springframework.messaging.Message;
import org.springframework.messaging.MessageChannel;
import org.springframework.messaging.simp.stomp.StompCommand;
import org.springframework.messaging.simp.stomp.StompHeaderAccessor;
import org.springframework.messaging.support.ChannelInterceptor;
import org.springframework.messaging.support.MessageHeaderAccessor;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;

import java.security.Principal;
import java.util.List;
import java.util.Set;

/**
 * STOMP 入站鉴权：CONNECT 校验 JWT，SUBSCRIBE 要求已认证且仅能订阅 /topic/admins/** 等管理 topic。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class StompAuthChannelInterceptor implements ChannelInterceptor {

    private static final String BEARER_PREFIX = "Bearer ";
    private static final Set<String> ALLOWED_ROLES = Set.of(
            "platform_admin", "merchant_owner", "operator"
    );
    private static final String ADMIN_TOPIC_PREFIX = "/topic/admins";

    private final JwtUtil jwtUtil;

    @Override
    public Message<?> preSend(Message<?> message, MessageChannel channel) {
        StompHeaderAccessor accessor = MessageHeaderAccessor.getAccessor(message, StompHeaderAccessor.class);
        if (accessor == null) {
            return message;
        }

        StompCommand command = accessor.getCommand();
        if (StompCommand.CONNECT.equals(command)) {
            authenticateConnect(accessor);
        } else if (StompCommand.SUBSCRIBE.equals(command)) {
            authorizeSubscribe(accessor);
        }
        return message;
    }

    private void authenticateConnect(StompHeaderAccessor accessor) {
        String token = extractToken(accessor);
        if (!StringUtils.hasText(token) || !jwtUtil.validateToken(token)) {
            log.warn("STOMP CONNECT 拒绝：无效或缺失 JWT");
            throw new IllegalArgumentException("STOMP authentication failed");
        }

        Claims claims = jwtUtil.parseToken(token);
        LoginUserInfo userInfo = LoginUserInfo.builder()
                .userId(claims.get("userId", String.class))
                .username(claims.getSubject())
                .merchantId(claims.get("merchantId", String.class))
                .role(claims.get("role", String.class))
                .build();

        if (!ALLOWED_ROLES.contains(userInfo.getRole())) {
            log.warn("STOMP CONNECT 拒绝：非法角色 {}", userInfo.getRole());
            throw new IllegalArgumentException("STOMP role not allowed");
        }

        accessor.setUser(new StompPrincipal(userInfo));
        log.debug("STOMP CONNECT 成功 - user: {}, role: {}", userInfo.getUsername(), userInfo.getRole());
    }

    private void authorizeSubscribe(StompHeaderAccessor accessor) {
        Principal principal = accessor.getUser();
        if (!(principal instanceof StompPrincipal stompPrincipal)) {
            log.warn("STOMP SUBSCRIBE 拒绝：未认证");
            throw new IllegalArgumentException("STOMP subscription requires authentication");
        }

        String destination = accessor.getDestination();
        if (!StringUtils.hasText(destination)) {
            return;
        }

        if (destination.startsWith(ADMIN_TOPIC_PREFIX)) {
            String role = stompPrincipal.getUserInfo().getRole();
            if (!ALLOWED_ROLES.contains(role)) {
                log.warn("STOMP SUBSCRIBE 拒绝：角色 {} 无权订阅 {}", role, destination);
                throw new IllegalArgumentException("STOMP subscription not allowed");
            }
        }
    }

    @Nullable
    private String extractToken(StompHeaderAccessor accessor) {
        List<String> authHeaders = accessor.getNativeHeader("Authorization");
        if (authHeaders != null && !authHeaders.isEmpty()) {
            String header = authHeaders.get(0);
            if (StringUtils.hasText(header) && header.startsWith(BEARER_PREFIX)) {
                return header.substring(BEARER_PREFIX.length()).trim();
            }
        }

        List<String> tokenHeaders = accessor.getNativeHeader("token");
        if (tokenHeaders != null && !tokenHeaders.isEmpty()) {
            return tokenHeaders.get(0);
        }
        return null;
    }
}
