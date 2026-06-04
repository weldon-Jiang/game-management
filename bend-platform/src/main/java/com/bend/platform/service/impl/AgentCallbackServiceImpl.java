package com.bend.platform.service.impl;

import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.AgentCallbackService;
import com.bend.platform.service.AgentLoadControlService;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.service.TaskGameAccountStatusService;
import com.bend.platform.service.TaskService;
import com.bend.platform.service.XboxHostService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

import jakarta.servlet.http.HttpServletRequest;
import java.time.LocalDateTime;
import java.util.*;

@Slf4j
@Service
@RequiredArgsConstructor
public class AgentCallbackServiceImpl implements AgentCallbackService {

    private final TaskService taskService;
    private final GameAccountService gameAccountService;
    private final TaskMapper taskMapper;
    private final TaskGameAccountStatusService statusService;
    private final AgentLoadControlService loadControlService;
    private final StreamingAccountService streamingAccountService;
    private final XboxHostService xboxHostService;

    @Override
    public Map<String, Object> reportProgress(Map<String, Object> payload) {
        log.info("【v2.0】统一进度上报 - Payload: {}", payload);

        String taskId = (String) payload.get("taskId");

        @SuppressWarnings("unchecked")
        Map<String, Object> data = (Map<String, Object>) payload.get("data");
        if (data == null) {
            throw new BusinessException(400, "data字段不能为空");
        }

        String step = (String) data.get("step");
        String status = (String) data.get("status");
        String message = (String) data.get("message");
        String gameAccountId = (String) data.get("gameAccountId");

        @SuppressWarnings("unchecked")
        Map<String, Object> metrics = (Map<String, Object>) data.get("metrics");
        @SuppressWarnings("unchecked")
        Map<String, Object> error = (Map<String, Object>) data.get("error");

        if (taskId == null || status == null) {
            throw new BusinessException(400, "taskId和status为必需字段");
        }

        Task task = requireTaskForAuthenticatedAgent(taskId);

        Map<String, Object> response = new HashMap<>();
        response.put("received", true);

        switch (status) {
            case "RUNNING":
                handleRunningStatus(task, taskId, step, message, gameAccountId, metrics, response);
                break;
            case "COMPLETED":
                handleCompletedStatus(task, taskId, step, message, gameAccountId, metrics, response);
                break;
            case "FAILED":
                handleFailedStatus(task, taskId, step, message, gameAccountId, metrics, error, response);
                break;
            case "GAME_PREPARING":
                handleGamePreparingStatus(task, taskId, step, gameAccountId, metrics);
                break;
            case "GAMING":
                handleGamingStatus(task, taskId, step, gameAccountId, metrics);
                break;
            case "CANCELLED":
                handleCancelledStatus(task, taskId, message, response);
                break;
            default:
                log.warn("未知状态 - Status: {}", status);
        }

        return response;
    }

    private void handleRunningStatus(Task task, String taskId, String step, String message,
                                     String gameAccountId, Map<String, Object> metrics,
                                     Map<String, Object> response) {
        if ("pending".equals(task.getStatus())) {
            task.setStatus("running");
            task.setStartedTime(LocalDateTime.now());
        }

        if (step != null) {
            task.setCurrentStep(step);
        }
        if (message != null) {
            task.setProgressMessage(message);
        }
        task.setStepStatus("RUNNING");

        if (gameAccountId != null) {
            statusService.updateStatus(taskId, gameAccountId, "running");
            updateMetrics(taskId, gameAccountId, metrics);
        }

        taskMapper.updateById(task);
        response.put("action", "CONTINUE");
        log.info("任务运行中 - TaskID: {}, Step: {}", taskId, step);
    }

