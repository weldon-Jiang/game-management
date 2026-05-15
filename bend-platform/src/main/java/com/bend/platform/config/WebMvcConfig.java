package com.bend.platform.config;

import lombok.RequiredArgsConstructor;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
@RequiredArgsConstructor
public class WebMvcConfig implements WebMvcConfigurer {

    private final JwtAuthInterceptor jwtAuthInterceptor;
    private final RateLimitInterceptor rateLimitInterceptor;

    @Override
    public void addInterceptors(InterceptorRegistry registry) {
        // 限流拦截器 - 对所有 API 生效
        registry.addInterceptor(rateLimitInterceptor)
                .addPathPatterns("/api/**");

        // JWT 认证拦截器 - 对所有 API 生效，但排除公开接口
        registry.addInterceptor(jwtAuthInterceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns(
                        "/api/auth/**",
                        "/api/agents/**",
                        "/api/agent-callback/**",
                        "/api/monitoring/**",
                        "/api/registration-codes/**",
                        "/api/test/**"
                );
    }
}
