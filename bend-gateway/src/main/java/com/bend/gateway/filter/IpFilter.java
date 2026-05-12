package com.bend.gateway.filter;

import com.bend.gateway.config.BendGatewayProperties;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.cloud.gateway.filter.GatewayFilterChain;
import org.springframework.cloud.gateway.filter.GlobalFilter;
import org.springframework.core.Ordered;
import org.springframework.core.io.buffer.DataBuffer;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.server.reactive.ServerHttpRequest;
import org.springframework.http.server.reactive.ServerHttpResponse;
import org.springframework.stereotype.Component;
import org.springframework.web.server.ServerWebExchange;
import reactor.core.publisher.Mono;

import java.nio.charset.StandardCharsets;

@Slf4j
@Component
@RequiredArgsConstructor
public class IpFilter implements GlobalFilter, Ordered {

    private final BendGatewayProperties gatewayProperties;

    @Override
    public Mono<Void> filter(ServerWebExchange exchange, GatewayFilterChain chain) {
        BendGatewayProperties.IpFilter ipFilter = gatewayProperties.getIpFilter();

        if (!ipFilter.isEnabled()) {
            return chain.filter(exchange);
        }

        String clientIp = getClientIp(exchange.getRequest());
        log.debug("Request from IP: {}", clientIp);

        if (!ipFilter.getWhitelist().isEmpty()) {
            if (!ipFilter.getWhitelist().contains(clientIp)) {
                log.warn("IP {} not in whitelist, blocked", clientIp);
                return forbidden(exchange, "IP not in whitelist");
            }
        }

        if (ipFilter.getBlacklist().contains(clientIp)) {
            log.warn("IP {} in blacklist, blocked", clientIp);
            return forbidden(exchange, "IP in blacklist");
        }

        return chain.filter(exchange);
    }

    private String getClientIp(ServerHttpRequest request) {
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

    private Mono<Void> forbidden(ServerWebExchange exchange, String message) {
        ServerHttpResponse response = exchange.getResponse();
        response.setStatusCode(HttpStatus.FORBIDDEN);
        response.getHeaders().setContentType(MediaType.APPLICATION_JSON);

        String body = String.format("{\"code\":403,\"message\":\"%s\"}", message);
        DataBuffer buffer = response.bufferFactory().wrap(body.getBytes(StandardCharsets.UTF_8));

        return response.writeWith(Mono.just(buffer));
    }

    @Override
    public int getOrder() {
        return -100;
    }
}