    private void handleCompletedStatus(Task task, String taskId, String step, String message,
                                        String gameAccountId, Map<String, Object> metrics,
                                        Map<String, Object> response) {
        if (step != null) {
            task.setCurrentStep(step);
        }
        if (message != null) {
            task.setProgressMessage(message);
        }
        task.setStepStatus("COMPLETED");

        if (gameAccountId != null) {
            statusService.updateStatus(taskId, gameAccountId, "completed");
            updateMetrics(taskId, gameAccountId, metrics);
        }

        boolean allCompleted = statusService.areAllGameAccountsCompleted(taskId);

        if (allCompleted) {
            task.setStatus("completed");
            task.setCompletedTime(LocalDateTime.now());
            task.setResult(message);
            loadControlService.decrementTaskCount(task.getTargetAgentId(), taskId);
            clearStreamingAccountBinding(task);
            response.put("action", "STOP");
            log.info("所有游戏账号完成 - TaskID: {}", taskId);
        } else {
            response.put("action", "CONTINUE");
            log.info("游戏账号完成，继续下一账号 - TaskID: {}, GameAccountID: {}", taskId, gameAccountId);
        }

        taskMapper.updateById(task);
    }

    private void handleFailedStatus(Task task, String taskId, String step, String message,
                                     String gameAccountId, Map<String, Object> metrics,
                                     Map<String, Object> error, Map<String, Object> response) {
        task.setStatus("failed");
        task.setStepStatus("FAILED");

        if (step != null) {
            task.setCurrentStep(step);
        }
        if (message != null) {
            task.setProgressMessage(message);
            task.setErrorMessage(message);
        }

        if (error != null) {
            String errorCode = (String) error.get("code");
            String errorDetails = (String) error.get("details");
            log.error("任务失败 - TaskID: {}, ErrorCode: {}, ErrorDetails: {}", taskId, errorCode, errorDetails);
        }

        if (gameAccountId != null) {
            statusService.updateStatus(taskId, gameAccountId, "failed");
            updateMetrics(taskId, gameAccountId, metrics);
        }

        clearStreamingAccountBinding(task);
        loadControlService.decrementTaskCount(task.getTargetAgentId(), taskId);
        taskMapper.updateById(task);

        response.put("action", "STOP");
        log.info("任务失败 - TaskID: {}, Message: {}", taskId, message);
    }

    private void handleGamePreparingStatus(Task task, String taskId, String step,
                                            String gameAccountId, Map<String, Object> metrics) {
        if (step != null) {
            task.setCurrentStep(step);
        }
        task.setStepStatus("GAME_PREPARING");

        if (gameAccountId != null) {
            statusService.updateStatus(taskId, gameAccountId, "game_preparing");
            updateMetrics(taskId, gameAccountId, metrics);
        }

        taskMapper.updateById(task);
        log.info("游戏准备中 - TaskID: {}, GameAccountID: {}", taskId, gameAccountId);
    }

    private void handleGamingStatus(Task task, String taskId, String step,
                                     String gameAccountId, Map<String, Object> metrics) {
        if (step != null) {
            task.setCurrentStep(step);
        }
        task.setStepStatus("GAMING");

        if (gameAccountId != null) {
            statusService.updateStatus(taskId, gameAccountId, "gaming");
            updateMetrics(taskId, gameAccountId, metrics);
        }

        taskMapper.updateById(task);
        log.info("游戏进行中 - TaskID: {}, GameAccountID: {}", taskId, gameAccountId);
    }

    private void handleCancelledStatus(Task task, String taskId, String message,
                                        Map<String, Object> response) {
        task.setStatus("cancelled");
        task.setStepStatus("CANCELLED");
        if (message != null) {
            task.setProgressMessage(message);
        }

        clearStreamingAccountBinding(task);
        loadControlService.decrementTaskCount(task.getTargetAgentId(), taskId);
        taskMapper.updateById(task);

        response.put("action", "STOP");
        log.info("任务取消 - TaskID: {}", taskId);
    }

