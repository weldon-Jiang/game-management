package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.AgentLoadControlService;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.TaskService;
import com.bend.platform.service.TaskGameAccountStatusService;
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
@RequestMapping("/api/task")
@RequiredArgsConstructor
public class AgentCallbackController {

    private final TaskService taskService;
    private final GameAccountService gameAccountService;
    private final TaskMapper taskMapper;
    private final TaskGameAccountStatusService statusService;
    private final AgentLoadControlService loadControlService;

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

        List<TaskGameAccountStatus> taskStatuses = statusService.findByTaskId(taskId);
        List<Map<String, Object>> statusList = new ArrayList<>();

        if (!taskStatuses.isEmpty()) {
            for (TaskGameAccountStatus ts : taskStatuses) {
                Map<String, Object> status = new HashMap<>();
                status.put("id", ts.getGameAccountId());
                status.put("completedCount", ts.getCompletedCount());
                status.put("failedCount", ts.getFailedCount());
                status.put("totalMatches", ts.getTotalMatches());
                status.put("status", ts.getStatus());
                status.put("completed", "completed".equals(ts.getStatus()) || "skipped".equals(ts.getStatus()));
                statusList.add(status);
            }
        } else {
            List<GameAccount> gameAccounts = gameAccountService.findByStreamingId(streamingAccountId);
            for (GameAccount ga : gameAccounts) {
                Map<String, Object> status = new HashMap<>();
                status.put("id", ga.getId());
                status.put("gamertag", ga.getXboxGameName());
                status.put("completedCount", ga.getTodayMatchCount() != null ? ga.getTodayMatchCount() : 0);
                status.put("targetMatches", ga.getDailyMatchLimit() != null ? ga.getDailyMatchLimit() : 3);
                status.put("completed", (ga.getTodayMatchCount() != null ? ga.getTodayMatchCount() : 0)
                        >= (ga.getDailyMatchLimit() != null ? ga.getDailyMatchLimit() : 3));
                statusList.add(status);
            }
        }

        log.info("返回游戏账号状态 - TaskID: {}, 账号数量: {}", taskId, statusList.size());
        return ApiResponse.success(statusList);
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

        String status = (String) progressData.get("status");
        String message = (String) progressData.get("message");
        String gameAccountId = (String) progressData.get("gameAccountId");

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        if ("COMPLETED".equals(status)) {
            if (gameAccountId != null) {
                statusService.updateStatus(taskId, gameAccountId, "completed");
            }
            if (statusService.areAllGameAccountsCompleted(taskId)) {
                task.setStatus("completed");
                task.setCompletedTime(LocalDateTime.now());
                task.setResult(message);
                taskMapper.updateById(task);
                loadControlService.decrementTaskCount(task.getTargetAgentId(), taskId);
            }
        } else if ("FAILED".equals(status)) {
            if (gameAccountId != null) {
                statusService.updateStatus(taskId, gameAccountId, "failed");
            }
            task.setStatus("failed");
            task.setErrorMessage(message);
        } else if ("RUNNING".equals(status)) {
            if ("pending".equals(task.getStatus())) {
                task.setStatus("running");
                task.setStartedTime(LocalDateTime.now());
                taskMapper.updateById(task);
            }
            if (gameAccountId != null) {
                statusService.updateStatus(taskId, gameAccountId, "running");
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

        TaskGameAccountStatus ts = statusService.findByTaskIdAndGameAccountId(taskId, gameAccountId);
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
            } else if ("failed".equals(status)) {
                ts.setStatus("failed");
                ts.setErrorMessage(errorMessage);
            }
            statusService.updateStatus(taskId, gameAccountId, ts.getStatus());
        }

        if (statusService.areAllGameAccountsCompleted(taskId)) {
            Task task = taskService.findById(taskId);
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
