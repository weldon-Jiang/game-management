package com.bend.platform.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.context.annotation.Profile;
import org.springframework.stereotype.Service;

import java.util.Map;

/**
 * Redis队列服务（临时禁用）
 *
 * <p>NOTE: 当前Redis配置存在问题，此服务暂时禁用
 * 如需启用，请确保Redis连接正常后移除 @Profile("redis-enabled") 注解
 */
@Slf4j
@Service
// @Profile("redis-enabled")  // 临时禁用
public class RedisQueueService {

    public void pushTask(String queue, Map<String, Object> task) {
        log.warn("RedisQueueService 暂时禁用，无法推送任务到队列: {}", queue);
    }

    public Map<String, Object> popTask(String queue) {
        log.warn("RedisQueueService 暂时禁用，无法从队列获取任务: {}", queue);
        return null;
    }

    public void publishTaskUpdate(String taskId, String status) {
        log.warn("RedisQueueService 暂时禁用，无法发布任务更新: {}", taskId);
    }

    public void subscribeTaskUpdates(String taskId, TaskUpdateCallback callback) {
        log.warn("RedisQueueService 暂时禁用，无法订阅任务更新: {}", taskId);
    }

    public interface TaskUpdateCallback {
        void onUpdate(String status, String result);
    }
}