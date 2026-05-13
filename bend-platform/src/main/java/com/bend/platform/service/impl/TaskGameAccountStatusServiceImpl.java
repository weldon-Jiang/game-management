package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.repository.TaskGameAccountStatusMapper;
import com.bend.platform.service.TaskGameAccountStatusService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;
import java.util.stream.Collectors;

@Service
public class TaskGameAccountStatusServiceImpl implements TaskGameAccountStatusService {

    @Autowired
    private TaskGameAccountStatusMapper statusMapper;

    @Override
    @Transactional
    public void createStatusRecords(String taskId, List<String> gameAccountIds, String streamingAccountId) {
        for (String gameAccountId : gameAccountIds) {
            TaskGameAccountStatus status = new TaskGameAccountStatus();
            status.setTaskId(taskId);
            status.setGameAccountId(gameAccountId);
            status.setStreamingAccountId(streamingAccountId);
            status.setStatus("pending");
            status.setCompletedCount(0);
            status.setFailedCount(0);
            status.setTotalMatches(0);
            statusMapper.insert(status);
        }
    }

    @Override
    public List<TaskGameAccountStatus> findByTaskId(String taskId) {
        return statusMapper.findByTaskId(taskId);
    }

    @Override
    public TaskGameAccountStatus findByTaskIdAndGameAccountId(String taskId, String gameAccountId) {
        LambdaQueryWrapper<TaskGameAccountStatus> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(TaskGameAccountStatus::getTaskId, taskId)
               .eq(TaskGameAccountStatus::getGameAccountId, gameAccountId);
        return statusMapper.selectOne(wrapper);
    }

    @Override
    @Transactional
    public void updateMatchComplete(String taskId, String gameAccountId, boolean success) {
        TaskGameAccountStatus status = findByTaskIdAndGameAccountId(taskId, gameAccountId);
        if (status != null) {
            status.setLastMatchTime(LocalDateTime.now());
            if ("pending".equals(status.getStatus()) || "running".equals(status.getStatus())) {
                status.setStatus("running");
                status.setStartedTime(status.getStartedTime() != null ? status.getStartedTime() : LocalDateTime.now());
            }
            if (success) {
                status.setCompletedCount(status.getCompletedCount() + 1);
                status.setTotalMatches(status.getTotalMatches() + 1);
            } else {
                status.setFailedCount(status.getFailedCount() + 1);
                status.setTotalMatches(status.getTotalMatches() + 1);
            }
            statusMapper.updateById(status);
        }
    }

    @Override
    @Transactional
    public void updateStatus(String taskId, String gameAccountId, String status) {
        TaskGameAccountStatus record = findByTaskIdAndGameAccountId(taskId, gameAccountId);
        if (record != null) {
            record.setStatus(status);
            if ("completed".equals(status)) {
                record.setCompletedTime(LocalDateTime.now());
            } else if ("running".equals(status) && record.getStartedTime() == null) {
                record.setStartedTime(LocalDateTime.now());
            }
            statusMapper.updateById(record);
        }
    }

    @Override
    public boolean areAllGameAccountsCompleted(String taskId) {
        List<TaskGameAccountStatus> allStatus = findByTaskId(taskId);
        if (allStatus.isEmpty()) {
            return false;
        }
        return allStatus.stream()
            .allMatch(s -> "completed".equals(s.getStatus()) || "skipped".equals(s.getStatus()) || "failed".equals(s.getStatus()));
    }

    @Override
    public int getCompletedCount(String taskId) {
        List<TaskGameAccountStatus> completed = statusMapper.findByTaskIdAndStatus(taskId, "completed");
        return completed.size();
    }

    @Override
    public int getTotalCount(String taskId) {
        return findByTaskId(taskId).size();
    }
}
