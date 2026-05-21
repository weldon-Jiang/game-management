package com.bend.platform.task;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.bend.platform.entity.Task;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.TaskExecutorService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Component;

import java.util.List;

/**
 * Pending状态任务重试调度器
 *
 * <p>定期检查并重试处于pending状态的任务，将任务发送给Agent执行。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class PendingTaskRetryScheduler {

    private final TaskMapper taskMapper;
    private final TaskExecutorService taskExecutorService;

    /**
     * 每30秒检查一次pending状态的任务并重试
     */
    @Scheduled(fixedRate = 30000)
    public void retryPendingTasks() {
        try {
            LambdaQueryWrapper<Task> wrapper = new LambdaQueryWrapper<>();
            wrapper.eq(Task::getStatus, "pending");

            List<Task> pendingTasks = taskMapper.selectList(wrapper);

            if (!pendingTasks.isEmpty()) {
                log.info("发现 {} 个待重试的pending状态任务", pendingTasks.size());

                for (Task task : pendingTasks) {
                    try {
                        log.info("重试pending任务 - TaskID: {}, Name: {}", task.getId(), task.getName());
                        taskExecutorService.executeTaskAsync(task);
                    } catch (Exception e) {
                        log.error("重试pending任务失败 - TaskID: {}", task.getId(), e);
                    }
                }
            }
        } catch (Exception e) {
            log.error("检查pending状态任务时发生错误", e);
        }
    }
}
