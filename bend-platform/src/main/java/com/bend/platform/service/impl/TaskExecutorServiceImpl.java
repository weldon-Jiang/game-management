package com.bend.platform.service.impl;

import com.bend.platform.dto.LoginUserInfo;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.AgentLoadControlService;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.TaskExecutorService;
import com.bend.platform.service.TaskGameAccountStatusService;
import com.bend.platform.util.DebugSessionLog;
import com.bend.platform.util.UserContext;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.CompletableFuture;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@Slf4j
@Service
public class TaskExecutorServiceImpl implements TaskExecutorService {

    private static final ExecutorService taskExecutor = Executors.newCachedThreadPool();

    @Autowired
    private TaskMapper taskMapper;

    @Autowired
    private GameAccountService gameAccountService;

    @Autowired
    private TaskGameAccountStatusService statusService;

    @Autowired
    private AgentLoadControlService loadControlService;

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Override
    public CompletableFuture<Void> executeTaskAsync(Task task) {
        LoginUserInfo userInfo = UserContext.getUserInfo();
        if (userInfo == null && task.getMerchantId() != null) {
            userInfo = LoginUserInfo.builder()
                    .merchantId(task.getMerchantId())
                    .userId(task.getCreatedBy())
                    .role("merchant_owner")
                    .build();
        }
        final LoginUserInfo contextUser = userInfo;
        return CompletableFuture.runAsync(() -> {
            try {
                if (contextUser != null) {
                    UserContext.setUserInfo(contextUser);
                }
                // #region agent log
                DebugSessionLog.log("H1", "TaskExecutorServiceImpl.executeTaskAsync", "async_user_context",
                        Map.of("taskId", task.getId(),
                                "hasContext", contextUser != null,
                                "merchantId", contextUser != null ? String.valueOf(contextUser.getMerchantId()) : "null",
                                "role", contextUser != null ? String.valueOf(contextUser.getRole()) : "null"));
                // #endregion
                executeTask(task);
            } finally {
                UserContext.clear();
            }
        }, taskExecutor);
    }

    @Override
    public void executeTask(Task task) {
        String agentId = task.getTargetAgentId();
        try {
            if (!loadControlService.canAcceptTask(agentId)) {
                task.setStatus("pending");
                task.setErrorMessage("Agent is at maximum capacity, task queued");
                taskMapper.updateById(task);
                return;
            }

            boolean agentOnline = AgentWebSocketEndpoint.isAgentOnline(agentId);
            // #region agent log
            DebugSessionLog.log("H2", "TaskExecutorServiceImpl.executeTask", "agent_online_check",
                    Map.of("taskId", task.getId(), "agentId", agentId, "online", agentOnline));
            // #endregion
            if (!agentOnline) {
                failTask(task, "Agent is offline or WebSocket not connected");
                return;
            }

            List<GameAccount> boundAccounts = gameAccountService.findByStreamingId(task.getStreamingAccountId());
            GameAccountSelection selection = resolveGameAccountsForTask(task, boundAccounts);
            // #region agent log
            DebugSessionLog.log("H3", "TaskExecutorServiceImpl.executeTask", "game_account_selection",
                    Map.of("taskId", task.getId(), "selectedCount", selection.ids.size(),
                            "boundActiveCount", selectionFromBoundAccounts(boundAccounts).ids.size()));
            // #endregion

            task.setStatus("running");
            task.setStartedTime(LocalDateTime.now());
            taskMapper.updateById(task);

            loadControlService.incrementTaskCount(agentId, task.getId());

            statusService.createStatusRecords(
                    task.getId(), selection.ids, selection.dailyLimits,
                    task.getStreamingAccountId(), task.getSessionId());

            ObjectNode taskData = buildTaskData(task, selection);
            Map<String, Object> taskDataMap = objectMapper.convertValue(
                    taskData, new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {});

            log.info("准备发送任务到Agent - TaskID: {}, AgentID: {}, GameAccountCount: {}",
                    task.getId(), agentId, selection.ids.size());

            boolean sent = AgentWebSocketEndpoint.sendTaskToAgent(agentId, task.getId(), taskDataMap);
            // #region agent log
            DebugSessionLog.log("H2", "TaskExecutorServiceImpl.executeTask", "ws_send_result",
                    Map.of("taskId", task.getId(), "agentId", agentId, "sent", sent));
            // #endregion

            if (!sent) {
                loadControlService.decrementTaskCount(agentId, task.getId());
                failTask(task, "Failed to deliver task to agent via WebSocket");
                return;
            }

            log.info("任务已发送到Agent - TaskID: {}, AgentID: {}, GameAccountCount: {}",
                    task.getId(), agentId, selection.ids.size());

        } catch (Exception e) {
            log.error("Failed to execute task {}: {}", task.getId(), e.getMessage(), e);
            if (agentId != null) {
                loadControlService.decrementTaskCount(agentId, task.getId());
            }
            failTask(task, e.getMessage());
        }
    }

    private void failTask(Task task, String message) {
        task.setStatus("failed");
        task.setErrorMessage(message);
        task.setCompletedTime(LocalDateTime.now());
        taskMapper.updateById(task);
    }

