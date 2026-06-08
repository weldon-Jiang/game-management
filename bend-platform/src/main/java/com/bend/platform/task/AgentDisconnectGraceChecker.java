package com.bend.platform.task;

import com.bend.platform.service.AgentDisconnectGraceService;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.service.TaskService;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 定时检查 Agent WS 断线宽限期：仅当 WS 与 HTTP 心跳均超时后才清理未完成任务。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class AgentDisconnectGraceChecker {

    private final AgentDisconnectGraceService disconnectGraceService;
    private final TaskService taskService;
    private final StreamingAccountService streamingAccountService;
    private final AgentInstanceService agentInstanceService;

    @Scheduled(fixedRateString = "${agent.disconnect_check_interval:30000}")
    public void checkDisconnectedAgents() {
        List<String> ready = disconnectGraceService.findAgentsReadyForCleanup();
        for (String agentId : ready) {
            performOfflineCleanup(agentId);
        }
    }

    private void performOfflineCleanup(String agentId) {
        log.warn("Agent 宽限期结束，执行离线清理 - AgentID: {}", agentId);

        try {
            streamingAccountService.clearAgentBindingByAgentId(agentId);
        } catch (Exception e) {
            log.error("清理流媒体账号绑定失败 - AgentID: {}", agentId, e);
        }

        try {
            taskService.cleanupIncompleteTasksAndRestoreAccounts(agentId);
        } catch (Exception e) {
            log.error("清理未完成任务失败 - AgentID: {}", agentId, e);
        }

        try {
            agentInstanceService.updateHeartbeat(agentId, "offline", null, null, null);
        } catch (Exception e) {
            log.error("更新 Agent 离线状态失败 - AgentID: {}", agentId, e);
        }

        disconnectGraceService.clearOnWsReconnect(agentId);

        Map<String, Object> adminEventData = new HashMap<>();
        adminEventData.put("agentId", agentId);
        adminEventData.put("event", "offline");
        AgentWebSocketEndpoint.broadcastToAdmins("agent_offline", adminEventData);
    }
}