    private void updateMetrics(String taskId, String gameAccountId, Map<String, Object> metrics) {
        if (metrics == null) return;

        Integer todayCompleted = metrics.get("todayCompleted") != null
                ? ((Number) metrics.get("todayCompleted")).intValue()
                : null;
        Integer dailyLimit = metrics.get("dailyLimit") != null
                ? ((Number) metrics.get("dailyLimit")).intValue()
                : null;
        Integer failedCount = metrics.get("failedCount") != null
                ? ((Number) metrics.get("failedCount")).intValue()
                : null;

        if (todayCompleted != null || dailyLimit != null || failedCount != null) {
            statusService.updateDailyMatchInfo(taskId, gameAccountId, todayCompleted, dailyLimit);
        }
    }

    private void clearStreamingAccountBinding(Task task) {
        if (task.getStreamingAccountId() != null) {
            streamingAccountService.updateAgentId(task.getStreamingAccountId(), null);
            streamingAccountService.updateTaskStatus(task.getStreamingAccountId(), "idle");
            List<GameAccount> gameAccounts = gameAccountService.findByStreamingId(task.getStreamingAccountId());
            for (GameAccount gameAccount : gameAccounts) {
                gameAccountService.updateStatus(gameAccount.getId(), "idle");
                gameAccountService.updateAgentId(gameAccount.getId(), null);
            }
        }
    }

    private Task findTaskForAgentCallback(String taskId) {
        return taskMapper.selectById(taskId);
    }

    /**
     * 加载任务并校验其 targetAgentId 与当前 HTTP 认证的 Agent 一致。
     */
    private Task requireTaskForAuthenticatedAgent(String taskId) {
        Task task = findTaskForAgentCallback(taskId);
        if (task == null) {
            throw new BusinessException(ResultCode.System.DATA_NOT_FOUND, "任务不存在");
        }
        String authenticatedAgentId = getAuthenticatedAgentId();
        if (authenticatedAgentId != null
                && task.getTargetAgentId() != null
                && !authenticatedAgentId.equals(task.getTargetAgentId())) {
            log.warn("Agent 无权操作任务 - AgentID: {}, TaskID: {}, TargetAgent: {}",
                    authenticatedAgentId, taskId, task.getTargetAgentId());
            throw new BusinessException(403, "任务不属于当前 Agent");
        }
        return task;
    }

    private String getAuthenticatedAgentId() {
        try {
            ServletRequestAttributes attrs =
                    (ServletRequestAttributes) RequestContextHolder.getRequestAttributes();
            if (attrs == null) {
                return null;
            }
            HttpServletRequest request = attrs.getRequest();
            Object agentId = request.getAttribute("agentId");
            return agentId != null ? agentId.toString() : null;
        } catch (Exception e) {
            log.debug("无法读取认证 AgentId: {}", e.getMessage());
            return null;
        }
    }

    @Override
    public Map<String, Object> getTaskInfo(String taskId) {
        log.info("【v2.0】获取任务信息 - TaskID: {}", taskId);

        Task task = requireTaskForAuthenticatedAgent(taskId);

        Map<String, Object> result = new HashMap<>();
        result.put("taskId", task.getId());
        result.put("taskType", task.getType());
        result.put("gameActionType", task.getGameActionType());
        result.put("createdAt", task.getCreatedTime());

        // 获取流媒体账号信息
        if (task.getStreamingAccountId() != null) {
            var streamingAccount = streamingAccountService.findById(task.getStreamingAccountId());
            if (streamingAccount != null) {
                Map<String, Object> streamingInfo = new HashMap<>();
                streamingInfo.put("id", streamingAccount.getId());
                streamingInfo.put("email", streamingAccount.getEmail());
                streamingInfo.put("name", streamingAccount.getName());
                result.put("streamingAccount", streamingInfo);
            }
        }

        // 获取游戏账号列表
        List<TaskGameAccountStatus> statuses = statusService.findByTaskId(taskId);
        List<Map<String, Object>> gameAccounts = new ArrayList<>();
        for (TaskGameAccountStatus status : statuses) {
            GameAccount ga = gameAccountService.findById(status.getGameAccountId());
            if (ga != null) {
                Map<String, Object> gaInfo = new HashMap<>();
                gaInfo.put("id", ga.getId());
                gaInfo.put("gamertag", ga.getGameName());
                gaInfo.put("dailyMatchLimit", ga.getDailyMatchLimit());
                gameAccounts.add(gaInfo);
            }
        }
        result.put("gameAccounts", gameAccounts);

        return result;
    }

