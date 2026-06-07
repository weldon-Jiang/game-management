package com.bend.platform.service.impl;

import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskEvent;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import com.bend.platform.repository.TaskEventMapper;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.AgentCallbackService;
import com.bend.platform.service.AgentLoadControlService;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.service.StreamingSessionService;
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

/**
 * Agent 回调服务实现（平台侧的回调入口）。
 *
 * <p>处理 Agent 在执行四步骤过程中上报的统一进度（{@link #reportProgress}）以及 Xbox 主机锁定、
 * 凭证兑换、档案绑定回写等回调。进度按 {@code scope} 分流：session（会话阶段）、module
 * （账号开通）、game_account（单账号）以及任务级 status（RUNNING/COMPLETED/FAILED/GAMING 等），
 * 并据此推进任务状态机、更新游戏账号执行状态、在终态释放账号占用与 Agent 负载计数。</p>
 *
 * <p>所有回调均经 {@link #requireTaskForAuthenticatedAgent} 校验任务归属于当前认证的 Agent，
 * 防止跨 Agent 越权操作。响应中的 action 字段（CONTINUE/STOP）用于指示 Agent 后续行为。</p>
 */
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
    private final StreamingSessionService streamingSessionService;
    private final TaskEventMapper taskEventMapper;

    /**
     * 统一进度上报入口。
     *
     * <p>校验 taskId/status 必填与任务归属后，先落库一条任务事件，再按 scope 分流处理：
     * session/module/game_account 走各自处理器；否则按任务级 status 推进任务与游戏账号状态。
     * 返回体含 received 与 action（CONTINUE 继续 / STOP 结束）指示 Agent 后续行为。</p>
     *
     * @param payload 含 taskId 及嵌套 data（step/status/message/scope/metrics/error 等）
     * @return 处理结果，含 action 指令
     */
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
        String accountStatus = (String) data.get("accountStatus");

        @SuppressWarnings("unchecked")
        Map<String, Object> metrics = (Map<String, Object>) data.get("metrics");
        @SuppressWarnings("unchecked")
        Map<String, Object> error = (Map<String, Object>) data.get("error");

        if (taskId == null || status == null) {
            throw new BusinessException(400, "taskId和status为必需字段");
        }

        Task task = requireTaskForAuthenticatedAgent(taskId);

        String scope = (String) data.get("scope");
        recordTaskEvent(task, taskId, data, status, message, scope);

        if ("session".equals(scope)) {
            return handleSessionScope(task, taskId, data, status, message);
        }
        if ("module".equals(scope) && "account_provisioning".equals(data.get("module"))) {
            return handleProvisioningScope(taskId, data, status);
        }
        if ("game_account".equals(scope)) {
            return handleGameAccountScope(taskId, data, status);
        }

        Map<String, Object> response = new HashMap<>();
        response.put("received", true);

        switch (status) {
            case "RUNNING":
                handleRunningStatus(task, taskId, step, message, gameAccountId, accountStatus, metrics, response);
                break;
            case "COMPLETED":
                handleCompletedStatus(task, taskId, step, message, gameAccountId, metrics, response);
                break;
            case "FAILED":
                handleFailedStatus(task, taskId, step, message, gameAccountId, metrics, error, response);
                break;
            case "GAME_PREPARING":
                handleGamePreparingStatus(task, taskId, step, gameAccountId, accountStatus, metrics);
                break;
            case "GAMING":
                handleGamingStatus(task, taskId, step, gameAccountId, accountStatus, metrics);
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
                                     String gameAccountId, String accountStatus,
                                     Map<String, Object> metrics,
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
            String gameAccountStatus = resolveGameAccountStatus(accountStatus, "running");
            statusService.updateStatus(taskId, gameAccountId, gameAccountStatus);
            updateMetrics(taskId, gameAccountId, metrics);
        }

        taskMapper.updateById(task);
        response.put("action", "CONTINUE");
        log.info("任务运行中 - TaskID: {}, Step: {}", taskId, step);
    }

    private String resolveGameAccountStatus(String accountStatus, String defaultStatus) {
        if (accountStatus == null || accountStatus.isBlank()) {
            return defaultStatus;
        }
        return accountStatus;
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
                                            String gameAccountId, String accountStatus,
                                            Map<String, Object> metrics) {
        if (step != null) {
            task.setCurrentStep(step);
        }
        task.setStepStatus("GAME_PREPARING");

        if (gameAccountId != null) {
            String gameAccountStatus = resolveGameAccountStatus(accountStatus, "game_preparing");
            statusService.updateStatus(taskId, gameAccountId, gameAccountStatus);
            updateMetrics(taskId, gameAccountId, metrics);
        }

        taskMapper.updateById(task);
        log.info("游戏准备中 - TaskID: {}, GameAccountID: {}", taskId, gameAccountId);
    }

    private void handleGamingStatus(Task task, String taskId, String step,
                                     String gameAccountId, String accountStatus,
                                     Map<String, Object> metrics) {
        if (step != null) {
            task.setCurrentStep(step);
        }
        task.setStepStatus("GAMING");

        if (gameAccountId != null) {
            String gameAccountStatus = resolveGameAccountStatus(accountStatus, "gaming");
            statusService.updateStatus(taskId, gameAccountId, gameAccountStatus);
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
                streamingInfo.put("name", streamingAccount.getDisplayLabel());
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
                gaInfo.put("gameName", ga.getGameName());
                gaInfo.put("dailyMatchLimit", ga.getDailyMatchLimit());
                if (ga.getPositionIndex() != null) {
                    gaInfo.put("positionIndex", ga.getPositionIndex());
                }
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
    public Map<String, Object> updateProfileBinding(String gameAccountId, Map<String, Object> payload) {
        if (gameAccountId == null || gameAccountId.isBlank()) {
            throw new BusinessException(400, "gameAccountId不能为空");
        }
        GameAccount account = gameAccountService.findById(gameAccountId);
        if (account == null) {
            throw new BusinessException(ResultCode.GameAccount.NOT_FOUND);
        }

        Boolean profileBound = null;
        Object boundRaw = payload.get("profileBound");
        if (boundRaw == null) {
            boundRaw = payload.get("profile_bound");
        }
        if (boundRaw instanceof Boolean b) {
            profileBound = b;
        } else if (boundRaw != null) {
            profileBound = Boolean.parseBoolean(String.valueOf(boundRaw));
        }

        Integer positionIndex = null;
        Object posRaw = payload.get("positionIndex");
        if (posRaw == null) {
            posRaw = payload.get("position_index");
        }
        if (posRaw instanceof Number n) {
            positionIndex = n.intValue();
        } else if (posRaw != null && !String.valueOf(posRaw).isBlank()) {
            positionIndex = Integer.parseInt(String.valueOf(posRaw));
        }

        String gameName = null;
        Object nameRaw = payload.get("gameName");
        if (nameRaw == null) {
            nameRaw = payload.get("game_name");
        }
        if (nameRaw != null && !String.valueOf(nameRaw).isBlank()) {
            gameName = String.valueOf(nameRaw).trim();
        }

        gameAccountService.updateProfileBinding(gameAccountId, profileBound, positionIndex, gameName);

        GameAccount updated = gameAccountService.findById(gameAccountId);
        Map<String, Object> result = new HashMap<>();
        result.put("gameAccountId", gameAccountId);
        result.put("profileBound", profileBound != null ? profileBound : account.getProfileBound());
        result.put("positionIndex", positionIndex != null ? positionIndex : account.getPositionIndex());
        result.put("gameName", updated != null ? updated.getGameName() : account.getGameName());
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

    private void recordTaskEvent(
            Task task, String taskId, Map<String, Object> data,
            String status, String message, String scope) {
        try {
            TaskEvent event = new TaskEvent();
            event.setTaskId(taskId);
            event.setMerchantId(task.getMerchantId());
            event.setScope(scope != null ? scope : "task");
            event.setPhase((String) data.get("phase"));
            event.setStatus(status);
            event.setMessage(message);
            event.setGameAccountId((String) data.get("gameAccountId"));
            event.setModule((String) data.get("module"));
            if (task.getSessionId() != null) {
                event.setSessionId(task.getSessionId());
            }
            taskEventMapper.insert(event);
        } catch (Exception e) {
            log.debug("task_event insert skipped: {}", e.getMessage());
        }
    }

    private Map<String, Object> handleGameAccountScope(
            String taskId, Map<String, Object> data, String status) {
        String gameAccountId = (String) data.get("gameAccountId");
        if (gameAccountId != null) {
            TaskGameAccountStatus gaStatus =
                    statusService.findByTaskIdAndGameAccountId(taskId, gameAccountId);
            if (gaStatus != null) {
                String phase = (String) data.get("phase");
                if (phase != null) {
                    gaStatus.setPhase(phase);
                }
                gaStatus.setStatus(status.toLowerCase());
                if (data.get("matchIndex") instanceof Number mi) {
                    gaStatus.setMatchIndex(mi.intValue());
                }
                if (data.get("matchTotal") instanceof Number mt) {
                    gaStatus.setMatchTotal(mt.intValue());
                }
                statusService.updateProvisioningStatus(gaStatus);
            }
        }
        Map<String, Object> response = new HashMap<>();
        response.put("received", true);
        response.put("scope", "game_account");
        return response;
    }

    private Map<String, Object> handleSessionScope(
            Task task, String taskId, Map<String, Object> data,
            String status, String message) {
        String phase = (String) data.get("phase");
        if (phase != null) {
            task.setSessionPhase(phase);
            if ("ready".equals(phase) || "automation_failed".equals(phase)) {
                task.setGameActionPending(true);
                if ("running".equals(task.getStatus())
                        || "paused".equals(task.getStatus())
                        || ("automation_failed".equals(phase) && "failed".equals(task.getStatus()))) {
                    task.setStatus("running");
                }
                if ("automation_failed".equals(phase)) {
                    task.setErrorMessage(null);
                }
            }
            if (phase.startsWith("paused")) {
                task.setStatus("paused");
            }
            if ("automating".equals(phase)) {
                task.setGameActionPending(false);
            }
        }
        if (message != null) {
            task.setProgressMessage(message);
        }
        Object windowState = data.get("windowState");
        if (windowState != null) {
            task.setWindowVisible("visible".equals(windowState));
        }
        Object pauseMode = data.get("pauseMode");
        if (pauseMode != null) {
            task.setPauseMode(String.valueOf(pauseMode));
        }
        taskMapper.updateById(task);

        if (task.getSessionId() != null && phase != null) {
            streamingSessionService.updatePhase(task.getSessionId(), phase, message);
        }

        Map<String, Object> response = new HashMap<>();
        response.put("received", true);
        response.put("scope", "session");
        response.put("action", "CONTINUE");
        log.info("Session progress - TaskID: {}, phase: {}", taskId, phase);
        return response;
    }

    @SuppressWarnings("unchecked")
    private Map<String, Object> handleProvisioningScope(
            String taskId, Map<String, Object> data, String status) {
        String gameAccountId = (String) data.get("gameAccountId");
        if (gameAccountId == null) {
            throw new BusinessException(400, "gameAccountId required for provisioning scope");
        }

        TaskGameAccountStatus gaStatus = statusService.findByTaskIdAndGameAccountId(taskId, gameAccountId);
        if (gaStatus != null) {
            gaStatus.setActiveModule("account_provisioning");
            gaStatus.setPhase("provisioning");
            gaStatus.setProvisioningPhase((String) data.get("phase"));
            gaStatus.setProvisioningMessage((String) data.get("message"));
            if (data.get("stepIndex") instanceof Number stepIndex) {
                gaStatus.setProvisioningStep(stepIndex.intValue());
            }
            if (data.get("stepTotal") instanceof Number stepTotal) {
                gaStatus.setProvisioningStepTotal(stepTotal.intValue());
            }

            String accountStatus = (String) data.get("accountStatus");
            if (accountStatus != null && !accountStatus.isBlank()) {
                gaStatus.setStatus(accountStatus.toLowerCase());
            } else if ("FAILED".equals(status)) {
                gaStatus.setStatus("failed");
            } else if ("SKIPPED".equals(status)) {
                gaStatus.setStatus("skipped");
            }

            String errorMessage = (String) data.get("errorMessage");
            if (errorMessage != null && !errorMessage.isBlank()) {
                gaStatus.setErrorMessage(errorMessage);
            } else if ("FAILED".equals(status) && data.get("message") != null) {
                gaStatus.setErrorMessage(String.valueOf(data.get("message")));
            }

            statusService.updateProvisioningStatus(gaStatus);
        }

        Map<String, Object> response = new HashMap<>();
        response.put("received", true);
        response.put("scope", "module");
        response.put("action", "CONTINUE");
        return response;
    }
}
