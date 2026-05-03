package com.bend.platform.task;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class AgentHeartbeatChecker {

    private final AgentInstanceMapper agentInstanceMapper;

    @Value("${agent.heartbeat_timeout:120}")
    private int heartbeatTimeoutSeconds;

    @Scheduled(fixedRateString = "${agent.heartbeat_check_interval:30000}")
    public void checkAgentHeartbeat() {
        log.debug("Running agent heartbeat check...");

        try {
            LocalDateTime threshold = LocalDateTime.now().minusSeconds(heartbeatTimeoutSeconds);

            LambdaQueryWrapper<AgentInstance> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(AgentInstance::getStatus, "online")
                    .lt(AgentInstance::getLastHeartbeat, threshold);

            List<AgentInstance> staleAgents = agentInstanceMapper.selectList(wrapper);

            for (AgentInstance agent : staleAgents) {
                handleStaleAgent(agent);
            }

            if (!staleAgents.isEmpty()) {
                log.info("Marked {} agents as offline due to heartbeat timeout", staleAgents.size());
            }
        } catch (Exception e) {
            log.error("Error during agent heartbeat check", e);
        }
    }

    private void handleStaleAgent(AgentInstance agent) {
        String agentId = agent.getAgentId();

        if (AgentWebSocketEndpoint.isAgentOnline(agentId)) {
            log.debug("Agent {} is actually online (WebSocket connected), skipping", agentId);
            return;
        }

        agent.setStatus("offline");
        agent.setUpdatedTime(LocalDateTime.now());
        agentInstanceMapper.updateById(agent);

        log.warn("Agent marked as offline - ID: {}, Last Heartbeat: {}",
                agentId, agent.getLastHeartbeat());
    }
}