    @Override
    public Map<String, Object> lockXboxHost(String xboxHostId, Map<String, Object> payload) {
        log.info("【v2.0】锁定Xbox主机 - XboxHostID: {}", xboxHostId);

        XboxHost host = xboxHostService.findById(xboxHostId);
        if (host == null) {
            throw new BusinessException(ResultCode.System.DATA_NOT_FOUND, "Xbox主机不存在");
        }

        String taskId = payload != null ? (String) payload.get("taskId") : null;
        if (taskId != null) {
            requireTaskForAuthenticatedAgent(taskId);
        }

        boolean locked = xboxHostService.lock(xboxHostId, taskId);

        Map<String, Object> result = new HashMap<>();
        result.put("locked", locked);

        if (locked) {
            result.put("expiresAt", System.currentTimeMillis() + 3600000);
            log.info("Xbox主机锁定成功 - XboxHostID: {}", xboxHostId);
        } else {
            log.warn("Xbox主机锁定失败 - XboxHostID: {}, 原因: 已被其他Agent锁定", xboxHostId);
        }

        return result;
    }

    @Override
    public Map<String, Object> unlockXboxHost(String xboxHostId, Map<String, Object> payload) {
        log.info("【v2.0】解锁Xbox主机 - XboxHostID: {}", xboxHostId);

        XboxHost host = xboxHostService.findById(xboxHostId);
        if (host == null) {
            throw new BusinessException(ResultCode.System.DATA_NOT_FOUND, "Xbox主机不存在");
        }

        boolean unlocked = xboxHostService.unlock(xboxHostId);

        Map<String, Object> result = new HashMap<>();
        result.put("unlocked", unlocked);

        if (unlocked) {
            log.info("Xbox主机解锁成功 - XboxHostID: {}", xboxHostId);
        } else {
            log.warn("Xbox主机解锁失败 - XboxHostID: {}", xboxHostId);
        }

        return result;
    }

    @Override
    public Map<String, Object> getXboxHostStatus(String xboxHostId) {
        log.info("【v2.0】查询Xbox主机状态 - XboxHostID: {}", xboxHostId);

        XboxHost host = xboxHostService.findById(xboxHostId);
        if (host == null) {
            throw new BusinessException(ResultCode.System.DATA_NOT_FOUND, "Xbox主机不存在");
        }

        Map<String, Object> result = new HashMap<>();
        result.put("id", host.getId());
        result.put("xboxId", host.getXboxId());  // 修正字段名（原为 deviceId）
        result.put("name", host.getName());
        result.put("ipAddress", host.getIpAddress());
        result.put("port", host.getPort());
        result.put("liveId", host.getLiveId());
        result.put("consoleType", host.getConsoleType());
        result.put("firmwareVersion", host.getFirmwareVersion());
        result.put("macAddress", host.getMacAddress());
        result.put("status", host.getStatus());
        result.put("locked", host.getLocked() != null && host.getLocked());  // 添加 locked 布尔字段
        result.put("lockedByAgentId", host.getLockedByAgentId());
        result.put("lockExpiresTime", host.getLockExpiresTime());
        result.put("boundStreamingAccountId", host.getBoundStreamingAccountId());
        result.put("boundGamertag", host.getBoundGamertag());
        result.put("lastSeenTime", host.getLastSeenTime());

        return result;
    }

