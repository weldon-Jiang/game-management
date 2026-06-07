package com.bend.platform.service;

import com.bend.platform.dto.StartStreamingRequest;
import com.bend.platform.dto.StartTaskAutomationRequest;
import com.bend.platform.dto.TaskPauseRequest;

import java.util.List;
import java.util.Map;

/**
 * 任务会话控制服务（分阶段控制面）。
 *
 * <p>承载 {@code TaskControlController} 的业务逻辑：创建/复用串流任务、阶段性启动游戏自动化、
 * 暂停/恢复/取消/终止，以及窗口控制、跳过账号、重连串流等运行时操作。所有方法均按
 * {@code merchantId} 做租户隔离校验，并通过 WebSocket 向目标 Agent 下发 task_control 指令。</p>
 */
public interface TaskControlService {

    /**
     * 阶段一：为流媒体账号创建或复用串流任务并触发执行（仅建立串流）。
     *
     * @return 含 taskId、sessionId、phase、reused 标志
     */
    Map<String, Object> startStreaming(String streamingAccountId, StartStreamingRequest request,
                                       String userId, String merchantId);

    /**
     * 阶段二：串流就绪后按 gameActionType 启动游戏自动化并锁定会话任务类型。
     */
    Map<String, Object> startAutomation(String taskId, StartTaskAutomationRequest request, String merchantId);

    /** 暂停任务（immediate / after_match），更新状态并下发 pause 指令。 */
    void pauseTask(String taskId, TaskPauseRequest request, String merchantId);

    /** 恢复已暂停任务，回到 ready 或 automating 阶段并下发 resume 指令。 */
    void resumeTask(String taskId, String merchantId);

    /** 取消任务（语义等同终止）。 */
    void cancelTask(String taskId, String merchantId);

    /** 终止任务：取消执行、关闭会话、释放账号占用并下发 terminate 指令。 */
    void terminateTask(String taskId, String merchantId);

    /** 控制 Agent 端显示窗口显隐（action: show / hide）。 */
    void windowControl(String taskId, String action, String merchantId);

    /** 跳过任务中的指定游戏账号，标记 skipped 并通知 Agent。 */
    void skipGameAccount(String taskId, String gameAccountId, String merchantId);

    /** 请求 Agent 重连串流通道。 */
    void reconnectStream(String taskId, String merchantId);

    /** 查询任务详情（任务本体 + 串流会话 + 游戏账号执行状态）。 */
    Map<String, Object> getTaskDetail(String taskId, String merchantId);

    /** 查询任务事件流，可按会话过滤；limit 控制返回条数。 */
    java.util.List<com.bend.platform.entity.TaskEvent> getTaskEvents(
            String taskId, String merchantId, int limit, String sessionId);

    /** 列出任务的全部历史串流会话（最近一次在前），供前端切换查看不同轮次。 */
    java.util.List<com.bend.platform.entity.StreamingSession> getTaskSessions(
            String taskId, String merchantId);

    /** 查询指定 Agent 的活跃任务列表。 */
    List<Map<String, Object>> getActiveTasks(String agentId, String merchantId);
}
