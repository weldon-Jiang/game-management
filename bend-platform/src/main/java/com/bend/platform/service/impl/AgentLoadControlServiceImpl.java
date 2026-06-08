package com.bend.platform.service.impl;

import com.bend.platform.entity.AgentInstance;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.service.AgentLoadControlService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Agent 并发负载控制：Redis Hash 按 taskId 计数；Redis 短暂不可用时降级本地 Map，并定期探测恢复。
 */
@Service
public class AgentLoadControlServiceImpl implements AgentLoadControlService {

    private static final Logger log = LoggerFactory.getLogger(AgentLoadControlServiceImpl.class);
    private static final String AGENT_TASK_COUNT_PREFIX = "agent:task:count:";
    private static final String REDIS_PROBE_KEY = "agent:load:redis_probe";
    private static final int DEFAULT_MAX_CONCURRENT_TASKS = 5;

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    @Autowired
    private AgentInstanceMapper agentMapper;

    private final Map<String, String> localTaskCounts = new ConcurrentHashMap<>();
    private volatile boolean redisAvailable = true;
    private volatile long lastRedisProbeMs = 0L;

    @Override
    public boolean canAcceptTask(String agentId) {
        AgentInstance agent = agentMapper.selectByAgentId(agentId);
        if (agent == null || !"online".equals(agent.getStatus())) {
            return false;
        }
        int maxTasks = agent.getMaxConcurrentTasks() != null
                ? agent.getMaxConcurrentTasks()
                : DEFAULT_MAX_CONCURRENT_TASKS;
        int currentCount = getCurrentTaskCount(agentId);
        return currentCount < maxTasks;
    }

    @Override
    public void incrementTaskCount(String agentId, String taskId) {
        if (useRedis()) {
            try {
                String key = AGENT_TASK_COUNT_PREFIX + agentId;
                redisTemplate.opsForHash().increment(key, taskId, 1);
                return;
            } catch (Exception e) {
                markRedisUnavailable("increment", e);
            }
        }
        localTaskCounts.put(agentId + ":" + taskId, "1");
    }

    @Override
    public void decrementTaskCount(String agentId, String taskId) {
        if (useRedis()) {
            try {
                String key = AGENT_TASK_COUNT_PREFIX + agentId;
                redisTemplate.opsForHash().delete(key, taskId);
                return;
            } catch (Exception e) {
                markRedisUnavailable("decrement", e);
            }
        }
        localTaskCounts.remove(agentId + ":" + taskId);
    }

    @Override
    public int getCurrentTaskCount(String agentId) {
        if (useRedis()) {
            try {
                String key = AGENT_TASK_COUNT_PREFIX + agentId;
                Long size = redisTemplate.opsForHash().size(key);
                return size != null ? size.intValue() : 0;
            } catch (Exception e) {
                markRedisUnavailable("get size", e);
            }
        }
        return (int) localTaskCounts.keySet().stream()
                .filter(k -> k.startsWith(agentId + ":"))
                .count();
    }

    @Override
    public AgentInstance getAgentWithLoadInfo(String agentId) {
        AgentInstance agent = agentMapper.selectByAgentId(agentId);
        if (agent != null) {
            agent.setCurrentTaskCount(getCurrentTaskCount(agentId));
        }
        return agent;
    }

    /** 每 60s 探测 Redis，恢复后重新走 Redis 计数路径。 */
    @Scheduled(fixedRateString = "${agent.load_control.redis_probe_interval:60000}")
    public void probeRedisAvailability() {
        if (redisTemplate == null) {
            redisAvailable = false;
            return;
        }
        try {
            redisTemplate.opsForValue().set(REDIS_PROBE_KEY, "1");
            redisTemplate.delete(REDIS_PROBE_KEY);
            if (!redisAvailable) {
                log.info("AgentLoadControl Redis 已恢复，切换回 Redis 计数");
            }
            redisAvailable = true;
            lastRedisProbeMs = System.currentTimeMillis();
        } catch (Exception e) {
            if (redisAvailable) {
                log.warn("AgentLoadControl Redis 探测失败，降级本地计数: {}", e.getMessage());
            }
            redisAvailable = false;
        }
    }

    private boolean useRedis() {
        return redisTemplate != null && redisAvailable;
    }

    private void markRedisUnavailable(String operation, Exception e) {
        log.warn("Redis {} failed, falling back to local map: {}", operation, e.getMessage());
        redisAvailable = false;
    }
}