    @Override
    public Map<String, Object> exchangeCredential(Map<String, Object> payload) {
        String token = (String) payload.get("token");
        if (token == null || token.isEmpty()) {
            throw new BusinessException(400, "token不能为空");
        }

        log.info("【v2.0】凭证兑换 - Token: {}", token.substring(0, Math.min(10, token.length())) + "...");

        if (token.startsWith("DISABLED:")) {
            throw new BusinessException(503, "Redis未启用，凭证功能不可用");
        }

        String credential = xboxHostService.getAndInvalidateCredential(token);
        if (credential == null) {
            throw new BusinessException(ResultCode.System.DATA_NOT_FOUND, "令牌不存在或已过期");
        }

        Map<String, Object> result = new HashMap<>();
        result.put("credential", credential);

        return result;
    }

    @Override
    public void reportTaskStatusLegacy(String taskId, Map<String, String> payload) {
        log.warn("【deprecated】使用旧接口 reportTaskStatus，请迁移至 /api/v1/agent-callback/progress");

        String status = payload.get("status");
        String message = payload.get("message");

        requireTaskForAuthenticatedAgent(taskId);

        taskService.updateStatus(taskId, status);

        Map<String, Object> newPayload = new HashMap<>();
        newPayload.put("taskId", taskId);
        newPayload.put("data", Map.of(
                "status", status,
                "message", message != null ? message : "",
                "deprecated", true
        ));

        reportProgress(newPayload);
    }

    @Override
    public void updateGameAccountStatusLegacy(String taskId, String gameAccountId, Map<String, Object> payload) {
        log.warn("【deprecated】使用旧接口 updateGameAccountStatus，请迁移至 /api/v1/agent-callback/progress");

        String status = (String) payload.get("status");
        Integer todayCompleted = payload.get("todayCompleted") != null
                ? ((Number) payload.get("todayCompleted")).intValue()
                : null;
        Integer dailyLimit = payload.get("dailyLimit") != null
                ? ((Number) payload.get("dailyLimit")).intValue()
                : null;

        requireTaskForAuthenticatedAgent(taskId);

        statusService.updateStatus(taskId, gameAccountId, status);

        if (todayCompleted != null || dailyLimit != null) {
            statusService.updateDailyMatchInfo(taskId, gameAccountId, todayCompleted, dailyLimit);
        }

        Map<String, Object> newPayload = new HashMap<>();
        newPayload.put("taskId", taskId);
        newPayload.put("data", Map.of(
                "status", status,
                "gameAccountId", gameAccountId,
                "metrics", Map.of(
                        "todayCompleted", todayCompleted != null ? todayCompleted : 0,
                        "dailyLimit", dailyLimit != null ? dailyLimit : 0
                ),
                "deprecated", true
        ));

        reportProgress(newPayload);
    }

    @Override
    public List<Map<String, Object>> getGameAccountsStatusLegacy(String taskId) {
        log.warn("【deprecated】使用旧接口 getGameAccountsStatus，请迁移至 /api/v1/agent-callback/task/{taskId}");

        Task task = requireTaskForAuthenticatedAgent(taskId);

        String streamingAccountId = task.getStreamingAccountId();
        if (streamingAccountId == null) {
            throw new BusinessException(400, "任务未关联串流账号");
        }

        Map<String, GameAccount> gameAccountMap = new HashMap<>();
        List<GameAccount> allGameAccounts = gameAccountService.findByStreamingId(streamingAccountId);
        for (GameAccount ga : allGameAccounts) {
            gameAccountMap.put(ga.getId(), ga);
        }

        List<TaskGameAccountStatus> taskStatuses = statusService.findByTaskId(taskId);
        List<Map<String, Object>> statusList = new ArrayList<>();

        if (!taskStatuses.isEmpty()) {
            for (TaskGameAccountStatus ts : taskStatuses) {
                Map<String, Object> status = new HashMap<>();
                status.put("id", ts.getGameAccountId());

                GameAccount ga = gameAccountMap.get(ts.getGameAccountId());
                status.put("gamertag", ga != null ? ga.getGameName() : "");

                status.put("todayCompleted", ts.getCompletedCount());
                status.put("dailyLimit", ts.getTotalMatches());
                status.put("completed", "completed".equals(ts.getStatus()));
                status.put("deprecated", true);

                statusList.add(status);
            }
        }

        return statusList;
    }
}
