package com.bend.platform.config;

import org.springframework.context.annotation.Configuration;
import org.springframework.web.socket.config.annotation.EnableWebSocket;
import org.springframework.web.socket.config.annotation.WebSocketConfigurer;
import org.springframework.web.socket.server.standard.SpringConfigurator;

/**
 * WebSocket配置类
 *
 * <p>配置WebSocket端点，支持Agent与后端的实时通信。
 *
 * <p>WebSocket端点：
 * <ul>
 *   <li>/ws/agent - Agent WebSocket连接端点（使用javax.websocket）</li>
 *   <li>STOMP WebSocket - 预留配置（当前未启用）</li>
 * </ul>
 *
 * <p>通信机制：
 * <ul>
 *   <li>Agent通过WebSocket保持长连接</li>
 *   <li>支持任务下发、心跳检测、实时消息推送</li>
 *   <li>连接断开后自动重连机制由客户端处理</li>
 * </ul>
 *
 * @see com.bend.platform.websocket.AgentWebSocketEndpoint
 */
@Configuration
@EnableWebSocket
public class WebSocketConfig implements WebSocketConfigurer {

    /**
     * 注册WebSocket处理器
     *
     * <p>Note: Agent使用的 /ws/agent 端点通过 AgentWebSocketEndpoint 类
     * 使用 javax.websocket 注解方式注册，不在此处配置。
     * 此方法为STOMP WebSocket预留配置接口。
     *
     * @param registry WebSocket处理器注册表
     */
    @Override
    public void registerWebSocketHandlers(org.springframework.web.socket.config.annotation.WebSocketHandlerRegistry registry) {
        // This is for STOMP WebSocket - the javax.websocket endpoints are registered separately
    }
}