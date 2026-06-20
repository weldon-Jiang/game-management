package com.bend.platform.websocket;

import com.bend.platform.config.AgentWebSocketConfigurator;
import com.bend.platform.util.AgentAuthUtils;
import com.bend.platform.entity.AgentInstance;
import com.bend.platform.entity.AgentVersion;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.service.AgentDisconnectGraceService;
import com.bend.platform.service.AgentInstanceService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.service.TaskService;
import com.bend.platform.service.XboxHostService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import jakarta.annotation.PostConstruct;
import jakarta.websocket.*;
import jakarta.websocket.server.PathParam;
import jakarta.websocket.server.ServerEndpoint;
import org.springframework.context.ApplicationContext;

import java.io.IOException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicInteger;

@Slf4j
@Component
@ServerEndpoint(value = "/ws/agent/{agentId}", configurator = AgentWebSocketConfigurator.class)
public class AgentWebSocketEndpoint {

    private static AgentInstanceService agentInstanceService;
    private static XboxHostService xboxHostService;
    private static TaskService taskService;
    private static StreamingAccountService streamingAccountService;
    private static ApplicationContext applicationContext;

    public static void setApplicationContext(ApplicationContext context) {
        applicationContext = context;
    }

    @PostConstruct
    public void init() {
        if (applicationContext != null) {
            agentInstanceService = applicationContext.getBean(AgentInstanceService.class);
            xboxHostService = applicationContext.getBean(XboxHostService.class);
            taskService = applicationContext.getBean(TaskService.class);
            streamingAccountService = applicationContext.getBean(StreamingAccountService.class);
        }
    }

    private static final Map<String, Session> AGENT_SESSIONS = new ConcurrentHashMap<>();
    private static final Map<String, AtomicInteger> AGENT_RECONNECT_COUNT = new ConcurrentHashMap<>();
    private static final int MAX_RECONNECT_COUNT = 10;

    private static void ensureServicesInitialized() {
        if (applicationContext != null && agentInstanceService == null) {
            agentInstanceService = applicationContext.getBean(AgentInstanceService.class);
        }
        if (applicationContext != null && xboxHostService == null) {
            xboxHostService = applicationContext.getBean(XboxHostService.class);
        }
        if (applicationContext != null && taskService == null) {
            taskService = applicationContext.getBean(TaskService.class);
        }
    }

    private static long getWsMaxIdleTimeoutMs() {
        if (applicationContext == null) {
            return 180_000L;
        }
        Long timeout = applicationContext.getEnvironment()
                .getProperty("agent.ws_max_idle_timeout_ms", Long.class, 180_000L);
        return timeout != null ? timeout : 180_000L;
    }

    private static AgentDisconnectGraceService getDisconnectGraceService() {
        if (applicationContext == null) {
            return null;
        }
        try {
            return applicationContext.getBean(AgentDisconnectGraceService.class);
        } catch (Exception e) {
            log.warn("AgentDisconnectGraceService 未就绪", e);
            return null;
        }
    }

