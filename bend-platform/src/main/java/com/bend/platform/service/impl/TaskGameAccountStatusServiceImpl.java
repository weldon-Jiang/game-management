package com.bend.platform.service.impl;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.enums.TaskGameAccountStatusEnum;
import com.bend.platform.repository.TaskGameAccountStatusMapper;
import com.bend.platform.service.TaskGameAccountStatusService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDateTime;
import java.util.List;

@Service
public class TaskGameAccountStatusServiceImpl implements TaskGameAccountStatusService {

    @Autowired
    private TaskGameAccountStatusMapper statusMapper;

    @Override
    @Transactional
    public void createStatusRecords(String taskId, List<String> gameAccountIds, List<Integer> dailyLimits,
                                    String streamingAccountId, String sessionId) {
        for (int i = 0; i < gameAccountIds.size(); i++) {
            String gameAccountId = gameAccountIds.get(i);
            Integer dailyLimit = (i < dailyLimits.size()) ? dailyLimits.get(i) : 3;
            
            TaskGameAccountStatus status = new TaskGameAccountStatus();
            status.setTaskId(taskId);
            status.setGameAccountId(gameAccountId);
            status.setStreamingAccountId(streamingAccountId);
            status.setSessionId(sessionId);
            status.setPhase("pending");
            status.setStatus(TaskGameAccountStatusEnum.PENDING.getCode());
            status.setCompletedCount(0);
            status.setFailedCount(0);
            status.setTotalMatches(dailyLimit);
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
            if (TaskGameAccountStatusEnum.PENDING.getCode().equals(status.getStatus()) || 
                TaskGameAccountStatusEnum.RUNNING.getCode().equals(status.getStatus())) {
                status.setStatus(TaskGameAccountStatusEnum.RUNNING.getCode());
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
            if (TaskGameAccountStatusEnum.COMPLETED.getCode().equals(status)) {
                record.setCompletedTime(LocalDateTime.now());
            } else if (TaskGameAccountStatusEnum.RUNNING.getCode().equals(status) && record.getStartedTime() == null) {
                record.setStartedTime(LocalDateTime.now());
            }
            statusMapper.updateById(record);
        }
    }

    @Override
    @Transactional
    public void updateToGamePreparing(String taskId, String gameAccountId) {
        TaskGameAccountStatus record = findByTaskIdAndGameAccountId(taskId, gameAccountId);
        if (record != null) {
            record.setStatus(TaskGameAccountStatusEnum.GAME_PREPARING.getCode());
            if (record.getStartedTime() == null) {
                record.setStartedTime(LocalDateTime.now());
            }
            statusMapper.updateById(record);
        }
    }

    @Override
    @Transactional
    public void updateToGaming(String taskId, String gameAccountId) {
        TaskGameAccountStatus record = findByTaskIdAndGameAccountId(taskId, gameAccountId);
        if (record != null) {
            record.setStatus(TaskGameAccountStatusEnum.GAMING.getCode());
            if (record.getStartedTime() == null) {
                record.setStartedTime(LocalDateTime.now());
            }
            statusMapper.updateById(record);
        }
    }

    @Override
    @Transactional
    public void updateToTimeout(String taskId, String gameAccountId) {
        TaskGameAccountStatus record = findByTaskIdAndGameAccountId(taskId, gameAccountId);
        if (record != null) {
            record.setStatus(TaskGameAccountStatusEnum.TIMEOUT.getCode());
            record.setCompletedTime(LocalDateTime.now());
            record.setErrorMessage("任务执行超时");
            statusMapper.updateById(record);
        }
    }

    @Override
    public boolean areAllGameAccountsCompleted(String taskId) {
        List<TaskGameAccountStatus> allStatus = findByTaskId(taskId);
        if (allStatus.isEmpty()) {
            return false;
        }
        return allStatus.stream().allMatch(s -> {
            TaskGameAccountStatusEnum statusEnum = TaskGameAccountStatusEnum.fromCode(s.getStatus());
            return statusEnum.isFinalStatus();
        });
    }

    @Override
    public int getCompletedCount(String taskId) {
        List<TaskGameAccountStatus> completed = statusMapper.findByTaskIdAndStatus(taskId, TaskGameAccountStatusEnum.COMPLETED.getCode());
        return completed.size();
    }

    @Override
    public int getTotalCount(String taskId) {
        return findByTaskId(taskId).size();
    }

    @Override
    @Transactional
    public void cancelByTaskId(String taskId) {
        List<TaskGameAccountStatus> statuses = findByTaskId(taskId);
        for (TaskGameAccountStatus status : statuses) {
            TaskGameAccountStatusEnum currentStatus = TaskGameAccountStatusEnum.fromCode(status.getStatus());
            if (currentStatus.isRunningStatus() || TaskGameAccountStatusEnum.PENDING.equals(currentStatus)) {
                status.setStatus(TaskGameAccountStatusEnum.CANCELLED.getCode());
                status.setCompletedTime(LocalDateTime.now());
                statusMapper.updateById(status);
            }
        }
    }

    @Override
    @Transactional
    public void deleteByTaskId(String taskId) {
        LambdaQueryWrapper<TaskGameAccountStatus> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(TaskGameAccountStatus::getTaskId, taskId);
        statusMapper.delete(wrapper);
    }

    @Override
    @Transactional
    public void updateDailyMatchInfo(String taskId, String gameAccountId, Integer todayCompleted, Integer dailyLimit) {
        TaskGameAccountStatus record = findByTaskIdAndGameAccountId(taskId, gameAccountId);
        if (record != null) {
            if (todayCompleted != null) {
                record.setCompletedCount(todayCompleted);
            }
            if (dailyLimit != null) {
                record.setTotalMatches(dailyLimit);
            }
            statusMapper.updateById(record);
        }
    }

    @Override
    @Transactional
    public void updateProvisioningStatus(TaskGameAccountStatus status) {
        if (status != null && status.getId() != null) {
            statusMapper.updateById(status);
        }
    }
}