    /**
     * Prefer gameAccounts embedded in task.params (automation selected subset).
     */
    private GameAccountSelection resolveGameAccountsForTask(Task task, List<GameAccount> boundAccounts)
            throws Exception {
        if (task.getParams() != null) {
            JsonNode params = objectMapper.readTree(task.getParams());
            JsonNode gas = params.get("gameAccounts");
            if (gas != null && gas.isArray() && !gas.isEmpty()) {
                List<String> ids = new ArrayList<>();
                List<Integer> limits = new ArrayList<>();
                for (JsonNode ga : gas) {
                    String id = null;
                    if (ga.hasNonNull("id")) {
                        id = ga.get("id").asText();
                    } else if (ga.hasNonNull("gameAccountId")) {
                        id = ga.get("gameAccountId").asText();
                    }
                    if (id == null || id.isEmpty()) {
                        continue;
                    }
                    ids.add(id);
                    if (ga.has("dailyMatchLimit") && !ga.get("dailyMatchLimit").isNull()) {
                        limits.add(ga.get("dailyMatchLimit").asInt(3));
                    } else {
                        GameAccount entity = gameAccountService.findById(id);
                        limits.add(entity != null && entity.getDailyMatchLimit() != null
                                ? entity.getDailyMatchLimit() : 3);
                    }
                }
                if (!ids.isEmpty()) {
                    return new GameAccountSelection(ids, limits);
                }
            }
        }
        return selectionFromBoundAccounts(boundAccounts);
    }

    private GameAccountSelection selectionFromBoundAccounts(List<GameAccount> gameAccounts) {
        List<String> ids = new ArrayList<>();
        List<Integer> limits = new ArrayList<>();
        for (GameAccount ga : gameAccounts) {
            if (Boolean.TRUE.equals(ga.getIsActive())) {
                ids.add(ga.getId());
                limits.add(ga.getDailyMatchLimit() != null ? ga.getDailyMatchLimit() : 3);
            }
        }
        return new GameAccountSelection(ids, limits);
    }

    @Override
    public void cancelTask(String taskId) {
        Task task = taskMapper.selectById(taskId);
        if (task != null && "running".equals(task.getStatus())) {
            task.setStatus("cancelled");
            task.setCompletedTime(LocalDateTime.now());
            taskMapper.updateById(task);

            loadControlService.decrementTaskCount(task.getTargetAgentId(), taskId);

            List<TaskGameAccountStatus> statuses = statusService.findByTaskId(taskId);
            for (TaskGameAccountStatus status : statuses) {
                if ("pending".equals(status.getStatus()) || "running".equals(status.getStatus())) {
                    statusService.updateStatus(taskId, status.getGameAccountId(), "cancelled");
                }
            }

            log.info("任务已取消 - TaskID: {}, AgentID: {} (WS 由 TaskControl 下发)",
                    taskId, task.getTargetAgentId());
        }
    }

    private ObjectNode buildTaskData(Task task, GameAccountSelection selection) throws Exception {
        ObjectNode taskData = objectMapper.createObjectNode();
        taskData.put("taskId", task.getId());
        taskData.put("type", task.getType());
        taskData.put("streamingAccountId", task.getStreamingAccountId());
        if (Boolean.TRUE.equals(task.getGameActionPending())) {
            taskData.put("phase", "streaming_only");
        } else if (task.getGameActionType() != null && !task.getGameActionType().isEmpty()) {
            taskData.put("gameActionType", task.getGameActionType());
        }
        if (task.getSessionId() != null) {
            taskData.put("sessionId", task.getSessionId());
        }

        com.fasterxml.jackson.databind.node.ArrayNode gameAccountList = objectMapper.createArrayNode();
        for (String gameAccountId : selection.ids) {
            GameAccount ga = gameAccountService.findById(gameAccountId);
            if (ga == null || !Boolean.TRUE.equals(ga.getIsActive())) {
                continue;
            }
            ObjectNode gaInfo = objectMapper.createObjectNode();
            gaInfo.put("gameAccountId", ga.getId());
            gaInfo.put("gameName", ga.getGameName());
            gaInfo.put("email", ga.getEmail());
            gaInfo.put("isPrimary", ga.getIsPrimary());
            gaInfo.put("priority", ga.getPriority());
            gaInfo.put("dailyMatchLimit", ga.getDailyMatchLimit());
            gaInfo.put("todayMatchCount", ga.getTodayMatchCount());
            gaInfo.put("cooldownHours", ga.getCooldownHours());
            gaInfo.put("totalCoins", ga.getTotalCoins());
            gaInfo.put("todayCoins", ga.getTodayCoins());
            gaInfo.put("drLevel", ga.getDrLevel());
            gameAccountList.add(gaInfo);
        }
        taskData.set("gameAccounts", gameAccountList);

        if (task.getParams() != null) {
            try {
                JsonNode params = objectMapper.readTree(task.getParams());
                if (params.isObject()) {
                    ObjectNode finalTaskData = taskData;
                    params.fields().forEachRemaining(entry -> finalTaskData.set(entry.getKey(), entry.getValue()));
                }
            } catch (Exception e) {
                log.warn("Failed to parse task params: {}", e.getMessage());
            }
        }

        return taskData;
    }

    private record GameAccountSelection(List<String> ids, List<Integer> dailyLimits) {}
}
