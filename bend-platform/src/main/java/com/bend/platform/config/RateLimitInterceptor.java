package com.bend.platform.config;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Component;
import org.springframework.web.servlet.HandlerInterceptor;

import java.util.concurrent.TimeUnit;

@Slf4j
@Component
@RequiredArgsConstructor
public class RateLimitInterceptor implements HandlerInterceptor {

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    private static final String RATE_LIMIT_PREFIX = "rate:limit:";
    private static final int DEFAULT_LIMIT = 100;
    private static final int DEFAULT_WINDOW = 60;

    @Override
    public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
        if (redisTemplate == null) {
            return true;
        }

        String path = request.getRequestURI();

        if (isExcluded(path)) {
            return true;
        }

        String clientId = getClientId(request);
        int limit = getLimit(path);
        int window = getWindow(path);

        String key = RATE_LIMIT_PREFIX + clientId + ":" + path;

        Long currentCount = redisTemplate.opsForValue().increment(key);

        if (currentCount != null && currentCount == 1) {
            redisTemplate.expire(key, window, TimeUnit.SECONDS);
        }

        response.setHeader("X-RateLimit-Limit", String.valueOf(limit));
        int remaining = (currentCount != null) ? Math.max(0, limit - currentCount.intValue()) : limit;
        response.setHeader("X-RateLimit-Remaining", String.valueOf(remaining));

        if (currentCount != null && currentCount > limit) {
            log.warn("请求过于频繁 - IP: {}, Path: {}, Count: {}", clientId, path, currentCount);
            response.setStatus(429);
            response.setContentType("application/json;charset=UTF-8");
            response.getWriter().write("{\"code\":429,\"message\":\"请求过于频繁，请稍后再试\"}");
            return false;
        }

        return true;
    }

    private boolean isExcluded(String path) {
        return path.contains("/actuator/")
                || path.contains("/swagger-ui")
                || path.contains("/v3/api-docs")
                || path.contains("/websocket");
    }

    private String getClientId(HttpServletRequest request) {
        String xForwardedFor = request.getHeader("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
            return xForwardedFor.split(",")[0].trim();
        }
        String xRealIp = request.getHeader("X-Real-IP");
        if (xRealIp != null && !xRealIp.isEmpty()) {
            return xRealIp;
        }
        return request.getRemoteAddr();
    }

    private int getLimit(String path) {
        if (path.contains("/api/auth/login")) {
            return 5;
        }
        if (path.contains("/api/auth/register")) {
            return 3;
        }
        if (path.contains("/api/registration-codes/activate")) {
            return 5;
        }
        return DEFAULT_LIMIT;
    }

    private int getWindow(String path) {
        if (path.contains("/api/auth/login")) {
            return 60;
        }
        if (path.contains("/api/auth/register")) {
            return 60;
        }
        if (path.contains("/api/registration-codes/activate")) {
            return 60;
        }
        return DEFAULT_WINDOW;
    }
}