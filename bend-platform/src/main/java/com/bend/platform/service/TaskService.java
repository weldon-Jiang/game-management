package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.TaskPageRequest;
import com.bend.platform.entity.Task;

import java.util.List;

/**
 * 任务服务接口
 *
 * <p>提供任务的完整生命周期管理功能，包括创建、分配、执行、状态流转、取消、重试等操作。
 *
 * <p>任务状态机定义：
 * <ul>
 *   <li>pending - 待处理，可转为 running 或 cancelled</li>
 *   <li>running - 执行中，可转为 completed、failed 或 cancelled</li>
 *   <li>completed - 已完成，终态，不可再流转</li>
 *   <li>failed - 失败，可转为 pending（重试）或保持终态</li>
 *   <li>cancelled - 已取消，终态，不可再流转</li>
 * </ul>
 *
 * <p>幂等性支持：
 * <ul>
 *   <li>complete() 和 fail() 方法提供 idempotent 参数</li>
 *   <li>开启幂等性时，非预期状态的任务不会重复处理</li>
 * </ul>
 *
 * @see com.bend.platform.enums.TaskStatus
 * @see com.bend.platform.service.TaskStateMachine
 */
public interface TaskService {

    /**
     * 创建新任务
     *
     * <p>任务创建后状态为 pending，可分配给 Agent 执行。
     *
     * @param task 任务实体（包含名称、类型、参数等信息）
     * @return 创建后的任务（含ID）
     */
    Task create(Task task);

    /**
     * 根据ID查询任务
     *
     * @param id 任务ID
     * @return 任务实体，不存在返回 null
     */
    Task findById(String id);

    /**
     * 查询指定Agent的所有任务
     *
     * @param agentId Agent ID
     * @return 任务列表，按创建时间倒序排列
     */
    List<Task> findByAgentId(String agentId);

    /**
     * 查询指定Agent的待处理任务
     *
     * @param agentId Agent ID
     * @return 待处理任务列表
     */
    List<Task> findPendingByAgentId(String agentId);

    /**
     * 分页查询任务
     *
     * @param request 分页请求参数（支持按状态、类型、Agent等筛选）
     * @return 任务分页结果
     */
    IPage<Task> findPage(TaskPageRequest request);

    /**
     * 将任务分配给指定Agent
     *
     * <p>分配操作会设置任务的 targetAgentId 和 assignedTime。
     * 仅 pending 状态的任务可以分配。
     *
     * @param taskId 任务ID
     * @param agentId 目标Agent ID
     * @return 分配后的任务
     * @throws BusinessException 任务不存在或状态不允许分配
     */
    Task assignToAgent(String taskId, String agentId);

    /**
     * 开始执行任务
     *
     * <p>将任务状态从 pending 转为 running，记录开始时间。
     *
     * @param taskId 任务ID
     * @return 执行开始后的任务
     * @throws BusinessException 任务不存在或状态不允许启动
     */
    Task start(String taskId);

    /**
     * 标记任务完成（非幂等）
     *
     * <p>将任务状态从 running 转为 completed，记录完成结果和时间。
     *
     * @param taskId 任务ID
     * @param result 任务执行结果
     * @return 完成后的任务
     * @throws BusinessException 任务不存在或状态不允许完成
     */
    Task complete(String taskId, String result);

    /**
     * 标记任务完成（支持幂等）
     *
     * <p>当 idempotent=true 时，如果任务状态不是 running，则跳过处理直接返回。
     * 适用于 Agent 回调场景，防止网络重试导致重复处理。
     *
     * @param taskId 任务ID
     * @param result 任务执行结果
     * @param idempotent 是否开启幂等性校验
     * @return 完成后的任务
     */
    Task complete(String taskId, String result, boolean idempotent);

    /**
     * 标记任务失败（非幂等）
     *
     * <p>失败后根据重试次数判断：
     * <ul>
     *   <li>未达最大重试次数：状态转为 pending，等待重试</li>
     *   <li>已达最大重试次数：状态转为 failed，终态</li>
     * </ul>
     *
     * @param taskId 任务ID
     * @param errorMessage 错误信息
     * @return 失败处理后的任务
     * @throws BusinessException 任务不存在或状态不允许失败
     */
    Task fail(String taskId, String errorMessage);

    /**
     * 标记任务失败（支持幂等）
     *
     * <p>当 idempotent=true 时，如果任务状态不是 running，则跳过处理直接返回。
     *
     * @param taskId 任务ID
     * @param errorMessage 错误信息
     * @param idempotent 是否开启幂等性校验
     * @return 失败处理后的任务
     */
    Task fail(String taskId, String errorMessage, boolean idempotent);

