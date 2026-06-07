package com.bend.platform.service;

import com.bend.platform.entity.TaskGameAccountStatus;

import java.util.List;

/**
 * 任务-游戏账号执行状态服务。
 *
 * <p>跟踪一个任务内每个游戏账号的执行进度：状态机（pending/running/game_preparing/gaming/
 * completed/failed/skipped/timeout）、当日完成场次与上限、账号开通（provisioning）子状态等。
 * 数据主要由 Agent 的进度回调驱动更新，并供前端任务详情与「全部完成」判定使用。</p>
 */
public interface TaskGameAccountStatusService {

    /** 任务创建时批量初始化各游戏账号的状态记录（含每日上限与所属会话）。 */
    void createStatusRecords(String taskId, List<String> gameAccountIds, List<Integer> dailyLimits,
                             String streamingAccountId, String sessionId);

    /** 查询任务下全部游戏账号状态。 */
    List<TaskGameAccountStatus> findByTaskId(String taskId);

    /** 查询任务内某个游戏账号的状态记录。 */
    TaskGameAccountStatus findByTaskIdAndGameAccountId(String taskId, String gameAccountId);

    /** 记录一场比赛完成结果（成功/失败），用于累加完成或失败计数。 */
    void updateMatchComplete(String taskId, String gameAccountId, boolean success);

    /** 直接更新某游戏账号的状态字符串。 */
    void updateStatus(String taskId, String gameAccountId, String status);

    /** 标记为「比赛准备中」。 */
    void updateToGamePreparing(String taskId, String gameAccountId);

    /** 标记为「比赛进行中」。 */
    void updateToGaming(String taskId, String gameAccountId);

    /** 标记为「超时」。 */
    void updateToTimeout(String taskId, String gameAccountId);

    /** 判断任务下所有游戏账号是否均已完成（用于任务整体收尾）。 */
    boolean areAllGameAccountsCompleted(String taskId);

    /** 任务下已完成的游戏账号数量。 */
    int getCompletedCount(String taskId);

    /** 任务下游戏账号总数。 */
    int getTotalCount(String taskId);

    /** 任务取消时将未完成账号置为取消态。 */
    void cancelByTaskId(String taskId);

    /** 删除任务下全部状态记录（复用任务重启前清理）。 */
    void deleteByTaskId(String taskId);

    /** 更新当日完成场次与每日上限（来自 metrics 回调）。 */
    void updateDailyMatchInfo(String taskId, String gameAccountId, Integer todayCompleted, Integer dailyLimit);

    /** 更新账号开通（provisioning）相关子状态与阶段信息。 */
    void updateProvisioningStatus(TaskGameAccountStatus status);
}