    @OnOpen
    public void onOpen(Session session, @PathParam("agentId") String agentId) {
        log.info("Agent WebSocket连接请求 - AgentID: {}, SessionID: {}", agentId, session.getId());

        ensureServicesInitialized();

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

        AgentDisconnectGraceService graceService = getDisconnectGraceService();
        if (graceService != null) {
            graceService.clearOnWsReconnect(agentId);
        }

        if (agentInstanceService != null) {
            agentInstanceService.updateHeartbeat(agentId, "online", null, null, null);
        }

        session.setMaxIdleTimeout(getWsMaxIdleTimeoutMs());

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
            log.info("收到Agent消息 - AgentID: {}, Message长度: {}, Message: {}", agentId, message.length(), message);
            
            ObjectMapper mapper = new ObjectMapper();
            JsonNode json = mapper.readTree(message);
            JsonNode typeNode = json.get("type");
            if (typeNode == null) {
                log.warn("Agent消息缺少type字段 - AgentID: {}, Message: {}", agentId, message);
                return;
            }
            String type = typeNode.asText();
            JsonNode data = json.get("data");

            log.info("解析Agent消息成功 - AgentID: {}, Type: {}", agentId, type);

            if ("heartbeat".equals(type)) {
                handleHeartbeat(agentId, data);
            } else if ("task_result".equals(type)) {
                handleTaskResult(agentId, data);
            } else if ("status_report".equals(type)) {
                handleStatusReport(agentId, data);
            } else if ("task_progress".equals(type)) {
                handleTaskProgress(agentId, data);
            } else if ("log".equals(type)) {
                handleAgentLog(agentId, data);
            } else if ("xbox_discovered".equals(type)) {
                handleXboxDiscovered(agentId, data);
            } else if ("task_control_ack".equals(type)) {
                handleTaskControlAck(agentId, data);
            } else {
                log.warn("未知消息类型 - AgentID: {}, Type: {}", agentId, type);
            }

        } catch (Exception e) {
            log.error("处理Agent消息失败 - AgentID: {}, Error: {}", agentId, e.getMessage());
        }
    }

    @OnClose
    public void onClose(Session session, @PathParam("agentId") String agentId, CloseReason closeReason) {
        Session currentSession = AGENT_SESSIONS.get(agentId);
        if (currentSession != null && !currentSession.getId().equals(session.getId())) {
            log.info("忽略旧Agent连接关闭 - AgentID: {}, ClosedSessionID: {}, CurrentSessionID: {}, Reason: {}",
                    agentId, session.getId(), currentSession.getId(),
                    closeReason != null ? closeReason.getReasonPhrase() : "");
            return;
        }

        AGENT_SESSIONS.remove(agentId, session);
        String reason = closeReason != null ? closeReason.getReasonPhrase() : "";
        log.info("Agent连接关闭 - AgentID: {}, Reason: {}, 当前连接数: {}",
                agentId, reason, AGENT_SESSIONS.size());

        if ("Replaced by new connection".equals(reason)) {
            log.info("Agent连接被新连接替换，跳过离线清理 - AgentID: {}", agentId);
            return;
        }

        // 进入断线宽限期：闪断不立即清理任务，由 AgentDisconnectGraceChecker 在超时后处理
        AgentDisconnectGraceService graceService = getDisconnectGraceService();
        if (graceService != null) {
            graceService.markWsDisconnected(agentId);
        }

        Map<String, Object> adminEventData = new HashMap<>();
        adminEventData.put("agentId", agentId);
        adminEventData.put("event", "reconnecting");
        broadcastToAdmins("agent_reconnecting", adminEventData);
    }

    @OnError
    public void onError(Session session, @PathParam("agentId") String agentId, Throwable error) {
        log.error("Agent WebSocket错误 - AgentID: {}", agentId, error);
        AGENT_SESSIONS.remove(agentId);
    }

    @SuppressWarnings("unchecked")
    private String getAuthToken(Session session) {
        // Prefer header (Base64) over query string to avoid secrets in URLs/logs
        Object headersObj = session.getUserProperties().get(AgentWebSocketConfigurator.HANDSHAKE_HEADERS_KEY);
        if (headersObj instanceof Map<?, ?> headers) {
            for (String headerName : List.of("X-Agent-Secret", "x-agent-secret")) {
                Object values = headers.get(headerName);
                if (values instanceof List<?> secretList && !secretList.isEmpty()) {
                    Object first = secretList.get(0);
                    if (first instanceof String encoded && !encoded.isEmpty()) {
                        return AgentAuthUtils.decodeSecretHeader(encoded);
                    }
                }
            }
        }

        Map<String, List<String>> params = session.getRequestParameterMap();
        if (params.containsKey("agentSecret")) {
            return params.get("agentSecret").get(0);
        }
        return null;
    }

    private boolean validateAgent(String agentId, String agentSecret) {
        try {
            ensureServicesInitialized();
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

    public static boolean sendTaskToAgent(String agentId, String taskId, Map<String, Object> taskData) {
        Session session = AGENT_SESSIONS.get(agentId);
        if (session == null || !session.isOpen()) {
            log.warn("Agent不在线，任务未下发 - AgentID: {}, TaskID: {}", agentId, taskId);
            return false;
        }
        sendMessage(session, "task", taskData);
        return true;
    }

    public static void sendCancelTaskToAgent(String agentId, String taskId) {
        Map<String, Object> data = new HashMap<>();
        data.put("taskId", taskId);
        sendMessageToAgent(agentId, "cancel_task", data);
        log.info("发送任务取消指令 - AgentID: {}, TaskID: {}", agentId, taskId);
    }

    public static boolean sendTaskControlToAgent(String agentId, Map<String, Object> data) {
        if (data == null || !data.containsKey("taskId")) {
            log.warn("task_control 拒绝下发：缺少 taskId - AgentID: {}", agentId);
            return false;
        }
        Session session = AGENT_SESSIONS.get(agentId);
        if (session == null || !session.isOpen()) {
            log.warn("Agent不在线，task_control 未下发 - AgentID: {}", agentId);
            return false;
        }
        sendMessage(session, "task_control", data);
        log.info("发送 task_control - AgentID: {}, TaskID: {}, action: {}",
                agentId, data.get("taskId"), data.get("action"));
        return true;
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

    public static void sendDiscoverXbox(String agentId) {
        Map<String, Object> data = new HashMap<>();
        data.put("timestamp", System.currentTimeMillis());
        sendMessageToAgent(agentId, "discover_xbox", data);
        log.info("发送Xbox发现指令 - AgentID: {}", agentId);
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

    /**
     * 检查Agent是否可用（WebSocket连接已建立或最近有心跳）
     */
    public static boolean isAgentAvailable(String agentId) {
        // 首先检查WebSocket连接
        if (isAgentOnline(agentId)) {
            return true;
        }
        return false;
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

            ensureServicesInitialized();
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

    /**
     * Agent 对 task_control 的异步应答；内存无任务时清理平台孤儿任务，避免详情页控制按钮失效。
     */
    private void handleTaskControlAck(String agentId, JsonNode data) {
        if (data == null) {
            return;
        }
        boolean failed = data.has("success") && !data.get("success").asBoolean(true);
        if (!failed) {
            return;
        }
        String error = data.has("error") ? data.get("error").asText("") : "";
        String taskId = data.has("taskId") ? data.get("taskId").asText("") : "";
        if (!error.contains("Unknown taskId") || taskId.isBlank()) {
            return;
        }
        ensureServicesInitialized();
        if (taskService == null) {
            log.warn("task_control_ack 孤儿清理跳过：TaskService 未就绪 - AgentID: {}, TaskID: {}", agentId, taskId);
            return;
        }
        try {
            taskService.failOrphanTaskOnAgent(agentId, taskId);
        } catch (Exception e) {
            log.error("处理 task_control_ack 孤儿任务失败 - AgentID: {}, TaskID: {}", agentId, taskId, e);
        }
    }

    private void handleStatusReport(String agentId, JsonNode data) {
        log.debug("Agent状态报告 - AgentID: {}, Data: {}", agentId, data);
        Map<String, Object> adminData = new HashMap<>();
        adminData.put("agentId", agentId);
        adminData.put("data", data.toString());
        broadcastToAdmins("status_report", adminData);
    }

    private void handleTaskProgress(String agentId, JsonNode data) {
        try {
            String taskId = data.has("taskId") ? data.get("taskId").asText() : null;
            String step = data.has("step") ? data.get("step").asText() : null;
            String status = data.has("status") ? data.get("status").asText() : null;
            String message = data.has("message") ? data.get("message").asText() : null;
            JsonNode extraData = data.has("extra_data") ? data.get("extra_data") : null;

            log.info("Agent任务进度 - AgentID: {}, TaskID: {}, Step: {}, Status: {}, Message: {}",
                    agentId, taskId, step, status, message);

            Map<String, Object> adminData = new HashMap<>();
            adminData.put("agentId", agentId);
            adminData.put("taskId", taskId);
            adminData.put("step", step);
            adminData.put("status", status);
            adminData.put("message", message);
            adminData.put("extraData", extraData != null ? extraData.toString() : null);
            adminData.put("timestamp", System.currentTimeMillis());

            broadcastToAdmins("task_progress", adminData);

        } catch (Exception e) {
            log.error("处理任务进度失败 - AgentID: {}, Error: {}", agentId, e.getMessage());
        }
    }

    private void handleAgentLog(String agentId, JsonNode data) {
        log.debug("Agent日志 - AgentID: {}, Data: {}", agentId, data);
    }

    private void handleXboxDiscovered(String agentId, JsonNode data) {
        try {
            log.info("========== 开始处理Xbox发现消息 ==========");
            log.info("Agent发现Xbox主机 - AgentID: {}, Data: {}", agentId, data);

            ensureServicesInitialized();
            log.info("服务初始化完成");
            
            AgentInstance agent = agentInstanceService.findByAgentId(agentId);
            if (agent == null) {
                log.warn("Agent实例不存在 - AgentID: {}", agentId);
                return;
            }
            log.info("找到Agent实例 - MerchantID: {}", agent.getMerchantId());

            String merchantId = agent.getMerchantId();
            int discoveredCount = 0;
            List<Map<String, Object>> discoveredXboxes = new ArrayList<>();

            if (data.has("xboxes") && data.get("xboxes").isArray()) {
                JsonNode xboxes = data.get("xboxes");
                discoveredCount = xboxes.size();
                
                for (JsonNode xbox : xboxes) {
                    String xboxId = xbox.has("device_id") ? xbox.get("device_id").asText() : null;
                    String name = xbox.has("name") ? xbox.get("name").asText() : null;
                    String ipAddress = xbox.has("ip_address") ? xbox.get("ip_address").asText() : null;
                    Integer port = xbox.has("port") && !xbox.get("port").isNull() ? xbox.get("port").asInt() : null;
                    String liveId = xbox.has("live_id") ? xbox.get("live_id").asText() : null;
                    String consoleType = xbox.has("console_type") ? xbox.get("console_type").asText() : null;
                    String firmwareVersion = xbox.has("firmware_version") ? xbox.get("firmware_version").asText() : null;
                    String macAddress = xbox.has("mac_address") ? xbox.get("mac_address").asText() : null;

                    if (xboxId == null || xboxId.isEmpty()) {
                        log.warn("Xbox设备ID为空，跳过 - AgentID: {}", agentId);
                        continue;
                    }

                    if ("null".equals(name)) {
                        name = null;
                    }
                    if ("null".equals(liveId)) {
                        liveId = null;
                    }
                    if ("null".equals(consoleType)) {
                        consoleType = null;
                    }
                    if ("null".equals(firmwareVersion)) {
                        firmwareVersion = null;
                    }
                    if ("null".equals(macAddress)) {
                        macAddress = null;
                    }

                    XboxHost host = xboxHostService.createOrUpdate(merchantId, xboxId, name, ipAddress,
                            port, liveId, consoleType, firmwareVersion, macAddress, "xbox");
                    
                    Map<String, Object> xboxInfo = new HashMap<>();
                    xboxInfo.put("id", host.getId());
                    xboxInfo.put("deviceId", xboxId);
                    xboxInfo.put("name", name);
                    xboxInfo.put("ipAddress", ipAddress);
                    xboxInfo.put("status", host.getStatus());
                    discoveredXboxes.add(xboxInfo);
                    
                    log.info("Xbox主机已注册 - XboxID: {}, Name: {}, IP: {}", xboxId, name, ipAddress);
                }
            }

            if (discoveredCount == 0) {
                log.info("Agent未发现Xbox主机 - AgentID: {}", agentId);
            }

            Map<String, Object> adminData = new HashMap<>();
            adminData.put("agentId", agentId);
            String displayName = StringUtils.hasText(agent.getAgentName()) ? agent.getAgentName() : agent.getHost();
            adminData.put("agentName", displayName);
            adminData.put("merchantId", merchantId);
            adminData.put("discoveredCount", discoveredCount);
            adminData.put("xboxes", discoveredXboxes);
            adminData.put("timestamp", System.currentTimeMillis());
            adminData.put("message", discoveredCount > 0 
                ? String.format("成功发现 %d 台Xbox主机", discoveredCount) 
                : "未发现Xbox主机，请确保Xbox主机已开机并连接到同一网络");
            
            log.info("准备广播Xbox发现结果 - 发现数量: {}, 商户ID: {}", discoveredCount, merchantId);
            broadcastToAdmins("xbox_discovered", adminData);
            log.info("Xbox发现消息广播完成");

        } catch (Exception e) {
            log.error("处理Xbox发现消息失败 - AgentID: {}", agentId, e);
        }
    }
}
