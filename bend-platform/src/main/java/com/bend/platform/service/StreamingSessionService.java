package com.bend.platform.service;

import com.bend.platform.entity.StreamingSession;
import com.bend.platform.entity.Task;

/**
 * 串流会话服务。
 *
 * <p>串流会话（streaming_session）是一次「拉起串流」的运行实例，与任务一对多：同一任务可被
 * 多次复用拉起，每次对应一个新的会话。会话记录串流阶段（phase）、锁定的游戏操作类型，
 * 并作为任务事件（task_event）按会话过滤的依据。</p>
 */
public interface StreamingSessionService {

    /** 为任务创建一个新的串流会话（阶段一拉起串流时调用）。 */
    StreamingSession createForTask(Task task, String merchantId);

    /** 查询任务当前关联的串流会话。 */
    StreamingSession findByTaskId(String taskId);

    /** 按会话 ID 查询。 */
    StreamingSession findById(String id);

    /** 更新会话阶段及消息（来自 Agent 的 session scope 进度回调）。 */
    void updatePhase(String sessionId, String phase, String message);

    /** 阶段二启动自动化时锁定会话的游戏操作类型，确保一次会话仅执行一种任务类型。 */
    void lockGameAction(String sessionId, String gameActionType);

    /** 关闭指定会话并写入终态 phase。 */
    void closeSession(String sessionId, String phase);

    /** 关闭任务下所有未结束的会话（复用任务重新拉起前清理旧会话）。 */
    void closeOpenSessionsForTask(String taskId, String phase);

    /** 列出任务的全部历史会话（按 startedTime 倒序），供前端切换查看不同轮次。 */
    java.util.List<StreamingSession> listByTaskId(String taskId);
}