    /**
     * 取消任务
     *
     * <p>仅 pending 状态的任务可以取消，转为 cancelled 终态。
     *
     * @param taskId 任务ID
     * @return 取消后的任务
     * @throws BusinessException 任务不存在或状态不允许取消
     */
    Task cancel(String taskId);

    /**
     * 重试失败任务
     *
     * <p>将 failed 状态的任务重置为 pending，清空错误信息和重试计数。
     *
     * @param taskId 任务ID
     * @return 重试准备的任务
     * @throws BusinessException 任务不存在或状态不允许重试
     */
    Task retry(String taskId);

    /**
     * 暂停任务
     *
     * <p>将 running 状态的任务转为 paused 状态。
     *
     * @param taskId 任务ID
     * @return 暂停后的任务
     */
    void pause(String taskId);

    /**
     * 恢复任务
     *
     * <p>将 paused 状态的任务转为 running 状态。
     *
     * @param taskId 任务ID
     * @return 恢复后的任务
     */
    void resume(String taskId);

    /**
     * 停止任务
     *
     * <p>将 running 或 paused 状态的任务强制停止，转为 stopped 状态。
     *
     * @param taskId 任务ID
     * @return 停止后的任务
     */
    void stop(String taskId);

    /**
     * 删除任务（软删除）
     *
     * <p>将任务的 deleted 标志设置为 true，不会真正从数据库删除。
     *
     * @param id 任务ID
     */
    void delete(String id);

    /**
     * 取消流媒体账号关联的所有任务
     *
     * <p>停止自动化时调用，将该账号下所有 pending 状态的任务取消。
     *
     * @param streamingAccountId 流媒体账号ID
     */
    void cancelByStreamingAccountId(String streamingAccountId);

    /**
     * 查询流媒体账号关联的所有任务
     *
     * @param streamingAccountId 流媒体账号ID
     * @return 任务列表，按创建时间倒序
     */
    List<Task> findByStreamingAccountId(String streamingAccountId);

    /**
     * 检查流媒体账号是否有运行中的任务
     *
     * @param streamingAccountId 流媒体账号ID
     * @return 是否有运行中的任务
     */
    boolean hasRunningTask(String streamingAccountId);

    /**
     * Active task for streaming account: pending, running, or paused.
     */
    Task findActiveTaskByStreamingAccountId(String streamingAccountId);

    /**
     * Latest reusable task bound to streaming account + agent (terminal states).
     */
    Task findReusableTaskByStreamingAccountAndAgent(String streamingAccountId, String agentId);

    /**
     * 查询卡住的任务
     *
     * <p>查找运行时间超过指定阈值但仍未完成的任务。
     * 用于定时检测异常任务并进行恢复处理。
     *
     * @param timeoutMinutes 超时阈值（分钟）
     * @return 卡住的任务列表
     */
    List<Task> findStuckRunningTasks(int timeoutMinutes);

    /**
     * 从离线Agent重新分配任务
     *
     * <p>将指定Agent的所有 running 状态任务重置为 pending，
     * 清除 agentId 分配，以便其他Agent可以接管。
     *
     * @param agentId 离线Agent的ID
     */
    void reassignTasksFromOfflineAgent(String agentId);

    /**
     * 更新任务状态
     *
     * @param taskId 任务ID
     * @param status 新状态
     */
    void updateStatus(String taskId, String status);

    /**
     * 清理Agent的未完成任务并还原账号状态
     *
     * <p>当Agent从离线变为在线时，清理该Agent所有未完成的任务（非completed状态），
     * 并还原相关的流媒体账号和游戏账号状态。
     *
     * @param agentId Agent的ID
     */
    void cleanupIncompleteTasksAndRestoreAccounts(String agentId);

    /**
     * Agent 进程重启后内存任务丢失，对仍标记为活跃的单条任务做失败清理并还原账号。
     *
     * @param agentId  目标 Agent ID（须与任务 targetAgentId 一致）
     * @param taskId   平台任务 ID
     */
    void failOrphanTaskOnAgent(String agentId, String taskId);

    /**
     * 根据商户ID查询所有正在运行的任务
     *
     * <p>用于计算扣点时统计其他正在运行的任务占用的点数。
     *
     * @param merchantId 商户ID
     * @return 正在运行的任务列表
     */
    List<Task> findRunningTasksByMerchantId(String merchantId);

    /**
     * 显式将 task.error_message 置 NULL（MyBatis-Plus 默认 updateById 会跳过 null 字段）。
     */
    void clearErrorMessage(String taskId);
}