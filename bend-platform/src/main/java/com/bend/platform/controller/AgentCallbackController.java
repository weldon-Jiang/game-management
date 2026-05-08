package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.TaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.web.bind.annotation.*;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Agent自动化回调接口
 *
 * 功能说明：
 * - Agent主动回调平台的接口
 * - 获取游戏账号状态
 * - 上报比赛完成
 * - 任务控制响应
 *
 * 回调触发时机：
 * - 任务开始时
 * - 步骤完成时
 * - 比赛完成时
 * - 任务异常时
 * - 任务完成时
 */
@Slf4j
@RestController
@RequestMapping("/api/task")
@RequiredArgsConstructor
public class AgentCallbackController {

    private final TaskService taskService;
    private final GameAccountService gameAccountService;
    private final TaskMapper taskMapper;

    /**
     * 获取串流账号下所有游戏账号的当天完成情况
     *
     * Agent在比赛开始前调用此API获取最新状态
     *
     * @param taskId 任务ID
     * @return 游戏账号状态列表
     */
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

        List<GameAccount> gameAccounts = gameAccountService.findByStreamingId(streamingAccountId);
        List<Map<String, Object>> statusList = new ArrayList<>();

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

        log.info("返回游戏账号状态 - TaskID: {}, 账号数量: {}", taskId, statusList.size());
        return ApiResponse.success(statusList);
    }

    /**
     * Agent上报比赛完成
     *
     * Agent比赛完成后调用此API更新平台数据
     * 实时同步游戏账号当天完成比赛次数
     *
     * @param taskId 任务ID
     * @param gameAccountId 游戏账号ID
     * @param completedCount 完成后当天总场次
     * @return 所有账号状态及是否全部完成
     */
    @PostMapping("/{taskId}/match/complete")
    public ApiResponse<Map<String, Object>> reportMatchComplete(
            @PathVariable String taskId,
            @RequestParam String gameAccountId,
            @RequestParam Integer completedCount) {

        log.info("比赛完成上报 - TaskID: {}, GameAccountID: {}, CompletedCount: {}",
                taskId, gameAccountId, completedCount);

        GameAccount gameAccount = gameAccountService.findById(gameAccountId);
        if (gameAccount == null) {
            return ApiResponse.error(404, "游戏账号不存在");
        }

        gameAccount.setTodayMatchCount(completedCount);
        gameAccount.setLastUsedTime(LocalDateTime.now());
        gameAccountService.update(gameAccountId, gameAccount);

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        String streamingAccountId = task.getStreamingAccountId();
        List<GameAccount> allAccounts = gameAccountService.findByStreamingId(streamingAccountId);

        List<Map<String, Object>> allAccountsStatus = new ArrayList<>();
        boolean allCompleted = true;

        for (GameAccount ga : allAccounts) {
            Map<String, Object> status = new HashMap<>();
            status.put("id", ga.getId());
            status.put("gamertag", ga.getXboxGameName());

            int completed = ga.getId().equals(gameAccountId) ? completedCount : ga.getTodayMatchCount() != null ? ga.getTodayMatchCount() : 0;
            int target = ga.getDailyMatchLimit() != null ? ga.getDailyMatchLimit() : 3;

            status.put("completedCount", completed);
            status.put("targetMatches", target);
            status.put("completed", completed >= target);
            allAccountsStatus.add(status);

            if (completed < target) {
                allCompleted = false;
            }
        }

        Map<String, Object> result = new HashMap<>();
        result.put("allAccounts", allAccountsStatus);
        result.put("allCompleted", allCompleted);

        log.info("比赛完成处理完成 - TaskID: {}, AllCompleted: {}", taskId, allCompleted);
        return ApiResponse.success(result);
    }

    /**
     * 接收Agent主动上报的任务进度
     *
     * @param taskId 任务ID
     * @param progressData 进度数据
     * @return 响应
     */
    @PostMapping("/{taskId}/progress")
    public ApiResponse<Void> reportTaskProgress(
            @PathVariable String taskId,
            @RequestBody Map<String, Object> progressData) {

        log.info("任务进度上报 - TaskID: {}, Data: {}", taskId, progressData);

        String step = (String) progressData.get("step");
        String status = (String) progressData.get("status");
        String message = (String) progressData.get("message");

        Task task = taskService.findById(taskId);
        if (task == null) {
            return ApiResponse.error(404, "任务不存在");
        }

        if ("COMPLETED".equals(status)) {
            task.setStatus("completed");
            task.setCompletedTime(LocalDateTime.now());
            task.setResult(message);
        } else if ("FAILED".equals(status)) {
            task.setStatus("failed");
            task.setErrorMessage(message);
        } else if ("RUNNING".equals(status)) {
            if ("pending".equals(task.getStatus())) {
                task.setStatus("running");
                task.setStartedTime(LocalDateTime.now());
            }
        }

        taskMapper.updateById(task);

        log.info("任务进度处理完成 - TaskID: {}, Step: {}, Status: {}", taskId, step, status);
        return ApiResponse.success("进度已接收", null);
    }

    /**
     * 重置游戏账号当日比赛数
     *
     * 每天零点调用，将所有游戏账号的今日比赛数重置为0
     *
     * @return 响应
     */
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
