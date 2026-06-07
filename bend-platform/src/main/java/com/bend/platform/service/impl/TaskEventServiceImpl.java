package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskEvent;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.repository.TaskEventMapper;
import com.bend.platform.service.TaskEventService;
import com.bend.platform.service.TaskService;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.util.List;

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
}
