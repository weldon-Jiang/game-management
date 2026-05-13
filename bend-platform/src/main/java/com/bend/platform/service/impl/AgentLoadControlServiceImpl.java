package com.bend.platform.service.impl;

import com.bend.platform.entity.AgentInstance;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.service.AgentLoadControlService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

@Service
public class AgentLoadControlServiceImpl implements AgentLoadControlService {

    private static final Logger log = LoggerFactory.getLogger(AgentLoadControlServiceImpl.class);
    private static final String AGENT_TASK_COUNT_PREFIX = "agent:task:count:";
    private static final int DEFAULT_MAX_CONCURRENT_TASKS = 5;

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    @Autowired
    private AgentInstanceMapper agentMapper;

    private final Map<String, String> localTaskCounts = new ConcurrentHashMap<>();
    private volatile boolean redisAvailable = true;

    @Override
    public boolean canAcceptTask(String agentId) {
        AgentInstance agent = agentMapper.selectByAgentId(agentId);
        if (agent == null || !"online".equals(agent.getStatus())) {
            return false;
        }
        int maxTasks = agent.getMaxConcurrentTasks() != null ? agent.getMaxConcurrentTasks() : DEFAULT_MAX_CONCURRENT_TASKS;
        int currentCount = getCurrentTaskCount(agentId);
        return currentCount < maxTasks;
    }

    @Override
    public void incrementTaskCount(String agentId, String taskId) {
        String key = AGENT_TASK_COUNT_PREFIX + agentId;
        if (redisTemplate != null && redisAvailable) {
            try {
                redisTemplate.opsForHash().increment(key, taskId, 1);
                return;
            } catch (Exception e) {
                log.warn("Redis increment failed, falling back to local map: {}", e.getMessage());
                redisAvailable = false;
            }
        }
        localTaskCounts.put(agentId + ":" + taskId, "1");
    }

    @Override
    public void decrementTaskCount(String agentId, String taskId) {
        String key = AGENT_TASK_COUNT_PREFIX + agentId;
        if (redisTemplate != null && redisAvailable) {
            try {
                redisTemplate.opsForHash().delete(key, taskId);
                return;
            } catch (Exception e) {
                log.warn("Redis delete failed, falling back to local map: {}", e.getMessage());
                redisAvailable = false;
            }
        }
        localTaskCounts.remove(agentId + ":" + taskId);
    }

    @Override
    public int getCurrentTaskCount(String agentId) {
        String key = AGENT_TASK_COUNT_PREFIX + agentId;
        if (redisTemplate != null && redisAvailable) {
            try {
                Long size = redisTemplate.opsForHash().size(key);
                return size != null ? size.intValue() : 0;
            } catch (Exception e) {
                log.warn("Redis get size failed, falling back to local map: {}", e.getMessage());
                redisAvailable = false;
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
            int currentCount = getCurrentTaskCount(agentId);
            agent.setMaxConcurrentTasks(currentCount);
        }
        return agent;
    }
}
