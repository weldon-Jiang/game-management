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
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Slf4j
@RestController
@RequestMapping("/api")
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

    @PostMapping("/agent-callback/task/{taskId}/status")
    public ApiResponse<Void> reportTaskStatus(
            @PathVariable String taskId,
            @RequestBody Map<String, String> payload) {
        log.info("上报任务状态 - TaskID: {}, Status: {}", taskId, payload.get("status"));

        String status = payload.get("status");
        String message = payload.get("message");

        Task task = taskService.findById(taskId);
        if (task == null) {
            log.warn("任务不存在 - TaskID: {}", taskId);
            return ApiResponse.error(404, "任务不存在");
        }

        taskService.updateStatus(taskId, status);
        
        if (message != null) {
            // 可以将消息记录到任务日志中
            log.info("任务状态消息 - TaskID: {}, Message: {}", taskId, message);
        }

        return ApiResponse.success();
    }

    @PostMapping("/agent-callback/task/{taskId}/step-progress")
    public ApiResponse<Void> reportTaskStepProgress(
            @PathVariable String taskId,
            @RequestBody Map<String, String> payload) {
        log.info("上报任务步骤进度 - TaskID: {}, Step: {}, Status: {}", 
                taskId, payload.get("step"), payload.get("status"));

        String step = payload.get("step");
        String status = payload.get("status");
        String message = payload.get("message");

        Task task = taskService.findById(taskId);
        if (task == null) {
            log.warn("任务不存在 - TaskID: {}", taskId);
            return ApiResponse.error(404, "任务不存在");
        }

        // 更新任务的当前步骤
        task.setCurrentStep(step);
        task.setStepStatus(status);
        if (message != null) {
            task.setProgressMessage(message);
        }
        taskMapper.updateById(task);

        return ApiResponse.success();
    }

    @PostMapping("/agent-callback/task/{taskId}/game-account/{gameAccountId}/status")
    public ApiResponse<Void> updateGameAccountStatus(
            @PathVariable String taskId,
            @PathVariable String gameAccountId,
            @RequestBody Map<String, Object> payload) {
        log.info("更新游戏账号状态 - TaskID: {}, GameAccountID: {}, Status: {}", 
                taskId, gameAccountId, payload.get("status"));

        String status = (String) payload.get("status");
        Integer todayCompleted = payload.get("todayCompleted") != null ? 
                ((Number) payload.get("todayCompleted")).intValue() : null;
        Integer dailyLimit = payload.get("dailyLimit") != null ? 
                ((Number) payload.get("dailyLimit")).intValue() : null;

        Task task = taskService.findById(taskId);
        if (task == null) {
            log.warn("任务不存在 - TaskID: {}", taskId);
            return ApiResponse.error(404, "任务不存在");
        }

        // 更新游戏账号状态
        statusService.updateStatus(taskId, gameAccountId, status);
        
        if (todayCompleted != null || dailyLimit != null) {
            statusService.updateDailyMatchInfo(taskId, gameAccountId, todayCompleted, dailyLimit);
        }

        return ApiResponse.success();
    }

    @GetMapping("/{taskId}/game-accounts/status")
    public ApiResponse<List<Map<String, Object>>> getGameAccountsStatus(@PathVariable String taskId) {
        log.info("获取游戏账号状态 - TaskID: {}", taskId);

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
                status.put("failedCount", ts.getFailedCount());
                status.put("dailyLimit", ts.getTotalMatches());
                status.put("totalMatches", ts.getTotalMatches());
                
                String statusCode = ts.getStatus();
                status.put("status", statusCode);
                status.put("statusDescription", getStatusDescription(statusCode));
                
                boolean isCompleted = "completed".equals(statusCode);
                status.put("completed", isCompleted);
                
                if (ts.getErrorMessage() != null) {
                    status.put("errorMessage", ts.getErrorMessage());
                }
                
                statusList.add(status);
            }
        } else {
            for (GameAccount ga : allGameAccounts) {
                Map<String, Object> status = new HashMap<>();
                status.put("id", ga.getId());
                status.put("gamertag", ga.getXboxGameName());
                status.put("todayCompleted", ga.getTodayMatchCount() != null ? ga.getTodayMatchCount() : 0);
                status.put("failedCount", 0);
                status.put("dailyLimit", ga.getDailyMatchLimit() != null ? ga.getDailyMatchLimit() : 3);
                status.put("totalMatches", ga.getDailyMatchLimit() != null ? ga.getDailyMatchLimit() : 3);
                status.put("status", "pending");
                status.put("statusDescription", "待执行");
                boolean completed = (ga.getTodayMatchCount() != null ? ga.getTodayMatchCount() : 0)
                        >= (ga.getDailyMatchLimit() != null ? ga.getDailyMatchLimit() : 3);
                status.put("completed", completed);
                statusList.add(status);
            }
        }

        log.info("返回游戏账号状态 - TaskID: {}, 账号数量: {}", taskId, statusList.size());
        return ApiResponse.success(statusList);
    }
    
    private String getStatusDescription(String status) {
        switch (status) {
            case "pending": return "待执行";
            case "running": return "操作中";
            case "game_preparing": return "游戏准备中";
            case "gaming": return "游戏中";
            case "completed": return "已完成";
            case "failed": return "失败";
            case "cancelled": return "已取消";
            case "timeout": return "超时";
            default: return status;
        }
    }

    @PostMapping("/{taskId}/match/complete")
    public ApiResponse<Map<String, Object>> reportMatchComplete(
            @PathVariable String taskId,
            @RequestParam String gameAccountId,
            @RequestParam Integer completedCount,
            @RequestParam(required = false, defaultValue = "true") Boolean success) {

        log.info("比赛完成上报 - TaskID: {}, GameAccountID: {}, CompletedCount: {}, Success: {}",
                taskId, gameAccountId, completedCount, success);

        GameAccount gameAccount = gameAccountService.findById(gameAccountId);
        if (gameAccount == null) {
            return ApiResponse.error(404, "游戏账号不存在");
        }

        gameAccount.setTodayMatchCount(completedCount);
        gameAccount.setLastUsedTime(LocalDateTime.now());
        gameAccount.setTotalMatchCount(gameAccount.getTotalMatchCount() != null ? gameAccount.getTotalMatchCount() + 1 : 1);
        gameAccountService.update(gameAccountId, gameAccount);

        statusService.updateMatchComplete(taskId, gameAccountId, success);

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        List<TaskGameAccountStatus> allStatuses = statusService.findByTaskId(taskId);
        List<Map<String, Object>> allAccountsStatus = new ArrayList<>();
        boolean allCompleted = true;

        for (TaskGameAccountStatus ts : allStatuses) {
            Map<String, Object> status = new HashMap<>();
            status.put("id", ts.getGameAccountId());
            status.put("completedCount", ts.getCompletedCount());
            status.put("failedCount", ts.getFailedCount());
            status.put("totalMatches", ts.getTotalMatches());
            status.put("status", ts.getStatus());
            status.put("completed", "completed".equals(ts.getStatus()) || "skipped".equals(ts.getStatus()) || "failed".equals(ts.getStatus()));
            allAccountsStatus.add(status);

            if (!"completed".equals(ts.getStatus()) && !"skipped".equals(ts.getStatus()) && !"failed".equals(ts.getStatus())) {
                allCompleted = false;
            }
        }

        if (allCompleted && statusService.areAllGameAccountsCompleted(taskId)) {
            task.setStatus("completed");
            task.setCompletedTime(LocalDateTime.now());
            taskMapper.updateById(task);
            loadControlService.decrementTaskCount(task.getTargetAgentId(), taskId);
            log.info("所有游戏账号任务完成 - TaskID: {}", taskId);
        }

        Map<String, Object> result = new HashMap<>();
        result.put("allAccounts", allAccountsStatus);
        result.put("allCompleted", allCompleted);

        log.info("比赛完成处理完成 - TaskID: {}, AllCompleted: {}", taskId, allCompleted);
        return ApiResponse.success(result);
    }

    @PostMapping("/{taskId}/progress")
    public ApiResponse<Void> reportTaskProgress(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> progressData) {

        log.info("任务进度上报 - TaskID: {}, Data: {}", taskId, progressData);

        String step = (String) progressData.get("step");
        String status = (String) progressData.get("status");
        String message = (String) progressData.get("message");
        String gameAccountId = (String) progressData.get("gameAccountId");
        Integer todayCompleted = progressData.get("todayCompleted") != null ? 
                ((Number) progressData.get("todayCompleted")).intValue() : null;
        Integer dailyLimit = progressData.get("dailyLimit") != null ? 
                ((Number) progressData.get("dailyLimit")).intValue() : null;

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        // 更新任务的当前步骤和步骤状态
        if (step != null) {
            task.setCurrentStep(step);
        }
        if (status != null) {
            task.setStepStatus(status);
        }
        if (message != null) {
            task.setProgressMessage(message);
        }

        if ("COMPLETED".equals(status)) {
            if (gameAccountId != null) {
                statusService.updateStatus(taskId, gameAccountId, "completed");
                if (todayCompleted != null || dailyLimit != null) {
                    statusService.updateDailyMatchInfo(taskId, gameAccountId, todayCompleted, dailyLimit);
                }
            }
            if (statusService.areAllGameAccountsCompleted(taskId)) {
                task.setStatus("completed");
                task.setCompletedTime(LocalDateTime.now());
                task.setResult(message);
                taskMapper.updateById(task);
                loadControlService.decrementTaskCount(task.getTargetAgentId(), taskId);
                // 任务完成时，清空流媒体账号的agentId和任务状态
                if (task.getStreamingAccountId() != null) {
                    streamingAccountService.updateAgentId(task.getStreamingAccountId(), null);
                    streamingAccountService.updateTaskStatus(task.getStreamingAccountId(), "idle");
                }
            }
        } else if ("FAILED".equals(status)) {
            if (gameAccountId != null) {
                statusService.updateStatus(taskId, gameAccountId, "failed");
                if (todayCompleted != null || dailyLimit != null) {
                    statusService.updateDailyMatchInfo(taskId, gameAccountId, todayCompleted, dailyLimit);
                }
            }
            task.setStatus("failed");
            task.setErrorMessage(message);
            // 任务失败时，清空流媒体账号的agentId和任务状态
            if (task.getStreamingAccountId() != null) {
                streamingAccountService.updateAgentId(task.getStreamingAccountId(), null);
                streamingAccountService.updateTaskStatus(task.getStreamingAccountId(), "idle");
            }
        } else if ("RUNNING".equals(status)) {
            if ("pending".equals(task.getStatus())) {
                task.setStatus("running");
                task.setStartedTime(LocalDateTime.now());
                taskMapper.updateById(task);
            }
            if (gameAccountId != null) {
                statusService.updateStatus(taskId, gameAccountId, "running");
                if (todayCompleted != null || dailyLimit != null) {
                    statusService.updateDailyMatchInfo(taskId, gameAccountId, todayCompleted, dailyLimit);
                }
            }
        } else if ("GAME_PREPARING".equals(status)) {
            if (gameAccountId != null) {
                statusService.updateToGamePreparing(taskId, gameAccountId);
                if (todayCompleted != null || dailyLimit != null) {
                    statusService.updateDailyMatchInfo(taskId, gameAccountId, todayCompleted, dailyLimit);
                }
            }
        } else if ("GAMING".equals(status)) {
            if (gameAccountId != null) {
                statusService.updateToGaming(taskId, gameAccountId);
                if (todayCompleted != null || dailyLimit != null) {
                    statusService.updateDailyMatchInfo(taskId, gameAccountId, todayCompleted, dailyLimit);
                }
            }
        }

        taskMapper.updateById(task);
        log.info("任务进度处理完成 - TaskID: {}, Status: {}", taskId, status);
        return ApiResponse.success("进度已接收", null);
    }

    @PostMapping("/{taskId}/game-account/{gameAccountId}/complete")
    public ApiResponse<Void> reportGameAccountComplete(
            @PathVariable String taskId,
            @PathVariable String gameAccountId,
            @RequestBody Map<String, Object> resultData) {

        log.info("游戏账号任务完成上报 - TaskID: {}, GameAccountID: {}, Result: {}",
                taskId, gameAccountId, resultData);

        String status = (String) resultData.get("status");
        Integer completedCount = (Integer) resultData.get("completedCount");
        Integer failedCount = (Integer) resultData.get("failedCount");
        String errorMessage = (String) resultData.get("errorMessage");

        Task task = taskService.findById(taskId);
        TaskGameAccountStatus ts = statusService.findByTaskIdAndGameAccountId(taskId, gameAccountId);
        GameAccount gameAccount = gameAccountService.findById(gameAccountId);
        
        if (ts != null) {
            if (completedCount != null) {
                ts.setCompletedCount(completedCount);
            }
            if (failedCount != null) {
                ts.setFailedCount(failedCount);
            }
            if ("completed".equals(status)) {
                ts.setStatus("completed");
                ts.setCompletedTime(LocalDateTime.now());
                
                // 检查是否需要扣点：游戏账号完成当天最大比赛次数且没有生效订阅
                if (task != null && gameAccount != null && completedCount != null) {
                    Integer dailyLimit = gameAccount.getDailyMatchLimit();
                    if (dailyLimit != null && completedCount >= dailyLimit) {
                        // 检查商户是否有生效的订阅
                        List<?> activeSubscriptions = subscriptionService.getActiveSubscriptions(task.getMerchantId());
                        if (activeSubscriptions == null || activeSubscriptions.isEmpty()) {
                            // 没有生效订阅，需要扣1点（按游戏账号维度，按天幂等）
                            String today = java.time.LocalDate.now().toString();
                            String idempotentKey = taskId + "_" + gameAccountId + "_" + today;
                            
                            // 先检查是否已扣点（幂等检查）
                            if (!balanceService.hasDeductedTransaction(task.getMerchantId(), "game_account_daily", idempotentKey)) {
                                boolean deducted = balanceService.deductPoints(
                                        task.getMerchantId(), 1, task.getCreatedBy(),
                                        "game_account_daily", idempotentKey,
                                        "游戏账号【" + gameAccount.getXboxGameName() + "】完成当日" + dailyLimit + "场比赛，消耗1点");
                                if (deducted) {
                                    log.info("游戏账号完成当日比赛，扣点成功 - GameAccount: {}, MerchantID: {}, CompletedCount: {}/{}",
                                            gameAccount.getXboxGameName(), task.getMerchantId(), completedCount, dailyLimit);
                                }
                            } else {
                                log.info("游戏账号完成当日比赛，但今日已扣点，跳过 - GameAccount: {}, MerchantID: {}",
                                        gameAccount.getXboxGameName(), task.getMerchantId());
                            }
                        } else {
                            log.info("游戏账号完成当日比赛，但商户有生效订阅，不扣点 - GameAccount: {}, MerchantID: {}",
                                    gameAccount.getXboxGameName(), task.getMerchantId());
                        }
                    }
                }
            } else if ("failed".equals(status)) {
                ts.setStatus("failed");
                ts.setErrorMessage(errorMessage);
            }
            statusService.updateStatus(taskId, gameAccountId, ts.getStatus());
        }

        if (statusService.areAllGameAccountsCompleted(taskId)) {
            if (task != null) {
                task.setStatus("completed");
                task.setCompletedTime(LocalDateTime.now());
                taskMapper.updateById(task);
                loadControlService.decrementTaskCount(task.getTargetAgentId(), taskId);
            }
        }

        return ApiResponse.success("游戏账号状态已更新", null);
    }

    @PostMapping("/daily-match-count/reset")
    public ApiResponse<Void> resetDailyMatchCount() {
        log.info("重置每日比赛计数");
        List<GameAccount> allAccounts = gameAccountService.findAllByStreamingId(null);
        for (GameAccount ga : allAccounts) {
            ga.setTodayMatchCount(0);
            gameAccountService.update(ga.getId(), ga);
        }
        return ApiResponse.success("已重置所有游戏账号的今日比赛数", null);
    }
}
