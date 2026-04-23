package com.bend.platform.service;

import com.bend.platform.entity.Task;
import com.bend.platform.enums.TaskStatus;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.service.impl.TaskServiceImpl;
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

@ExtendWith(MockitoExtension.class)
class TaskServiceTest {

    @Mock
    private TaskMapper taskMapper;

    @Mock
    private TaskStateMachine stateMachine;

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
        testTask.setMaxRetries(3);
        testTask.setDeleted(false);
    }

    @Test
    void testCreateTask() {
        when(taskMapper.insert(any(Task.class))).thenReturn(1);

        Task created = taskService.create(testTask);

        assertNotNull(created);
        assertEquals("pending", created.getStatus());
        assertEquals(0, created.getRetryCount());
        verify(taskMapper, times(1)).insert(any(Task.class));
    }

    @Test
    void testFindById() {
        when(taskMapper.selectById("task-001")).thenReturn(testTask);

        Task found = taskService.findById("task-001");

        assertNotNull(found);
        assertEquals("task-001", found.getId());
        verify(taskMapper, times(1)).selectById("task-001");
    }

    @Test
    void testFindByIdNotFound() {
        when(taskMapper.selectById("non-existent")).thenReturn(null);

        Task found = taskService.findById("non-existent");

        assertNull(found);
    }

    @Test
    void testFindByAgentId() {
        when(taskMapper.selectList(any())).thenReturn(Arrays.asList(testTask));

        List<Task> tasks = taskService.findByAgentId("agent-001");

        assertEquals(1, tasks.size());
        verify(taskMapper, times(1)).selectList(any());
    }

    @Test
    void testStartTask() {
        testTask.setStatus("pending");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);
        doNothing().when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        Task started = taskService.start("task-001");

        assertEquals("running", started.getStatus());
        assertNotNull(started.getStartedTime());
    }

    @Test
    void testCompleteTask() {
        testTask.setStatus("running");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);
        doNothing().when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        Task completed = taskService.complete("task-001", "执行成功");

        assertEquals("completed", completed.getStatus());
        assertEquals("执行成功", completed.getResult());
        assertNotNull(completed.getCompletedTime());
    }

    @Test
    void testCompleteTaskIdempotent() {
        testTask.setStatus("pending");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);
        doNothing().when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        Task result = taskService.complete("task-001", "执行成功", true);

        assertEquals("pending", result.getStatus());
        verify(taskMapper, never()).updateById(any(Task.class));
    }

    @Test
    void testFailTaskWithRetry() {
        testTask.setStatus("running");
        testTask.setRetryCount(0);
        testTask.setMaxRetries(3);
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);
        doNothing().when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        Task failed = taskService.fail("task-001", "执行失败");

        assertEquals("pending", failed.getStatus());
        assertEquals(1, failed.getRetryCount());
        assertEquals("执行失败", failed.getErrorMessage());
    }

    @Test
    void testFailTaskMaxRetries() {
        testTask.setStatus("running");
        testTask.setRetryCount(2);
        testTask.setMaxRetries(3);
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);
        doNothing().when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        Task failed = taskService.fail("task-001", "执行失败");

        assertEquals("failed", failed.getStatus());
        assertEquals(3, failed.getRetryCount());
    }

    @Test
    void testFailTaskIdempotent() {
        testTask.setStatus("completed");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        doNothing().when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        Task result = taskService.fail("task-001", "执行失败", true);

        assertEquals("completed", result.getStatus());
        verify(taskMapper, never()).updateById(any(Task.class));
    }

    @Test
    void testCancelPendingTask() {
        testTask.setStatus("pending");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);
        doNothing().when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        Task cancelled = taskService.cancel("task-001");

        assertEquals("cancelled", cancelled.getStatus());
    }

    @Test
    void testCancelRunningTask() {
        testTask.setStatus("running");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        doThrow(new BusinessException(400, "非法状态转换")).when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        assertThrows(BusinessException.class, () -> {
            taskService.cancel("task-001");
        });
    }

    @Test
    void testRetryFailedTask() {
        testTask.setStatus("failed");
        testTask.setRetryCount(3);
        testTask.setErrorMessage("之前的错误");
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);
        doNothing().when(stateMachine).validateTransition(any(Task.class), any(TaskStatus.class));

        Task retried = taskService.retry("task-001");

        assertEquals("pending", retried.getStatus());
        assertEquals(0, retried.getRetryCount());
        assertNull(retried.getErrorMessage());
    }

    @Test
    void testDeleteTask() {
        when(taskMapper.selectById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        taskService.delete("task-001");

        verify(taskMapper, times(1)).updateById(argThat(task ->
            task.getDeleted() != null && task.getDeleted()
        ));
    }

    @Test
    void testFindStuckRunningTasks() {
        Task stuckTask = new Task();
        stuckTask.setId("stuck-task");
        stuckTask.setStatus("running");
        when(taskMapper.selectList(any())).thenReturn(Arrays.asList(stuckTask));

        List<Task> stuckTasks = taskService.findStuckRunningTasks(30);

        assertEquals(1, stuckTasks.size());
        assertEquals("stuck-task", stuckTasks.get(0).getId());
    }
}