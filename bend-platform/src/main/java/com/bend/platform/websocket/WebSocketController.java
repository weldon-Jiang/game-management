package com.bend.platform.websocket;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.service.AgentInstanceService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.messaging.handler.annotation.MessageMapping;
import org.springframework.messaging.handler.annotation.Payload;
import org.springframework.messaging.simp.SimpMessageHeaderAccessor;
import org.springframework.stereotype.Controller;

import java.util.Map;

@Slf4j
@Controller
@RequiredArgsConstructor
public class WebSocketController {

    private final WebSocketMessageService messageService;
    private final AgentInstanceService agentInstanceService;

    @MessageMapping("/agent/heartbeat")
    public void agentHeartbeat(SimpMessageHeaderAccessor headerAccessor, @Payload Map<String, Object> data) {
        String agentId = (String) data.get("agentId");
        log.debug("收到Agent心跳 - AgentID: {}", agentId);
    }

    @MessageMapping("/admin/broadcast")
    public void broadcastToAgents(SimpMessageHeaderAccessor headerAccessor, @Payload Map<String, Object> data) {
        String agentId = (String) data.get("agentId");
        String type = (String) data.get("type");
        Map<String, Object> payload = (Map<String, Object>) data.get("data");

        if (agentId != null && "all".equals(agentId)) {
            log.info("广播消息给所有Agent - Type: {}", type);
        } else if (agentId != null) {
            messageService.sendToAgent(agentId, type, payload);
            log.info("发送消息给Agent - AgentID: {}, Type: {}", agentId, type);
        }
    }

    @MessageMapping("/admin/sendTask")
    public ApiResponse<Void> sendTaskToAgent(SimpMessageHeaderAccessor headerAccessor, @Payload Map<String, Object> data) {
        String agentId = (String) data.get("agentId");
        String taskId = (String) data.get("taskId");
        Map<String, Object> taskData = (Map<String, Object>) data.get("taskData");

        if (agentId == null || taskId == null) {
            return ApiResponse.error(400, "缺少必要参数");
        }

        if (!messageService.isAgentOnline(agentId)) {
            return ApiResponse.error(400, "Agent不在线");
        }

        messageService.sendTaskToAgent(agentId, taskId, taskData);
        return ApiResponse.success("任务已下发", null);
    }

    @MessageMapping("/admin/onlineAgents")
    public ApiResponse<Object> getOnlineAgents(SimpMessageHeaderAccessor headerAccessor) {
        int count = messageService.getOnlineAgentCount();
        Map<String, Object> result = new java.util.HashMap<>();
        result.put("count", count);
        return ApiResponse.success(result);
    }
}
