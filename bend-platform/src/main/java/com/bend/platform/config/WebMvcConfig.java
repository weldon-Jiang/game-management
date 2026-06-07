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

        // JWT 认证拦截器 - 对所有 API 生效，但排除公开接口和 Agent 回调接口
        // 注意：Agent 回调接口（如 /api/{taskId}/progress）由 AgentAuthFilter 处理，不需要 JWT
        registry.addInterceptor(jwtAuthInterceptor)
                .addPathPatterns("/api/**")
                .excludePathPatterns(
                        "/api/auth/**",
                        "/api/agents/register",
                        "/api/agents/heartbeat",
                        "/api/agents/uninstall",
                        "/api/agents/offline",
                        "/api/agents/status",
                        "/api/agent-callback/**",
                        "/api/v1/agent-callback/**",
                        "/api/registration-codes/validate/**",
                        "/api/registration-codes/check/**",
                        "/api/registration-codes/activate/**",
                        "/api/test/**",
                        "/api/tasks/*/complete",
                        "/api/tasks/*/fail",
                        "/api/tasks/**/complete",
                        "/api/tasks/**/fail",
                        "/api/**/progress",
                        "/api/**/match/complete",
                        "/api/**/game-accounts/status",
                        "/api/**/game-account/*/complete",
                        "/api/**/game-account/*/status",
                        "/api/daily-match-count/reset",
                        "/api/agent/credentials/**"
                );
    }
}
