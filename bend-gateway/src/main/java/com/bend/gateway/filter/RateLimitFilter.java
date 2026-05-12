package com.bend.gateway.filter;

import com.bend.gateway.config.BendGatewayProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.data.redis.core.ReactiveStringRedisTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;
import java.time.Duration;

@Slf4j
@Component
@RequiredArgsConstructor
public class RateLimitFilter implements GlobalFilter, Ordered {

    private final BendGatewayProperties gatewayProperties;
    private final ReactiveStringRedisTemplate redisTemplate;

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        BendGatewayProperties.RateLimit rateLimit = gatewayProperties.getRateLimit();

        if (!rateLimit.isEnabled()) {
            return chain.filter(exchange);
        }

        String path = exchange.getRequest().getURI().getPath();
        String clientId = getClientId(exchange.getRequest());

        BendGatewayProperties.PathLimit pathLimit = findPathLimit(path, rateLimit);
        int qps = pathLimit != null ? pathLimit.getQps() : rateLimit.getDefaultLimit().getQps();
        int burst = pathLimit != null ? pathLimit.getBurst() : rateLimit.getDefaultLimit().getBurst();

        String key = "gateway:rate:" + clientId + ":" + path;
        int maxRequests = qps + burst;

        return redisTemplate.opsForValue().increment(key)
                .flatMap(count -> {
                    if (count == 1) {
                        return redisTemplate.expire(key, Duration.ofSeconds(1))
                                .thenReturn(count);
                    }
                    return Mono.just(count);
                })
                .flatMap(count -> {
                    if (count <= maxRequests) {
                        log.debug("Request allowed - IP: {}, Path: {}, QPS: {}, Count: {}", clientId, path, qps, count);
                        return chain.filter(exchange);
                    } else {
                        log.warn("Request rate limited - IP: {}, Path: {}, Limit: {}/{}", clientId, path, qps, burst);
                        return rateLimited(exchange);
                    }
                })
                .onErrorResume(e -> {
                    log.warn("Redis rate limit failed, skipping", e);
                    return chain.filter(exchange);
                });
    }

    private String getClientId(ServerHttpRequest request) {
        String xForwardedFor = request.getHeaders().getFirst("X-Forwarded-For");
        if (xForwardedFor != null && !xForwardedFor.isEmpty()) {
            return xForwardedFor.split(",")[0].trim();
        }

        String xRealIp = request.getHeaders().getFirst("X-Real-IP");
        if (xRealIp != null && !xRealIp.isEmpty()) {
            return xRealIp;
        }

        return request.getRemoteAddress() != null ? request.getRemoteAddress().getAddress().getHostAddress() : "unknown";
    }

    private BendGatewayProperties.PathLimit findPathLimit(String path, BendGatewayProperties.RateLimit rateLimit) {
        for (BendGatewayProperties.PathLimit pl : rateLimit.getPaths()) {
            if (pathMatch(path, pl.getPath())) {
                return pl;
            }
        }
        return null;
    }

    private boolean pathMatch(String requestPath, String pattern) {
        if (pattern.endsWith("/**")) {
            String basePath = pattern.substring(0, pattern.length() - 3);
            return requestPath.startsWith(basePath);
        }
        return requestPath.equals(pattern) || requestPath.startsWith(pattern + "/");
    }

    private Mono<Void> rateLimited(ServerWebExchange exchange) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.TOO_MANY_REQUESTS);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);

        String body = "{\"code\":429,\"message\":\"请求过于频繁，请稍后再试\"}";
        DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));

        return response.writeWith(Mono.just(buffer));
    }

    @Override
    public int getOrder() {
        return -90;
    }
}
