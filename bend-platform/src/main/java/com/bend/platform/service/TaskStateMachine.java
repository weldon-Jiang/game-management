package com.bend.platform.service;

import com.bend.platform.entity.Task;
import com.bend.platform.enums.TaskStatus;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.exception.ResultCode;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

/**
 * 任务状态机
 *
 * <p>负责校验任务状态的合法转换，确保任务状态流转符合预定义规则。
 *
 * <p>状态转换规则：
 * <table border="1">
 *   <tr><th>当前状态</th><th>可转换目标状态</th></tr>
 *   <tr><td>pending</td><td>running, cancelled</td></tr>
 *   <tr><td>running</td><td>completed, failed, cancelled</td></tr>
 *   <tr><td>completed</td><td>（终态，不可转换）</td></tr>
 *   <tr><td>failed</td><td>pending（重试）, running</td></tr>
 *   <tr><td>cancelled</td><td>（终态，不可转换）</td></tr>
 * </table>
 *
 * @see TaskStatus
 * @see Task
 */
@Slf4j
@Component
public class TaskStateMachine {

    /**
     * 校验任务状态转换（通过任务对象）
     *
     * <p>根据任务的当前状态，校验是否可以转换为目标状态。
     *
     * @param task 任务对象
     * @param newStatus 目标状态
     * @throws BusinessException 状态无效或不允许转换
     */
    public void validateTransition(Task task, TaskStatus newStatus) {
        TaskStatus currentStatus = TaskStatus.fromCode(task.getStatus());
        if (currentStatus == null) {
            log.error("任务状态无效 - taskId: {}, status: {}", task.getId(), task.getStatus());
            throw new BusinessException(ResultCode.Task.INVALID_STATUS);
        }

        if (!currentStatus.canTransitionTo(newStatus)) {
            log.warn("非法状态转换 - taskId: {}, current: {}, target: {}",
                task.getId(), currentStatus.getDescription(), newStatus.getDescription());
            throw new BusinessException(ResultCode.Task.INVALID_STATUS_TRANSITION);
        }
    }

    /**
     * 校验任务状态转换（通过状态码）
     *
     * <p>根据当前状态码和目标状态码，校验是否可以转换。
     *
     * @param currentStatusCode 当前状态码
     * @param targetStatusCode 目标状态码
     * @throws BusinessException 状态无效或不允许转换
     */
    public void validateTransition(String currentStatusCode, String targetStatusCode) {
        TaskStatus currentStatus = TaskStatus.fromCode(currentStatusCode);
        TaskStatus targetStatus = TaskStatus.fromCode(targetStatusCode);

        if (currentStatus == null || targetStatus == null) {
            throw new BusinessException(ResultCode.Task.INVALID_STATUS);
        }

        if (!currentStatus.canTransitionTo(targetStatus)) {
            throw new BusinessException(ResultCode.Task.INVALID_STATUS_TRANSITION);
        }
    }

    /**
     * 检查是否可以转换
     *
     * <p>与 validateTransition 不同，此方法只返回校验结果，不抛出异常。
     *
     * @param task 任务对象
     * @param newStatus 目标状态
     * @return true 可以转换，false 不可以转换
     */
    public boolean canTransition(Task task, TaskStatus newStatus) {
        TaskStatus currentStatus = TaskStatus.fromCode(task.getStatus());
        if (currentStatus == null) {
            return false;
        }
        return currentStatus.canTransitionTo(newStatus);
    }
}