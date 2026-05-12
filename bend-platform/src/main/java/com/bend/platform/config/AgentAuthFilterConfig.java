package com.bend.platform.config;

import lombok.RequiredArgsConstructor;
import org.springframework.boot.web.servlet.FilterRegistrationBean;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Agent 认证过滤器配置
 *
 * 配置 AgentAuthFilter 只对以下路径生效：
 * - /api/agents/heartbeat - 心跳（Agent调用）
 * - /api/agents/offline - 下线（Agent调用）
 * - /api/agents/uninstall - 卸载（Agent调用）
 * - /api/agents/status - 状态更新（Agent调用）
 * - /api/agent-callback/** - Agent回调
 * - /ws/agents - WebSocket
 *
 * 以下接口不经过此过滤器（使用JWT认证）：
 * - /api/agents/page - 分页查询（平台调用）
 * - /api/agents/{id} - 查询详情（平台调用）
 * - /api/agents/register - 注册（使用注册码）
 */
@Configuration
@RequiredArgsConstructor
public class AgentAuthFilterConfig {

    private final AgentAuthFilter agentAuthFilter;

    @Bean
    public FilterRegistrationBean<AgentAuthFilter> agentAuthFilterRegistration() {
        FilterRegistrationBean<AgentAuthFilter> registration = new FilterRegistrationBean<>();
        registration.setFilter(agentAuthFilter);
        // 只拦截 Agent 服务端点，不拦截平台查询接口
        registration.addUrlPatterns(
            "/api/agents/heartbeat",
            "/api/agents/offline",
            "/api/agents/uninstall",
            "/api/agents/status",
            "/api/agent-callback/*",
            "/ws/agents"
        );
        registration.setName("agentAuthFilter");
        registration.setOrder(1);
        return registration;
    }
}
