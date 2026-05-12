package com.bend.platform.config;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.web.filter.CorsFilter;

import java.util.Arrays;
import java.util.stream.Collectors;

/**
 * 跨域配置
 * - 生产环境（Docker部署）：通过 Gateway 统一处理，禁用此配置
 * - 本地开发直接访问后端：可以启用此配置
 */
@Configuration
@ConditionalOnProperty(name = "cors.enabled", havingValue = "true", matchIfMissing = true)
public class CorsConfig {

    @Value("${cors.allowed-origins:http://localhost:5173,http://localhost:3090}")
    private String allowedOrigins;

    @Value("${cors.allowed-methods:GET,POST,PUT,DELETE,OPTIONS}")
    private String allowedMethods;

    @Value("${cors.allowed-headers:*}")
    private String allowedHeaders;

    @Value("${cors.allow-credentials:true}")
    private boolean allowCredentials;

    @Value("${cors.max-age:3600}")
    private long maxAge;

    @Bean
    public CorsFilter corsFilter() {
        CorsConfiguration config = new CorsConfiguration();

        config.setAllowedOrigins(Arrays.asList(allowedOrigins.split(","))
                .stream()
                .map(String::trim)
                .collect(Collectors.toList()));

        config.setAllowedMethods(Arrays.asList(allowedMethods.split(","))
                .stream()
                .map(String::trim)
                .collect(Collectors.toList()));

        if ("*".equals(allowedHeaders)) {
            config.setAllowedHeaders(Arrays.asList("*"));
        } else {
            config.setAllowedHeaders(Arrays.asList(allowedHeaders.split(","))
                    .stream()
                    .map(String::trim)
                    .collect(Collectors.toList()));
        }

        config.setAllowCredentials(allowCredentials);
        config.setMaxAge(maxAge);

        config.setExposedHeaders(Arrays.asList("Authorization", "Content-Type", "X-Requested-With"));

        UrlBasedCorsConfigurationSource source = new UrlBasedCorsConfigurationSource();
        source.registerCorsConfiguration("/**", config);
        return new CorsFilter(source);
    }
}
