package com.bend.platform.service.impl;

import com.bend.platform.entity.AgentInstance;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.service.AgentDisconnectGraceService;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.stereotype.Service;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Agent WS 断线宽限期：Redis 记录断线时刻，不可用时降级内存 Map。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class AgentDisconnectGraceServiceImpl implements AgentDisconnectGraceService {

    private static final String DISCONNECT_KEY_PREFIX = "agent:ws_disconnect:";

    private final AgentInstanceMapper agentInstanceMapper;

    @Autowired(required = false)
    private StringRedisTemplate redisTemplate;

    @Value("${agent.disconnect_grace_seconds:180}")
    private int disconnectGraceSeconds;

    @Value("${agent.heartbeat_timeout:120}")
    private int heartbeatTimeoutSeconds;

    private final Map<String, Long> localDisconnectAt = new ConcurrentHashMap<>();

    @Override
    public void markWsDisconnected(String agentId) {
        long now = System.currentTimeMillis();
        storeDisconnectTime(agentId, now);

        AgentInstance instance = agentInstanceMapper.selectByAgentId(agentId);
        if (instance != null && !"uninstalled".equals(instance.getStatus())) {
            instance.setStatus("reconnecting");
            instance.setUpdatedTime(LocalDateTime.now());
            agentInstanceMapper.updateById(instance);
        }
        log.info("Agent WS 断开，进入宽限期 - AgentID: {}, grace={}s", agentId, disconnectGraceSeconds);
    }

    @Override
    public void clearOnWsReconnect(String agentId) {
        removeDisconnectTime(agentId);
        log.debug("Agent WS 重连，清除宽限期 - AgentID: {}", agentId);
    }

    @Override
    public List<String> findAgentsReadyForCleanup() {
        List<String> ready = new ArrayList<>();
        LocalDateTime heartbeatCutoff = LocalDateTime.now().minusSeconds(heartbeatTimeoutSeconds);
        long graceCutoff = System.currentTimeMillis() - disconnectGraceSeconds * 1000L;

        for (String agentId : listDisconnectedAgents()) {
            if (AgentWebSocketEndpoint.isAgentOnline(agentId)) {
                clearOnWsReconnect(agentId);
                continue;
            }

            Long disconnectedAt = getDisconnectTime(agentId);
            if (disconnectedAt == null || disconnectedAt > graceCutoff) {
                continue;
            }

            AgentInstance instance = agentInstanceMapper.selectByAgentId(agentId);
            if (instance == null) {
                removeDisconnectTime(agentId);
                continue;
            }

            if (instance.getLastHeartbeat() != null && instance.getLastHeartbeat().isAfter(heartbeatCutoff)) {
                continue;
            }

            ready.add(agentId);
        }
        return ready;
    }

    private void storeDisconnectTime(String agentId, long epochMs) {
        String key = DISCONNECT_KEY_PREFIX + agentId;
        if (redisTemplate != null) {
            try {
                redisTemplate.opsForValue().set(
                        key,
                        String.valueOf(epochMs),
                        Duration.ofSeconds(disconnectGraceSeconds + heartbeatTimeoutSeconds + 60L));
                localDisconnectAt.remove(agentId);
                return;
            } catch (Exception e) {
                log.warn("Redis 记录 Agent 断线失败，降级内存 - AgentID: {}", agentId, e);
            }
        }
        localDisconnectAt.put(agentId, epochMs);
    }

    private void removeDisconnectTime(String agentId) {
        if (redisTemplate != null) {
            try {
                redisTemplate.delete(DISCONNECT_KEY_PREFIX + agentId);
            } catch (Exception e) {
                log.warn("Redis 清除 Agent 断线标记失败 - AgentID: {}", agentId, e);
            }
        }
        localDisconnectAt.remove(agentId);
    }

    private Long getDisconnectTime(String agentId) {
        if (redisTemplate != null) {
            try {
                String value = redisTemplate.opsForValue().get(DISCONNECT_KEY_PREFIX + agentId);
                if (value != null) {
                    return Long.parseLong(value);
                }
            } catch (Exception e) {
                log.warn("Redis 读取 Agent 断线时刻失败 - AgentID: {}", agentId, e);
            }
        }
        return localDisconnectAt.get(agentId);
    }

    private List<String> listDisconnectedAgents() {
        List<String> agentIds = new ArrayList<>(localDisconnectAt.keySet());
        if (redisTemplate != null) {
            try {
                var keys = redisTemplate.keys(DISCONNECT_KEY_PREFIX + "*");
                if (keys != null) {
                    for (String key : keys) {
                        String agentId = key.substring(DISCONNECT_KEY_PREFIX.length());
                        if (!agentIds.contains(agentId)) {
                            agentIds.add(agentId);
                        }
                    }
                }
            } catch (Exception e) {
                log.warn("Redis 枚举 Agent 断线标记失败", e);
            }
        }
        return agentIds;
    }
}
