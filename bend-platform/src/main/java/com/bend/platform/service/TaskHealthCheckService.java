package com.bend.platform.service;

import com.bend.platform.entity.AgentInstance;
import com.bend.platform.repository.AgentInstanceMapper;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Service
@RequiredArgsConstructor
public class TaskHealthCheckService {

    private final AgentInstanceMapper agentInstanceMapper;
    private final TaskService taskService;

    private static final int HEARTBEAT_TIMEOUT_MINUTES = 5;
    private static final int TASK_STUCK_TIMEOUT_MINUTES = 30;

    @Scheduled(fixedRate = 60000)
    public void checkOfflineAgents() {
        List<AgentInstance> allAgents = agentInstanceMapper.selectList(null);

        for (AgentInstance agent : allAgents) {
            if ("online".equals(agent.getStatus())) {
                boolean isReallyOnline = AgentWebSocketEndpoint.isAgentOnline(agent.getAgentId());

                if (!isReallyOnline) {
                    log.warn("检测到Agent离线但状态仍为online - agentId: {}", agent.getAgentId());
                    agent.setStatus("offline");
                    agentInstanceMapper.updateById(agent);

                    taskService.reassignTasksFromOfflineAgent(agent.getAgentId());
                }
            }
        }
    }

    @Scheduled(fixedRate = 300000)
    public void checkStuckTasks() {
        List<com.bend.platform.entity.Task> stuckTasks = taskService.findStuckRunningTasks(TASK_STUCK_TIMEOUT_MINUTES);

        for (com.bend.platform.entity.Task task : stuckTasks) {
            log.warn("检测到卡住的任务 - taskId: {}, 运行时间: {}分钟", task.getId(), TASK_STUCK_TIMEOUT_MINUTES);

            String agentId = task.getTargetAgentId();
            if (agentId != null) {
                boolean isAgentOnline = AgentWebSocketEndpoint.isAgentOnline(agentId);
                if (!isAgentOnline) {
                    taskService.reassignTasksFromOfflineAgent(agentId);
                }
            }
        }
    }
}