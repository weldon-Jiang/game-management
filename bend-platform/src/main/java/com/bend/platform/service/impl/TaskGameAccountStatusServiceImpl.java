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

/**
 * 任务游戏账号状态服务实现。
 *
 * <p>该服务维护任务维度下每个游戏账号的生命周期：创建初始占用记录、更新比赛进度、
 * 切换账号级状态、取消任务时释放未终态账号。状态变更会影响前端任务详情展示，也会被
 * 余额预占和账号占用校验读取。
 */
@Service
public class TaskGameAccountStatusServiceImpl implements TaskGameAccountStatusService {

    @Autowired
    private TaskGameAccountStatusMapper statusMapper;

    /**
     * 为任务批量创建账号状态记录。
     *
     * <p>初始状态为 pending，sessionId 绑定当前长寿命串流会话；dailyLimits 与
     * gameAccountIds 按下标对应，缺省时使用 3 场作为兼容默认值。
     */
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

    /** 查询任务下所有游戏账号状态，供任务详情和进度统计使用。 */
    @Override
    public List<TaskGameAccountStatus> findByTaskId(String taskId) {
        return statusMapper.findByTaskId(taskId);
    }

    /** 查询任务内指定账号状态，后续状态迁移都以此记录为更新目标。 */
    @Override
    public TaskGameAccountStatus findByTaskIdAndGameAccountId(String taskId, String gameAccountId) {
        LambdaQueryWrapper<TaskGameAccountStatus> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(TaskGameAccountStatus::getTaskId, taskId)
               .eq(TaskGameAccountStatus::getGameAccountId, gameAccountId);
        return statusMapper.selectOne(wrapper);
    }

    /**
     * 查询当前商户内仍占用指定游戏账号的运行中记录。
     *
     * <p>用于启动前冲突检查，避免同一游戏账号被多个任务并发自动化。
     */
    @Override
    public List<TaskGameAccountStatus> findActiveOccupancies(String merchantId, List<String> gameAccountIds) {
        if (merchantId == null || gameAccountIds == null || gameAccountIds.isEmpty()) {
            return List.of();
        }
        return statusMapper.findActiveOccupancies(merchantId, gameAccountIds);
    }

    /**
     * 累计单场比赛完成结果。
     *
     * <p>pending/running 状态会保持为 running；成功与失败分别累加对应计数，
     * lastMatchTime 表示最近一次比赛尝试结束时间。
     */
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

    /**
     * 更新账号级主状态。
     *
     * <p>进入 running 时补 startedTime；进入 completed 时补 completedTime。
     * 其他终态如 failed/cancelled/timeout 由专用方法写入更多上下文。
     */
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

    /** 标记账号正在进行游戏前准备，通常发生在 Step4 切换账号并进入菜单前。 */
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

    /** 标记账号正在比赛自动化阶段，表示 Step4 已开始对该账号发送游戏操作。 */
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

    /** 标记账号执行超时，并写入统一错误文案供前端展示。 */
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

    /** 当任务内所有账号都进入终态时，任务执行器可据此推进任务终态。 */
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

    /**
     * 取消任务下所有仍在运行或等待中的账号。
     *
     * <p>已 completed/failed/timeout 的记录不回退，避免覆盖真实执行结果。
     */
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

    /** 删除任务下账号状态记录，通常用于清理未真正启动或测试任务数据。 */
    @Override
    @Transactional
    public void deleteByTaskId(String taskId) {
        LambdaQueryWrapper<TaskGameAccountStatus> wrapper = new LambdaQueryWrapper<>();
        wrapper.eq(TaskGameAccountStatus::getTaskId, taskId);
        statusMapper.delete(wrapper);
    }

    /** 同步账号当日比赛进度，用于前端展示本账号距 dailyLimit 的剩余额度。 */
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

    /**
     * 更新账号开通/档案绑定阶段。
     *
     * <p>调用方传入已填充 id 的状态对象，避免在开通流程中重复查询并降低并发覆盖风险。
     */
    @Override
    @Transactional
    public void updateProvisioningStatus(TaskGameAccountStatus status) {
        if (status != null && status.getId() != null) {
            statusMapper.updateById(status);
        }
    }
}
