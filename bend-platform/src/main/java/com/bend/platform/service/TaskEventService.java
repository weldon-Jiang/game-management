package com.bend.platform.service;

import com.bend.platform.entity.TaskEvent;

import java.util.List;

/**
 * 任务事件服务。
 *
 * <p>任务事件（task_event）是 Agent 进度回调写入的时间线（含 scope/phase/status/message 等），
 * 供前端任务详情按时间或会话回溯执行过程。读取均按 limit 限制条数。</p>
 */
public interface TaskEventService {

    /** 按任务 ID 查询事件（内部使用，不做 merchant 校验）。 */
    List<TaskEvent> listByTaskId(String taskId, int limit);

    /** 按任务 ID 查询事件，并校验任务归属当前商户。 */
    List<TaskEvent> listByTaskIdForMerchant(String taskId, String merchantId, int limit);

    /** 按任务 ID + 串流会话过滤查询事件（仅返回指定会话内的事件）。 */
    List<TaskEvent> listByTaskIdAndSession(String taskId, String merchantId, String sessionId, int limit);

    /** 记录 Agent 上报的任务事件，写入前由调用方完成 task/session 归属校验。 */
    void record(TaskEvent event);
}
