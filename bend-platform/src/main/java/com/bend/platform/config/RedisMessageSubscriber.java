package com.bend.platform.config;

import com.bend.platform.websocket.AgentWebSocketEndpoint;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Redis消息订阅器
 *
 * 功能说明：
 * - 订阅Redis频道消息
 * - 处理跨实例的任务分发
 * - 处理Agent状态同步消息
 *
 * 消息类型：
 * - task:create: 新任务创建通知
 * - task:cancel: 任务取消通知
 * - agent:status: Agent状态变更通知
 * - agent:heartbeat: Agent心跳同步
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class RedisMessageSubscriber implements MessageListener {

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 处理任务相关消息
     */
    public void handleTaskMessage(Message message) {
        try {
            String channel = new String(message.getChannel());
            String body = new String(message.getBody());

            log.info("收到Redis任务消息 - 频道: {}, 内容: {}", channel, body);

            if (channel.startsWith("task:")) {
                String action = channel.substring(5);
                Map<String, Object> data = objectMapper.readValue(body, Map.class);

                switch (action) {
                    case "create":
                        handleTaskCreate(data);
                        break;
                    case "cancel":
                        handleTaskCancel(data);
                        break;
                    default:
                        log.warn("未知任务消息类型: {}", action);
                }
            }
        } catch (Exception e) {
            log.error("处理Redis消息失败", e);
        }
    }

    /**
     * 处理Agent相关消息
     */
    public void handleAgentMessage(Message message) {
        try {
            String channel = new String(message.getChannel());
            String body = new String(message.getBody());

            log.info("收到Redis Agent消息 - 频道: {}, 内容: {}", channel, body);

            if (channel.startsWith("agent:")) {
                String action = channel.substring(6);
                Map<String, Object> data = objectMapper.readValue(body, Map.class);

                switch (action) {
                    case "status":
                        handleAgentStatusChange(data);
                        break;
                    case "heartbeat":
                        handleAgentHeartbeat(data);
                        break;
                    default:
                        log.warn("未知Agent消息类型: {}", action);
                }
            }
        } catch (Exception e) {
            log.error("处理Redis消息失败", e);
        }
    }

    /**
     * 处理任务创建消息
     * 通知所有相关实例有新任务
     */
    private void handleTaskCreate(Map<String, Object> data) {
        String taskId = (String) data.get("taskId");
        String agentId = (String) data.get("agentId");
        log.info("Redis通知：新任务创建 - TaskID: {}, AgentID: {}", taskId, agentId);
    }

    /**
     * 处理任务取消消息
     */
    private void handleTaskCancel(Map<String, Object> data) {
        String taskId = (String) data.get("taskId");
        log.info("Redis通知：任务取消 - TaskID: {}", taskId);
    }

    /**
     * 处理Agent状态变更消息
     */
    private void handleAgentStatusChange(Map<String, Object> data) {
        String agentId = (String) data.get("agentId");
        String status = (String) data.get("status");
        log.info("Redis通知：Agent状态变更 - AgentID: {}, 状态: {}", agentId, status);
    }

    /**
     * 处理Agent心跳同步消息
     */
    private void handleAgentHeartbeat(Map<String, Object> data) {
        String agentId = (String) data.get("agentId");
        log.debug("Redis同步：Agent心跳 - AgentID: {}", agentId);
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        try {
            String channel = new String(message.getChannel());
            if (channel.startsWith("task:")) {
                handleTaskMessage(message);
            } else if (channel.startsWith("agent:")) {
                handleAgentMessage(message);
            }
        } catch (Exception e) {
            log.error("处理Redis消息失败", e);
        }
    }
}
