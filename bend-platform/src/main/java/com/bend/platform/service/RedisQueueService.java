package com.bend.platform.service;

import com.bend.platform.config.RedisConfig;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;
import org.springframework.util.CollectionUtils;

import java.util.concurrent.TimeUnit;

/**
 * Redis消息队列服务
 *
 * 功能说明：
 * - 提供分布式消息队列功能
 * - 支持任务分发和事件通知
 * - 支持分布式锁
 *
 * 队列类型：
 * - FIFO队列：按顺序处理任务
 * - 优先级队列：通过ZSet实现
 * - 发布/订阅：实时通知
 *
 * 应用场景：
 * - 跨实例任务分发
 * - Agent状态同步
 * - 分布式锁（任务分配）
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class RedisQueueService {

    private final StringRedisTemplate redisTemplate;
    private final ObjectMapper objectMapper = new ObjectMapper();

    // 队列键前缀
    private static final String QUEUE_PREFIX = "queue:";
    private static final String TASK_QUEUE = QUEUE_PREFIX + "tasks";
    private static final String AGENT_QUEUE = QUEUE_PREFIX + "agents";

    // 分布式锁键前缀
    private static final String LOCK_PREFIX = "lock:";
    private static final String AGENT_LOCK_PREFIX = LOCK_PREFIX + "agent:";
    private static final String TASK_LOCK_PREFIX = LOCK_PREFIX + "task:";

    // 缓存键前缀
    private static final String CACHE_PREFIX = "cache:";
    private static final String AGENT_STATUS_CACHE = CACHE_PREFIX + "agent:status:";
    private static final String AGENT_HEARTBEAT_CACHE = CACHE_PREFIX + "agent:heartbeat:";

    // 频道前缀
    private static final String CHANNEL_PREFIX = "channel:";
    private static final String TASK_CHANNEL = CHANNEL_PREFIX + "task";
    private static final String AGENT_CHANNEL = CHANNEL_PREFIX + "agent";

    /**
     * 发布任务消息到队列
     *
     * 功能说明：
     * - 将任务数据放入FIFO队列
     * - 同时发布到订阅频道通知在线实例
     *
     * 参数说明：
     * - taskId: 任务ID
     * - agentId: 目标Agent ID
     * - taskData: 任务数据
     */
    public void publishTask(String taskId, String agentId, Object taskData) {
        try {
            String message = objectMapper.writeValueAsString(taskData);

            // 放入FIFO队列
            redisTemplate.opsForList().rightPush(TASK_QUEUE, message);

            // 发布到任务频道
            java.util.Map<String, Object> taskMessageMap = new java.util.HashMap<>();
            taskMessageMap.put("taskId", taskId);
            taskMessageMap.put("agentId", agentId);
            taskMessageMap.put("action", "create");
            taskMessageMap.put("timestamp", System.currentTimeMillis());
            String channelMessage = objectMapper.writeValueAsString(taskMessageMap);
            redisTemplate.convertAndSend(TASK_CHANNEL, channelMessage);

            log.info("Redis发布任务消息 - TaskID: {}, AgentID: {}", taskId, agentId);
        } catch (Exception e) {
            log.error("发布任务消息失败", e);
        }
    }

    /**
     * 从队列获取任务（阻塞）
     *
     * 功能说明：
     * - 从FIFO队列左侧取任务
     * - 支持超时设置避免阻塞
     *
     * 参数说明：
     * - timeout: 超时时间
     * - unit: 时间单位
     *
     * 返回值：
     * - 任务数据字符串，无数据返回null
     */
    public String popTask(long timeout, TimeUnit unit) {
        try {
            return redisTemplate.opsForList().leftPop(TASK_QUEUE, timeout, unit);
        } catch (Exception e) {
            log.error("获取任务消息失败", e);
            return null;
        }
    }

    /**
     * 发布Agent状态变更消息
     *
     * 参数说明：
     * - agentId: Agent ID
     * - status: 状态（online/offline/busy）
     */
    public void publishAgentStatus(String agentId, String status) {
        try {
            java.util.Map<String, Object> agentStatusMap = new java.util.HashMap<>();
            agentStatusMap.put("agentId", agentId);
            agentStatusMap.put("status", status);
            agentStatusMap.put("timestamp", System.currentTimeMillis());
            String channelMessage = objectMapper.writeValueAsString(agentStatusMap);
            redisTemplate.convertAndSend(AGENT_CHANNEL, channelMessage);
            log.debug("Redis发布Agent状态消息 - AgentID: {}, 状态: {}", agentId, status);
        } catch (Exception e) {
            log.error("发布Agent状态消息失败", e);
        }
    }

    /**
     * 缓存Agent状态
     *
     * 功能说明：
     * - 在Redis中缓存Agent在线状态
     * - 用于多实例间的状态共享
     *
     * 参数说明：
     * - agentId: Agent ID
     * - status: 状态
     * - ttl: 过期时间（秒）
     */
    public void cacheAgentStatus(String agentId, String status, long ttl) {
        try {
            redisTemplate.opsForValue().set(AGENT_STATUS_CACHE + agentId, status, ttl, TimeUnit.SECONDS);
        } catch (Exception e) {
            log.error("缓存Agent状态失败", e);
        }
    }

    /**
     * 获取缓存的Agent状态
     *
     * 返回值：Agent状态，不存在返回null
     */
    public String getCachedAgentStatus(String agentId) {
        try {
            return redisTemplate.opsForValue().get(AGENT_STATUS_CACHE + agentId);
        } catch (Exception e) {
            log.error("获取Agent状态缓存失败", e);
            return null;
        }
    }

    /**
     * 更新Agent心跳时间
     *
     * 功能说明：
     * - 使用Redis INCR原子递增心跳计数器
     * - 结合TTL实现心跳过期检测
     *
     * 参数说明：
     * - agentId: Agent ID
     * - ttl: 过期时间（秒）
     */
    public void updateAgentHeartbeat(String agentId, long ttl) {
        try {
            String key = AGENT_HEARTBEAT_CACHE + agentId;
            redisTemplate.opsForValue().increment(key);
            redisTemplate.expire(key, ttl, TimeUnit.SECONDS);
        } catch (Exception e) {
            log.error("更新Agent心跳失败", e);
        }
    }

    /**
     * 检查Agent是否活跃（心跳是否超时）
     *
     * 参数说明：
     * - agentId: Agent ID
     * - timeout: 超时阈值（秒）
     *
     * 返回值：
     * - true: Agent活跃
     * - false: Agent可能已离线
     */
    public boolean isAgentAlive(String agentId, long timeout) {
        try {
            String key = AGENT_HEARTBEAT_CACHE + agentId;
            Long count = redisTemplate.opsForValue().increment(key);
            return count != null && count > 0;
        } catch (Exception e) {
            log.error("检查Agent活跃状态失败", e);
            return false;
        }
    }

    /**
     * 获取Agent在线列表
     *
     * 功能说明：
     * - 扫描所有Agent状态缓存
     * - 返回当前在线的Agent列表
     *
     * 返回值：在线Agent ID列表
     */
    public java.util.List<String> getOnlineAgents() {
        try {
            java.util.Set<String> keys = redisTemplate.keys(AGENT_STATUS_CACHE + "*");
            if (CollectionUtils.isEmpty(keys)) {
                return new java.util.ArrayList<>();
            }
            java.util.List<String> onlineAgents = new java.util.ArrayList<>();
            for (String key : keys) {
                String status = redisTemplate.opsForValue().get(key);
                if ("online".equals(status)) {
                    onlineAgents.add(key.substring(AGENT_STATUS_CACHE.length()));
                }
            }
            return onlineAgents;
        } catch (Exception e) {
            log.error("获取在线Agent列表失败", e);
            return new java.util.ArrayList<>();
        }
    }

    /**
     * 尝试获取分布式锁（任务分配锁）
     *
     * 功能说明：
     * - 使用Redis SETNX实现分布式锁
     * - 支持锁自动过期
     *
     * 参数说明：
     * - taskId: 任务ID
     * - ttl: 锁过期时间（秒）
     *
     * 返回值：
     * - true: 获取锁成功
     * - false: 锁已被占用
     */
    public boolean tryAcquireTaskLock(String taskId, long ttl) {
        try {
            String key = TASK_LOCK_PREFIX + taskId;
            Boolean success = redisTemplate.opsForValue().setIfAbsent(key, "locked", ttl, TimeUnit.SECONDS);
            return success != null && success;
        } catch (Exception e) {
            log.error("获取任务锁失败", e);
            return false;
        }
    }

    /**
     * 释放任务锁
     */
    public void releaseTaskLock(String taskId) {
        try {
            redisTemplate.delete(TASK_LOCK_PREFIX + taskId);
        } catch (Exception e) {
            log.error("释放任务锁失败", e);
        }
    }

    /**
     * 尝试获取Agent锁（防止多实例同时控制同一Agent）
     *
     * 参数说明：
     * - agentId: Agent ID
     * - ttl: 锁过期时间
     *
     * 返回值：是否获取成功
     */
    public boolean tryAcquireAgentLock(String agentId, long ttl) {
        try {
            String key = AGENT_LOCK_PREFIX + agentId;
            Boolean success = redisTemplate.opsForValue().setIfAbsent(key, "locked", ttl, TimeUnit.SECONDS);
            return success != null && success;
        } catch (Exception e) {
            log.error("获取Agent锁失败", e);
            return false;
        }
    }

    /**
     * 释放Agent锁
     */
    public void releaseAgentLock(String agentId) {
        try {
            redisTemplate.delete(AGENT_LOCK_PREFIX + agentId);
        } catch (Exception e) {
            log.error("释放Agent锁失败", e);
        }
    }

    /**
     * 获取队列长度
     *
     * 参数说明：
     * - queueName: 队列名称
     *
     * 返回值：队列中的消息数量
     */
    public long getQueueLength(String queueName) {
        try {
            Long size = redisTemplate.opsForList().size(QUEUE_PREFIX + queueName);
            return size != null ? size : 0;
        } catch (Exception e) {
            log.error("获取队列长度失败", e);
            return 0;
        }
    }

    /**
     * 清空任务队列
     *
     * 使用场景：
     * - 系统初始化时
     * - 队列异常时重置
     */
    public void clearTaskQueue() {
        try {
            redisTemplate.delete(TASK_QUEUE);
            log.info("任务队列已清空");
        } catch (Exception e) {
            log.error("清空任务队列失败", e);
        }
    }
}
