package com.bend.platform.websocket;

import com.bend.platform.config.AgentWebSocketConfigurator;
import com.bend.platform.entity.AgentVersion;
import com.bend.platform.service.AgentInstanceService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import jakarta.annotation.PostConstruct;
import jakarta.websocket.*;
import jakarta.websocket.server.PathParam;
import jakarta.websocket.server.ServerEndpoint;
import org.springframework.context.ApplicationContext;

import java.io.IOException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Slf4j
@Component
@ServerEndpoint(value = "/ws/agents/{agentId}", configurator = AgentWebSocketConfigurator.class)
public class AgentWebSocketEndpoint {

    private static AgentInstanceService agentInstanceService;
    private static ApplicationContext applicationContext;

    public static void setApplicationContext(ApplicationContext context) {
        applicationContext = context;
    }

    @PostConstruct
    public void init() {
        if (applicationContext != null) {
            agentInstanceService = applicationContext.getBean(AgentInstanceService.class);
        }
    }

    private static final Map<String, Session> AGENT_SESSIONS = new ConcurrentHashMap<>();
    private static final Map<String, AtomicInteger> AGENT_RECONNECT_COUNT = new ConcurrentHashMap<>();
    private static final int MAX_RECONNECT_COUNT = 10;

    @OnOpen
    public void onOpen(Session session, @PathParam("agentId") String agentId) {
        log.info("Agent WebSocket连接请求 - AgentID: {}, SessionID: {}", agentId, session.getId());

        String agentSecret = getAuthToken(session);
        if (agentSecret == null) {
            log.warn("Agent认证失败 - AgentID: {}, 原因: 缺少认证信息", agentId);
            closeSession(session, 1008, "Authentication required");
            return;
        }

        if (!validateAgent(agentId, agentSecret)) {
            log.warn("Agent认证失败 - AgentID: {}, 原因: 无效的认证信息", agentId);
            closeSession(session, 1008, "Invalid credentials");
            return;
        }

        Session existingSession = AGENT_SESSIONS.get(agentId);
        if (existingSession != null && existingSession.isOpen()) {
            log.info("Agent重复连接 - AgentID: {}, 关闭旧连接", agentId);
            try {
                existingSession.close(new CloseReason(CloseReason.CloseCodes.NORMAL_CLOSURE, "Replaced by new connection"));
            } catch (IOException e) {
                log.error("关闭旧连接失败 - AgentID: {}", agentId, e);
            }
        }

        AGENT_SESSIONS.put(agentId, session);
        AGENT_RECONNECT_COUNT.remove(agentId);

        session.setMaxIdleTimeout(120000);

        Map<String, Object> connectedData = new HashMap<>();
        connectedData.put("agentId", agentId);
        connectedData.put("status", "connected");
        connectedData.put("message", "连接成功");
        sendMessage(session, "connected", connectedData);

        Map<String, Object> adminEventData = new HashMap<>();
        adminEventData.put("agentId", agentId);
        adminEventData.put("event", "online");
        broadcastToAdmins("agent_online", adminEventData);

        log.info("Agent连接成功 - AgentID: {}, 当前连接数: {}", agentId, AGENT_SESSIONS.size());
    }

    @OnMessage
    public void onMessage(String message, Session session, @PathParam("agentId") String agentId) {
        try {
            ObjectMapper mapper = new ObjectMapper();
            JsonNode json = mapper.readTree(message);
            String type = json.get("type").asText();
            JsonNode data = json.get("data");

            log.debug("收到Agent消息 - AgentID: {}, Type: {}", agentId, type);

            if ("heartbeat".equals(type)) {
                handleHeartbeat(agentId, data);
            } else if ("task_result".equals(type)) {
                handleTaskResult(agentId, data);
            } else if ("status_report".equals(type)) {
                handleStatusReport(agentId, data);
            } else if ("log".equals(type)) {
                handleAgentLog(agentId, data);
            } else {
                log.warn("未知消息类型 - AgentID: {}, Type: {}", agentId, type);
            }

        } catch (Exception e) {
            log.error("处理Agent消息失败 - AgentID: {}, Error: {}", agentId, e.getMessage());
        }
    }

    @OnClose
    public void onClose(Session session, @PathParam("agentId") String agentId) {
        AGENT_SESSIONS.remove(agentId);
        log.info("Agent连接关闭 - AgentID: {}, 当前连接数: {}", agentId, AGENT_SESSIONS.size());

        Map<String, Object> adminEventData = new HashMap<>();
        adminEventData.put("agentId", agentId);
        adminEventData.put("event", "offline");
        broadcastToAdmins("agent_offline", adminEventData);
    }

    @OnError
    public void onError(Session session, @PathParam("agentId") String agentId, Throwable error) {
        log.error("Agent WebSocket错误 - AgentID: {}", agentId, error);
        AGENT_SESSIONS.remove(agentId);
    }

    private String getAuthToken(Session session) {
        Map<String, List<String>> params = session.getRequestParameterMap();
        if (params.containsKey("agentSecret")) {
            return params.get("agentSecret").get(0);
        }
        return null;
    }

