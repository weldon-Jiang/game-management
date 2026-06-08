package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskEvent;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.repository.TaskEventMapper;
import com.bend.platform.service.TaskEventService;
import com.bend.platform.service.TaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;

import java.util.List;

/**
 * 任务事件查询与写入：Agent 回调/控制面经 record 落库，详情页按 taskId/sessionId 分页拉取。
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class TaskEventServiceImpl implements TaskEventService {

    private final TaskEventMapper taskEventMapper;
    private final TaskService taskService;

    @Override
    public List<TaskEvent> listByTaskId(String taskId, int limit) {
        int safeLimit = Math.min(Math.max(limit, 1), 200);
        LambdaQueryWrapper<TaskEvent> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(TaskEvent::getTaskId, taskId)
                .orderByDesc(TaskEvent::getCreatedTime)
                .last("LIMIT " + safeLimit);
        return taskEventMapper.selectList(wrapper);
    }

    @Override
    public List<TaskEvent> listByTaskIdForMerchant(String taskId, String merchantId, int limit) {
        Task task = taskService.findById(taskId);
        if (task == null || !merchantId.equals(task.getMerchantId())) {
            throw new BusinessException(404, "任务不存在");
        }
        return listByTaskId(taskId, limit);
    }

    @Override
    public List<TaskEvent> listByTaskIdAndSession(
            String taskId, String merchantId, String sessionId, int limit) {
        Task task = taskService.findById(taskId);
        if (task == null || !merchantId.equals(task.getMerchantId())) {
            throw new BusinessException(404, "任务不存在");
        }
        int safeLimit = Math.min(Math.max(limit, 1), 200);
        LambdaQueryWrapper<TaskEvent> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(TaskEvent::getTaskId, taskId)
                .eq(TaskEvent::getSessionId, sessionId)
                .orderByDesc(TaskEvent::getCreatedTime)
                .last("LIMIT " + safeLimit);
        return taskEventMapper.selectList(wrapper);
    }

    /** 写入单条任务事件（架构红线：回调/控制面统一入口，禁止 Mapper 直连）。 */
    @Override
    public void record(TaskEvent event) {
        try {
            taskEventMapper.insert(event);
        } catch (Exception e) {
            log.warn("TaskEvent 写入失败 - taskId: {}, scope: {}, message: {}",
                    event.getTaskId(), event.getScope(), event.getMessage(), e);
        }
    }
}
