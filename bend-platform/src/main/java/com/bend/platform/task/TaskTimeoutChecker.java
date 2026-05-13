package com.bend.platform.task;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.Task;
import com.bend.platform.entity.TaskGameAccountStatus;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.AgentLoadControlService;
import com.bend.platform.service.TaskGameAccountStatusService;
import com.bend.platform.service.TaskService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.List;

@Slf4j
@Component
@RequiredArgsConstructor
public class TaskTimeoutChecker {

    private final TaskMapper taskMapper;
    private final TaskService taskService;
    private final TaskGameAccountStatusService statusService;
    private final AgentLoadControlService loadControlService;

    @Value("${task.timeout_check_interval:60000}")
    private long timeoutCheckInterval;

    @Scheduled(fixedRateString = "${task.timeout_check_interval:60000}")
    public void checkTaskTimeout() {
        log.debug("Running task timeout check...");

        try {
            LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(Task::getStatus, "running")
                    .gt(Task::getTimeoutSeconds, 0)
                    .isNotNull(Task::getStartedTime);

            List<Task> runningTasks = taskMapper.selectList(wrapper);

            for (Task task : runningTasks) {
                if (isTaskTimedOut(task)) {
                    log.warn("Task timed out - ID: {}, Name: {}, Started: {}, Timeout: {}s",
                            task.getId(), task.getName(), task.getStartedTime(), task.getTimeoutSeconds());
                    handleTaskTimeout(task);
                }
            }
        } catch (Exception e) {
            log.error("Error during task timeout check", e);
        }
    }

    private boolean isTaskTimedOut(Task task) {
        if (task.getStartedTime() == null || task.getTimeoutSeconds() == null || task.getTimeoutSeconds() <= 0) {
            return false;
        }

        LocalDateTime timeoutTime = task.getStartedTime().plusSeconds(task.getTimeoutSeconds());
        return LocalDateTime.now().isAfter(timeoutTime);
    }

    private void handleTaskTimeout(Task task) {
        try {
            task.setStatus("cancelled");
            task.setErrorMessage("Task timeout after " + task.getTimeoutSeconds() + " seconds");
            task.setCompletedTime(LocalDateTime.now());
            taskMapper.updateById(task);

            List<TaskGameAccountStatus> statuses = statusService.findByTaskId(task.getId());
            for (TaskGameAccountStatus status : statuses) {
                if ("pending".equals(status.getStatus()) || "running".equals(status.getStatus())) {
                    statusService.updateStatus(task.getId(), status.getGameAccountId(), "skipped");
                }
            }

            loadControlService.decrementTaskCount(task.getTargetAgentId(), task.getId());

            log.info("Task cancelled due to timeout - ID: {}", task.getId());
        } catch (Exception e) {
            log.error("Failed to handle task timeout - ID: {}", task.getId(), e);
        }
    }
}