    private boolean validateAgent(String agentId, String agentSecret) {
        try {
            if (agentInstanceService == null) {
                log.warn("AgentInstanceService未初始化");
                return false;
            }
            return agentInstanceService.validateCredentials(agentId, agentSecret);
        } catch (Exception e) {
            log.error("验证Agent失败 - AgentID: {}", agentId, e);
            return false;
        }
    }

    private void closeSession(Session session, int code, String reason) {
        try {
            session.close(new CloseReason(CloseReason.CloseCodes.getCloseCode(code), reason));
        } catch (IOException e) {
            log.error("关闭连接失败", e);
        }
    }

    public static void sendMessage(Session session, String type, Map<String, Object> data) {
        if (session == null || !session.isOpen()) {
            return;
        }
        try {
            Map<String, Object> message = new HashMap<>();
            message.put("type", type);
            message.put("data", data);
            message.put("timestamp", System.currentTimeMillis());

            ObjectMapper mapper = new ObjectMapper();
            session.getBasicRemote().sendText(mapper.writeValueAsString(message));
        } catch (Exception e) {
            log.error("发送消息失败 - SessionID: {}", session.getId(), e);
        }
    }

    public static void sendMessageToAgent(String agentId, String type, Map<String, Object> data) {
        Session session = AGENT_SESSIONS.get(agentId);
        sendMessage(session, type, data);
    }

    public static void sendTaskToAgent(String agentId, String taskId, Map<String, Object> taskData) {
        Map<String, Object> data = new HashMap<>();
        data.put("taskId", taskId);
        data.put("task", taskData);
        sendMessageToAgent(agentId, "task", data);
    }

    public static void sendVersionUpdate(String agentId, AgentVersion version) {
        Map<String, Object> data = new HashMap<>();
        data.put("version", version.getVersion());
        data.put("downloadUrl", version.getDownloadUrl() != null ? version.getDownloadUrl() : "");
        data.put("md5Checksum", version.getMd5Checksum() != null ? version.getMd5Checksum() : "");
        data.put("changelog", version.getChangelog() != null ? version.getChangelog() : "");
        data.put("mandatory", version.getMandatory() != null && version.getMandatory() == 1);
        data.put("forceRestart", version.getForceRestart() != null && version.getForceRestart() == 1);
        data.put("timestamp", System.currentTimeMillis());
        sendMessageToAgent(agentId, "version_update", data);
        log.info("发送版本更新通知 - AgentID: {}, 版本: {}", agentId, version.getVersion());
    }

    public static void broadcastToAdmins(String type, Map<String, Object> data) {
        log.debug("广播给管理员 - Type: {}, Data: {}", type, data);
        if (applicationContext != null) {
            try {
                WebSocketMessageService messageService = applicationContext.getBean(WebSocketMessageService.class);
                messageService.broadcastToAdmins(type, data);
            } catch (Exception e) {
                log.error("广播消息给管理员失败", e);
            }
        }
    }

    public static boolean isAgentOnline(String agentId) {
        Session session = AGENT_SESSIONS.get(agentId);
        return session != null && session.isOpen();
    }

    public static int getOnlineAgentCount() {
        return AGENT_SESSIONS.size();
    }

    public static Map<String, Session> getOnlineAgents() {
        return new ConcurrentHashMap<>(AGENT_SESSIONS);
    }

    private void handleHeartbeat(String agentId, JsonNode data) {
        try {
            String status = data.has("status") ? data.get("status").asText() : null;
            String currentTaskId = data.has("currentTaskId") ? data.get("currentTaskId").asText() : null;
            String currentStreamingId = data.has("currentStreamingId") ? data.get("currentStreamingId").asText() : null;
            String version = data.has("version") ? data.get("version").asText() : null;

            if (agentInstanceService != null) {
                agentInstanceService.updateHeartbeat(agentId, status, currentTaskId, currentStreamingId, version);
            }

            Session session = AGENT_SESSIONS.get(agentId);
            if (session != null && session.isOpen()) {
                Map<String, Object> ackData = new HashMap<>();
                ackData.put("timestamp", System.currentTimeMillis());
                sendMessage(session, "heartbeat_ack", ackData);
            }

            log.debug("Agent心跳 - AgentID: {}, Status: {}", agentId, status);
        } catch (Exception e) {
            log.error("处理心跳失败 - AgentID: {}", agentId, e);
        }
    }

    private void handleTaskResult(String agentId, JsonNode data) {
        log.info("Agent任务结果 - AgentID: {}, Data: {}", agentId, data);
        Map<String, Object> adminData = new HashMap<>();
        adminData.put("agentId", agentId);
        adminData.put("data", data.toString());
        broadcastToAdmins("task_result", adminData);
    }

    private void handleStatusReport(String agentId, JsonNode data) {
        log.debug("Agent状态报告 - AgentID: {}, Data: {}", agentId, data);
        Map<String, Object> adminData = new HashMap<>();
        adminData.put("agentId", agentId);
        adminData.put("data", data.toString());
        broadcastToAdmins("status_report", adminData);
    }

    private void handleAgentLog(String agentId, JsonNode data) {
        log.debug("Agent日志 - AgentID: {}, Data: {}", agentId, data);
    }
}
