package com.bend.gateway.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.reactive.CorsWebFilter;
import org.springframework.web.cors.reactive.UrlBasedCorsConfigurationSource;

import java.util.Arrays;

/**
 * 全局 CORS 配置：允许前端跨域访问 Gateway（8060）上的 /api 与 /ws。
 * 生产环境通过 bend.gateway.cors.allowed-origin-patterns 配置白名单。
 */
@Configuration
@RequiredArgsConstructor
public class CorsConfig {

    private final BendGatewayProperties gatewayProperties;

    @Bean
    public CorsWebFilter corsWebFilter() {
        BendGatewayProperties.Cors cors = gatewayProperties.getCors();
        CorsConfiguration config = new CorsConfiguration();

        for (String pattern : cors.getAllowedOriginPatterns()) {
            if (pattern == null || pattern.isBlank()) {
                continue;
            }
            // 支持环境变量注入逗号分隔的多个域名
            for (String part : pattern.split(",")) {
                String trimmed = part.trim();
                if (!trimmed.isEmpty()) {
                    config.addAllowedOriginPattern(trimmed);
                }
            }
        }

        config.setAllowedMethods(Arrays.asList("GET", "POST", "PUT", "DELETE", "OPTIONS"));
        config.addAllowedHeader("*");
        config.setAllowCredentials(cors.isAllowCredentials());
        config.setMaxAge(cors.getMaxAge());

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);

        return new CorsWebFilter(source);
    }
}
