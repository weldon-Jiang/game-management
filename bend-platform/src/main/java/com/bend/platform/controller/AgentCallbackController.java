package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.entity.XboxHost;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.AgentLoadControlService;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.MerchantBalanceService;
import com.bend.platform.service.StreamingAccountService;
import com.bend.platform.service.SubscriptionService;
import com.bend.platform.service.TaskService;
import com.bend.platform.service.TaskGameAccountStatusService;
import com.bend.platform.service.XboxHostService;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.*;

/**
 * Agent回调控制器 v2.0
 *
 * 统一接口规范：
 * - 所有回调接口使用 /api/v1/agent-callback 前缀
 * - 所有参数通过请求体JSON传递
 * - 使用 X-Agent-Id 和 X-Agent-Secret 请求头认证
 * - 响应使用 ApiResponse<T> 包装
 *
 * @version 2.0
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/agent-callback")
@RequiredArgsConstructor
public class AgentCallbackController {

    private final TaskService taskService;
    private final GameAccountService gameAccountService;
    private final TaskMapper taskMapper;
    private final TaskGameAccountStatusService statusService;
    private final AgentLoadControlService loadControlService;
    private final SubscriptionService subscriptionService;
    private final MerchantBalanceService balanceService;
    private final StreamingAccountService streamingAccountService;
    private final XboxHostService xboxHostService;

    private final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 统一进度上报接口 v2.0
     *
     * 功能：
     * - 替代原有的 report_task_status、report_task_progress、update_game_account_status
     * - 支持详细的步骤级进度上报
     * - 自动处理任务状态转换和游戏账号状态更新
     *
     * @param payload 统一进度上报请求体
     * @return 操作结果
     */
    @PostMapping("/progress")
    public ApiResponse<Map<String, Object>> reportProgress(@RequestBody Map<String, Object> payload) {
        log.info("【v2.0】统一进度上报 - Payload: {}", payload);

        try {
            String taskId = (String) payload.get("taskId");
            Long timestamp = payload.get("timestamp") != null
                    ? ((Number) payload.get("timestamp")).longValue()
                    : System.currentTimeMillis();

            Map<String, Object> data = (Map<String, Object>) payload.get("data");
            if (data == null) {
                return ApiResponse.error(400, "data字段不能为空");
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
                return ApiResponse.error(400, "taskId和status为必需字段");
            }

            Task task = taskService.findById(taskId);
            if (task == null) {
                return ApiResponse.error(404, "任务不存在");
            }

            Map<String, Object> response = new HashMap<>();
            response.put("received", true);

            // 根据状态执行不同逻辑
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

            return ApiResponse.success(response);

        } catch (Exception e) {
            log.error("处理进度上报失败", e);
            return ApiResponse.error(500, "处理失败: " + e.getMessage());
        }
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
        }
    }

    /**
     * 获取任务信息
     *
     * @param taskId 任务ID
     * @return 任务完整信息
     */
    @GetMapping("/task/{taskId}")
    public ApiResponse<Map<String, Object>> getTaskInfo(@PathVariable String taskId) {
        log.info("【v2.0】获取任务信息 - TaskID: {}", taskId);

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        Map<String, Object> result = new HashMap<>();
        result.put("taskId", task.getId());
        result.put("taskType", task.getType());  // 修正：字段名是type，不是taskType
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
                gaInfo.put("gamertag", ga.getXboxGameName());
                gaInfo.put("dailyMatchLimit", ga.getDailyMatchLimit());
                gameAccounts.add(gaInfo);
            }
        }
        result.put("gameAccounts", gameAccounts);

        return ApiResponse.success(result);
    }

    /**
     * Xbox主机锁定
     *
     * @param xboxHostId Xbox主机ID
     * @param payload 请求体（包含taskId）
     * @return 锁定结果
     */
    @PostMapping("/xbox/{xboxHostId}/lock")
    public ApiResponse<Map<String, Object>> lockXboxHost(
            @PathVariable String xboxHostId,
            @RequestBody(required = false) Map<String, Object> payload) {

        log.info("【v2.0】锁定Xbox主机 - XboxHostID: {}", xboxHostId);

        XboxHost host = xboxHostService.findById(xboxHostId);
        if (host == null) {
            return ApiResponse.error(404, "Xbox主机不存在");
        }

        String taskId = payload != null ? (String) payload.get("taskId") : null;

        boolean locked = xboxHostService.lock(xboxHostId, taskId);

        Map<String, Object> result = new HashMap<>();
        result.put("locked", locked);

        if (locked) {
            result.put("expiresAt", System.currentTimeMillis() + 3600000); // 1小时后过期
            log.info("Xbox主机锁定成功 - XboxHostID: {}", xboxHostId);
        } else {
            log.warn("Xbox主机锁定失败 - XboxHostID: {}, 原因: 已被其他Agent锁定", xboxHostId);
        }

        return ApiResponse.success(result);
    }

    /**
     * Xbox主机解锁
     *
     * @param xboxHostId Xbox主机ID
     * @param payload 请求体（包含taskId）
     * @return 解锁结果
     */
    @PostMapping("/xbox/{xboxHostId}/unlock")
    public ApiResponse<Map<String, Object>> unlockXboxHost(
            @PathVariable String xboxHostId,
            @RequestBody(required = false) Map<String, Object> payload) {

        log.info("【v2.0】解锁Xbox主机 - XboxHostID: {}", xboxHostId);

        XboxHost host = xboxHostService.findById(xboxHostId);
        if (host == null) {
            return ApiResponse.error(404, "Xbox主机不存在");
        }

        String taskId = payload != null ? (String) payload.get("taskId") : null;

        boolean unlocked = xboxHostService.unlock(xboxHostId);

        Map<String, Object> result = new HashMap<>();
        result.put("unlocked", unlocked);

        if (unlocked) {
            log.info("Xbox主机解锁成功 - XboxHostID: {}", xboxHostId);
        } else {
            log.warn("Xbox主机解锁失败 - XboxHostID: {}", xboxHostId);
        }

        return ApiResponse.success(result);
    }

    /**
     * Xbox主机状态查询
     *
     * @param xboxHostId Xbox主机ID
     * @return 主机详细信息
     */
    @GetMapping("/xbox/{xboxHostId}")
    public ApiResponse<Map<String, Object>> getXboxHostStatus(@PathVariable String xboxHostId) {
        log.info("【v2.0】查询Xbox主机状态 - XboxHostID: {}", xboxHostId);

        XboxHost host = xboxHostService.findById(xboxHostId);
        if (host == null) {
            return ApiResponse.error(404, "Xbox主机不存在");
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

        return ApiResponse.success(result);
    }

    /**
     * 凭证兑换
     *
     * @param payload 包含token的请求体
     * @return 兑换的凭证
     */
    @PostMapping("/credentials/exchange")
    public ApiResponse<Map<String, Object>> exchangeCredential(@RequestBody Map<String, Object> payload) {
        String token = (String) payload.get("token");
        if (token == null || token.isEmpty()) {
            return ApiResponse.error(400, "token不能为空");
        }

        log.info("【v2.0】凭证兑换 - Token: {}", token.substring(0, Math.min(10, token.length())) + "...");

        if (token.startsWith("DISABLED:")) {
            return ApiResponse.error(503, "Redis未启用，凭证功能不可用");
        }

        String credential = xboxHostService.getAndInvalidateCredential(token);
        if (credential == null) {
            return ApiResponse.error(404, "令牌不存在或已过期");
        }

        Map<String, Object> result = new HashMap<>();
        result.put("credential", credential);

        return ApiResponse.success(result);
    }

    // ==================== 兼容旧接口（标记为deprecated） ====================

    /**
     * @deprecated 使用 POST /api/v1/agent-callback/progress 替代
     */
    @Deprecated
    @PostMapping("/task/{taskId}/status")
    public ApiResponse<Void> reportTaskStatus(
            @PathVariable String taskId,
            @RequestBody Map<String, String> payload) {
        log.warn("【deprecated】使用旧接口 reportTaskStatus，请迁移至 /api/v1/agent-callback/progress");

        String status = payload.get("status");
        String message = payload.get("message");

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        taskService.updateStatus(taskId, status);

        Map<String, Object> newPayload = new HashMap<>();
        newPayload.put("taskId", taskId);
        newPayload.put("data", Map.of(
                "status", status,
                "message", message != null ? message : "",
                "deprecated", true
        ));

        reportProgress(newPayload);

        return ApiResponse.success();
    }

    /**
     * @deprecated 使用 POST /api/v1/agent-callback/progress 替代
     */
    @Deprecated
    @PostMapping("/task/{taskId}/game-account/{gameAccountId}/status")
    public ApiResponse<Void> updateGameAccountStatus(
            @PathVariable String taskId,
            @PathVariable String gameAccountId,
            @RequestBody Map<String, Object> payload) {
        log.warn("【deprecated】使用旧接口 updateGameAccountStatus，请迁移至 /api/v1/agent-callback/progress");

        String status = (String) payload.get("status");
        Integer todayCompleted = payload.get("todayCompleted") != null
                ? ((Number) payload.get("todayCompleted")).intValue()
                : null;
        Integer dailyLimit = payload.get("dailyLimit") != null
                ? ((Number) payload.get("dailyLimit")).intValue()
                : null;

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

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

        return ApiResponse.success();
    }

    /**
     * @deprecated 使用 GET /api/v1/agent-callback/task/{taskId} 替代
     */
    @Deprecated
    @GetMapping("/{taskId}/game-accounts/status")
    public ApiResponse<List<Map<String, Object>>> getGameAccountsStatus(@PathVariable String taskId) {
        log.warn("【deprecated】使用旧接口 getGameAccountsStatus，请迁移至 /api/v1/agent-callback/task/{taskId}");

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        String streamingAccountId = task.getStreamingAccountId();
        if (streamingAccountId == null) {
            return ApiResponse.error(400, "任务未关联串流账号");
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
                status.put("gamertag", ga != null ? ga.getXboxGameName() : "");

                status.put("todayCompleted", ts.getCompletedCount());
                status.put("dailyLimit", ts.getTotalMatches());
                status.put("completed", "completed".equals(ts.getStatus()));
                status.put("deprecated", true);

                statusList.add(status);
            }
        }

        return ApiResponse.success(statusList);
    }
}
