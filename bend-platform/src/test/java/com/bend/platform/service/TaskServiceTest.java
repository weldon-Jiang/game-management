package com.bend.platform.service;

import com.bend.platform.entity.Task;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.exception.BusinessException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

/**
 * TaskService 单元测试
 *
 * 测试场景：
 * - 任务创建
 * - 任务查询
 * - 任务状态流转
 * - 任务分配
 * - 任务取消和重试
 *
 * 使用Mockito模拟依赖
 */
@ExtendWith(MockitoExtension.class)
class TaskServiceTest {

    @Mock
    private TaskMapper taskMapper;

    @InjectMocks
    private TaskServiceImpl taskService;

    private Task testTask;

    @BeforeEach
    void setUp() {
        testTask = new Task();
        testTask.setId("task-001");
        testTask.setName("测试任务");
        testTask.setType("stream_control");
        testTask.setStatus("pending");
        testTask.setPriority("0");
    }

    /**
     * 测试：创建任务
     *
     * 验证：
     * - 任务状态初始为pending
     * - 重试次数为0
     * - mapper.insert被调用
     */
    @Test
    void testCreateTask() {
        when(taskMapper.insert(any(Task.class))).thenReturn(1);

        Task created = taskService.create(testTask);

        assertNotNull(created);
        assertEquals("pending", created.getStatus());
        assertEquals(0, created.getRetryCount());
        verify(taskMapper, times(1)).insert(any(Task.class));
    }

    /**
     * 测试：根据ID查询任务
     *
     * 验证：
     * - 任务存在时返回任务对象
     * - mapper.selectById被调用
     */
    @Test
    void testFindById() {
        when(taskMapper.selectById("task-001")).thenReturn(testTask);

        Task found = taskService.findById("task-001");

        assertNotNull(found);
        assertEquals("task-001", found.getId());
        assertEquals("测试任务", found.getName());
        verify(taskMapper, times(1)).selectById("task-001");
    }

    /**
     * 测试：根据ID查询不存在的任务
     *
     * 验证：
     * - 返回null
     */
    @Test
    void testFindByIdNotFound() {
        when(taskMapper.selectById("non-existent")).thenReturn(null);

        Task found = taskService.findById("non-existent");

        assertNull(found);
    }

    /**
     * 测试：查询Agent的任务列表
     *
     * 验证：
     * - 返回该Agent的所有任务
     * - 按创建时间倒序排列
     */
    @Test
    void testFindByAgentId() {
        Task task1 = new Task();
        task1.setId("task-001");
        Task task2 = new Task();
        task2.setId("task-002");
        when(taskMapper.selectList(any())).thenReturn(Arrays.asList(task1, task2));

        List<Task> tasks = taskService.findByAgentId("agent-001");

        assertEquals(2, tasks.size());
        verify(taskMapper, times(1)).selectList(any());
    }

    /**
     * 测试：分配任务给Agent
     *
     * 验证：
     * - 任务状态更新
     * - 分配时间设置
     * - mapper.updateById被调用
     */
    @Test
    void testAssignToAgent() {
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Task assigned = taskService.assignToAgent("task-001", "agent-001");

        assertNotNull(assigned);
        assertEquals("agent-001", assigned.getTargetAgentId());
        assertNotNull(assigned.getAssignedAt());
        verify(taskMapper, times(1)).updateById(any(Task.class));
    }

    /**
     * 测试：分配不存在的任务
     *
     * 验证：
     * - 抛出BusinessException
     */
    @Test
    void testAssignNonExistentTask() {
        when(taskMapper.selectById("non-existent")).thenReturn(null);

        assertThrows(BusinessException.class, () -> {
            taskService.assignToAgent("non-existent", "agent-001");
        });
    }

    /**
     * 测试：开始执行任务
     *
     * 验证：
     * - 状态变为running
     * - 开始时间设置
     */
    @Test
    void testStartTask() {
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Task started = taskService.start("task-001");

        assertEquals("running", started.getStatus());
        assertNotNull(started.getStartedAt());
    }

    /**
     * 测试：标记任务完成
     *
     * 验证：
     * - 状态变为completed
     * - 完成时间设置
     * - 结果存储
     */
    @Test
    void testCompleteTask() {
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Task completed = taskService.complete("task-001", "任务执行成功");

        assertEquals("completed", completed.getStatus());
        assertEquals("任务执行成功", completed.getResult());
        assertNotNull(completed.getCompletedAt());
    }

    /**
     * 测试：标记任务失败（未达最大重试次数）
     *
     * 验证：
     * - 重试次数增加
     * - 状态回到pending等待重试
     */
    @Test
    void testFailTaskWithRetry() {
        testTask.setRetryCount(0);
        testTask.setMaxRetries(3);
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Task failed = taskService.fail("task-001", "执行失败");

        assertEquals("pending", failed.getStatus());
        assertEquals(1, failed.getRetryCount());
        assertEquals("执行失败", failed.getErrorMessage());
    }

    /**
     * 测试：标记任务失败（达到最大重试次数）
     *
     * 验证：
     * - 状态变为failed
     * - 不再重试
     */
    @Test
    void testFailTaskMaxRetries() {
        testTask.setRetryCount(2);
        testTask.setMaxRetries(3);
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Task failed = taskService.fail("task-001", "执行失败");

        assertEquals("failed", failed.getStatus());
        assertEquals(3, failed.getRetryCount());
    }

    /**
     * 测试：取消任务
     *
     * 验证：
     * - 只能取消pending状态的任务
     * - 其他状态抛出异常
     */
    @Test
    void testCancelPendingTask() {
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Task cancelled = taskService.cancel("task-001");

        assertEquals("cancelled", cancelled.getStatus());
    }

    /**
     * 测试：取消运行中的任务（应失败）
     *
     * 验证：
     * - 只能取消pending状态的任务
     * - running状态抛出BusinessException
     */
    @Test
    void testCancelRunningTask() {
        testTask.setStatus("running");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);

        assertThrows(BusinessException.class, () -> {
            taskService.cancel("task-001");
        });
    }

    /**
     * 测试：重试失败任务
     *
     * 验证：
     * - 状态重置为pending
     * - 重试计数清零
     * - 错误信息清空
     */
    @Test
    void testRetryFailedTask() {
        testTask.setStatus("failed");
        testTask.setRetryCount(3);
        testTask.setErrorMessage("之前的错误");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Task retried = taskService.retry("task-001");

        assertEquals("pending", retried.getStatus());
        assertEquals(0, retried.getRetryCount());
        assertNull(retried.getErrorMessage());
    }

    /**
     * 测试：删除任务（软删除）
     *
     * 验证：
     * - deleted标志设置为true
     */
    @Test
    void testDeleteTask() {
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        taskService.delete("task-001");

        verify(taskMapper, times(1)).updateById(argThat(task ->
            task.getDeleted() != null && task.getDeleted()
        ));
    }
}
