package com.bend.platform.config;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.autoconfigure.condition.ConditionalOnProperty;
import org.springframework.data.redis.connection.Message;
import org.springframework.data.redis.connection.MessageListener;
import org.springframework.stereotype.Component;

import java.util.Map;

/**
 * Redis消息订阅器
 *
 * <p>NOTE: 仅在 Redis 配置启用时生效
 */
@Slf4j
@Component
// @ConditionalOnProperty(name = "spring.data.redis.enabled", havingValue = "true", matchIfMissing = false)
public class RedisMessageSubscriber implements MessageListener {

    private final ObjectMapper objectMapper = new ObjectMapper();

    public void handleTaskMessage(Message message) {
        log.info("收到Redis任务消息（已禁用）");
    }

    public void handleAgentMessage(Message message) {
        log.info("收到Redis Agent消息（已禁用）");
    }

    @Override
    public void onMessage(Message message, byte[] pattern) {
        log.info("收到Redis消息（已禁用）");
    }
}