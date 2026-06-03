package com.bend.platform.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.Map;

/**
 * Redis 队列服务（当前未启用）
 *
 * <p><b>设计决策（2026-06-03）</b>：任务下发以 WebSocket 直推为主（TaskExecutorService →
 * AgentWebSocketEndpoint）。Redis 队列作为可选的离线缓冲，在 Redis 连接与 spring profile
 * {@code redis-enabled} 就绪前保持 no-op，避免误用半残队列。
 *
 * <p>启用步骤：修复 Redis 配置 → 实现本类 → 在 TaskExecutorService 中增加 WS 失败时的 push 回退。
 */
@Slf4j
@Service
public class RedisQueueService {

    public void pushTask(String queue, Map<String, Object> task) {
        log.debug("RedisQueueService 未启用，任务经 WebSocket 直推: queue={}", queue);
    }

    public Map<String, Object> popTask(String queue) {
        log.debug("RedisQueueService 未启用: queue={}", queue);
        return null;
    }

    public void publishTaskUpdate(String taskId, String status) {
        log.debug("RedisQueueService 未启用: taskId={}", taskId);
    }

    public void subscribeTaskUpdates(String taskId, TaskUpdateCallback callback) {
        log.debug("RedisQueueService 未启用: taskId={}", taskId);
    }

    public interface TaskUpdateCallback {
        void onUpdate(String status, String result);
    }
}