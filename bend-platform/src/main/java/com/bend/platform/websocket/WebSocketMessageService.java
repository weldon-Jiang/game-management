package com.bend.platform.websocket;

import com.bend.platform.service.AgentInstanceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.simp.SimpMessagingTemplate;
import org.springframework.stereotype.Service;

import java.util.Map;

@Slf4j
@Service
@RequiredArgsConstructor
public class WebSocketMessageService {

    private final SimpMessagingTemplate messagingTemplate;
    private final AgentInstanceService agentInstanceService;

    public void broadcastToAdmins(String destination, Map<String, Object> payload) {
        try {
            messagingTemplate.convertAndSend("/topic/admins/" + destination, payload);
            log.debug("广播消息给管理员 - Destination: {}", destination);
        } catch (Exception e) {
            log.error("广播消息失败 - Destination: {}", destination, e);
        }
    }

    public void sendToAgent(String agentId, String type, Map<String, Object> data) {
        try {
            AgentWebSocketEndpoint.sendMessageToAgent(agentId, type, data);
            log.debug("发送消息给Agent - AgentID: {}, Type: {}", agentId, type);
        } catch (Exception e) {
            log.error("发送消息给Agent失败 - AgentID: {}, Type: {}", agentId, type, e);
        }
    }

    public void sendTaskToAgent(String agentId, String taskId, Map<String, Object> taskData) {
        try {
            AgentWebSocketEndpoint.sendTaskToAgent(agentId, taskId, taskData);
            log.info("下发任务给Agent - AgentID: {}, TaskID: {}", agentId, taskId);
        } catch (Exception e) {
            log.error("下发任务失败 - AgentID: {}, TaskID: {}", agentId, taskId, e);
        }
    }

    public boolean isAgentOnline(String agentId) {
        return AgentWebSocketEndpoint.isAgentOnline(agentId);
    }

    public int getOnlineAgentCount() {
        return AgentWebSocketEndpoint.getOnlineAgentCount();
    }
}
