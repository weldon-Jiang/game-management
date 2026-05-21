package com.bend.platform.service.impl;

import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.AgentLoadControlService;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.TaskExecutorService;
import com.bend.platform.service.TaskGameAccountStatusService;
import com.bend.platform.websocket.AgentWebSocketEndpoint;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;

import java.util.HashMap;
import java.util.Map;

import lombok.extern.slf4j.Slf4j;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
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
        return CompletableFuture.runAsync(() -> executeTask(task), taskExecutor);
    }

    @Override
    public void executeTask(Task task) {
        try {
            if (!loadControlService.canAcceptTask(task.getTargetAgentId())) {
                task.setStatus("pending");
                task.setErrorMessage("Agent is at maximum capacity, task queued");
                taskMapper.updateById(task);
                return;
            }

            task.setStatus("running");
            task.setStartedTime(LocalDateTime.now());
            taskMapper.updateById(task);

            loadControlService.incrementTaskCount(task.getTargetAgentId(), task.getId());

            List<GameAccount> gameAccounts = gameAccountService.findByStreamingId(task.getStreamingAccountId());
            List<String> gameAccountIds = new ArrayList<>();
            for (GameAccount ga : gameAccounts) {
                if (Boolean.TRUE.equals(ga.getIsActive())) {
                    gameAccountIds.add(ga.getId());
                }
            }

            List<Integer> dailyLimits = new ArrayList<>();
            for (GameAccount ga : gameAccounts) {
                if (Boolean.TRUE.equals(ga.getIsActive())) {
                    dailyLimits.add(ga.getDailyMatchLimit() != null ? ga.getDailyMatchLimit() : 3);
                }
            }
            
            statusService.createStatusRecords(task.getId(), gameAccountIds, dailyLimits, task.getStreamingAccountId());

            ObjectNode taskData = buildTaskData(task, gameAccounts);
            Map<String, Object> taskDataMap = objectMapper.convertValue(taskData, new com.fasterxml.jackson.core.type.TypeReference<Map<String, Object>>() {});
            
            log.info("准备发送任务到Agent - TaskID: {}, AgentID: {}, GameAccountCount: {}", 
                task.getId(), task.getTargetAgentId(), gameAccountIds.size());
            
            AgentWebSocketEndpoint.sendTaskToAgent(task.getTargetAgentId(), task.getId(), taskDataMap);

            log.info("任务已发送到Agent - TaskID: {}, AgentID: {}, GameAccountCount: {}",
                task.getId(), task.getTargetAgentId(), gameAccountIds.size());

        } catch (Exception e) {
            log.error("Failed to execute task {}: {}", task.getId(), e.getMessage(), e);
            task.setStatus("failed");
            task.setErrorMessage(e.getMessage());
            task.setCompletedTime(LocalDateTime.now());
            taskMapper.updateById(task);
        }
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

            AgentWebSocketEndpoint.sendCancelTaskToAgent(task.getTargetAgentId(), taskId);
            log.info("任务已取消并通知Agent - TaskID: {}, AgentID: {}", taskId, task.getTargetAgentId());
        }
    }

    private ObjectNode buildTaskData(Task task, List<GameAccount> gameAccounts) throws Exception {
        ObjectNode taskData = objectMapper.createObjectNode();
        taskData.put("taskId", task.getId());
        taskData.put("type", task.getType());
        taskData.put("streamingAccountId", task.getStreamingAccountId());

        com.fasterxml.jackson.databind.node.ArrayNode gameAccountList = objectMapper.createArrayNode();
        for (GameAccount ga : gameAccounts) {
            if (Boolean.TRUE.equals(ga.getIsActive())) {
                ObjectNode gaInfo = objectMapper.createObjectNode();
                gaInfo.put("gameAccountId", ga.getId());
                gaInfo.put("xboxGameName", ga.getXboxGameName());
                gaInfo.put("xboxLiveEmail", ga.getXboxLiveEmail());
                gaInfo.put("isPrimary", ga.getIsPrimary());
                gaInfo.put("priority", ga.getPriority());
                gaInfo.put("dailyMatchLimit", ga.getDailyMatchLimit());
                gaInfo.put("todayMatchCount", ga.getTodayMatchCount());
                gameAccountList.add(gaInfo);
            }
        }
        taskData.set("gameAccounts", gameAccountList);

        if (task.getParams() != null) {
            try {
                com.fasterxml.jackson.databind.JsonNode params = objectMapper.readTree(task.getParams());
                if (params.isObject()) {
                    final ObjectNode finalTaskData = taskData;
                    ((ObjectNode) params).fields().forEachRemaining(entry -> {
                        finalTaskData.set(entry.getKey(), entry.getValue());
                    });
                }
            } catch (Exception e) {
                log.warn("Failed to parse task params: {}", e.getMessage());
            }
        }

        return taskData;
    }
}
