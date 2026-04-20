package com.bend.platform.controller;

import com.bend.platform.entity.Task;
import com.bend.platform.service.TaskService;
import com.bend.platform.websocket.WebSocketMessageService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;

import java.util.Arrays;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * TaskController 单元测试
 *
 * 测试场景：
 * - 任务创建
 * - 任务查询
 * - 任务状态变更
 * - 任务分配和取消
 *
 * 使用Mockito直接测试Controller方法
 */
@ExtendWith(MockitoExtension.class)
class TaskControllerTest {

    @Mock
    private TaskService taskService;

    @Mock
    private WebSocketMessageService messageService;

    @Mock
    private com.bend.platform.util.JwtUtil jwtUtil;

    @InjectMocks
    private TaskController taskController;

    private Task testTask;
    private String authToken = "Bearer test-token";

    @BeforeEach
    void setUp() {
        testTask = new Task();
        testTask.setId("task-001");
        testTask.setName("测试任务");
        testTask.setType("stream_control");
        testTask.setStatus("pending");
    }

    /**
     * 测试：创建任务
     *
     * 验证：
     * - 调用taskService.create
     * - 返回ApiResponse.success
     */
    @Test
    void testCreateTask() {
        when(taskService.create(any(Task.class))).thenReturn(testTask);

        var response = taskController.create(authToken, testTask);

        assertNotNull(response);
        assertEquals(0, response.getCode());
        assertEquals("创建成功", response.getMessage());
        verify(taskService, times(1)).create(any(Task.class));
    }

    /**
     * 测试：获取单个任务
     *
     * 验证：
     * - 任务存在时返回任务详情
     */
    @Test
    void testGetTaskById() {
        when(taskService.findById("task-001")).thenReturn(testTask);

        var response = taskController.getById("task-001");

        assertNotNull(response);
        assertEquals(0, response.getCode());
        assertEquals("task-001", response.getData().getId());
    }

    /**
     * 测试：获取不存在的任务
     *
     * 验证：
     * - 返回404错误
     */
    @Test
    void testGetTaskNotFound() {
        when(taskService.findById("non-existent")).thenReturn(null);

        var response = taskController.getById("non-existent");

        assertEquals(404, response.getCode());
    }

    /**
     * 测试：获取Agent的任务列表
     *
     * 验证：
     * - 返回该Agent的所有任务
     */
    @Test
    void testListTasksByAgent() {
        List<Task> tasks = Arrays.asList(testTask);
        when(taskService.findByAgentId("agent-001")).thenReturn(tasks);

        var response = taskController.listByAgent("agent-001");

        assertNotNull(response);
        assertEquals(0, response.getCode());
        assertEquals(1, response.getData().size());
    }

    /**
     * 测试：获取Agent的待处理任务
     */
    @Test
    void testListPendingTasksByAgent() {
        List<Task> tasks = Arrays.asList(testTask);
        when(taskService.findPendingByAgentId("agent-001")).thenReturn(tasks);

        var response = taskController.listPendingByAgent("agent-001");

        assertNotNull(response);
        assertEquals(0, response.getCode());
        assertEquals(1, response.getData().size());
    }

    /**
     * 测试：分配任务给Agent（Agent在线）
     *
     * 验证：
     * - 分配成功
     */
    @Test
    void testAssignTaskToOnlineAgent() {
        when(messageService.isAgentOnline("agent-001")).thenReturn(true);
        when(taskService.assignToAgent("task-001", "agent-001")).thenReturn(testTask);

        var response = taskController.assign("task-001", "agent-001");

        assertEquals(0, response.getCode());
        assertEquals("分配成功", response.getMessage());
    }

    /**
     * 测试：分配任务给Agent（Agent离线）
     *
     * 验证：
     * - 返回400错误
     */
    @Test
    void testAssignTaskToOfflineAgent() {
        when(messageService.isAgentOnline("agent-001")).thenReturn(false);

        var response = taskController.assign("task-001", "agent-001");

        assertEquals(400, response.getCode());
        assertEquals("Agent不在线", response.getMessage());
    }

    /**
     * 测试：开始执行任务
     */
    @Test
    void testStartTask() {
        when(taskService.start("task-001")).thenReturn(testTask);

        var response = taskController.start("task-001");

        assertEquals(0, response.getCode());
        assertEquals("开始执行", response.getMessage());
    }

    /**
     * 测试：标记任务完成
     */
    @Test
    void testCompleteTask() {
        when(taskService.complete(eq("task-001"), anyString())).thenReturn(testTask);

        var response = taskController.complete("task-001", java.util.Map.of("result", "执行成功"));

        assertEquals(0, response.getCode());
        assertEquals("任务完成", response.getMessage());
    }

    /**
     * 测试：标记任务失败
     */
    @Test
    void testFailTask() {
        when(taskService.fail(eq("task-001"), anyString())).thenReturn(testTask);

        var response = taskController.fail("task-001", java.util.Map.of("errorMessage", "执行失败"));

        assertEquals(0, response.getCode());
        assertEquals("标记失败", response.getMessage());
    }

    /**
     * 测试：取消任务
     */
    @Test
    void testCancelTask() {
        when(taskService.cancel("task-001")).thenReturn(testTask);

        var response = taskController.cancel("task-001");

        assertEquals(0, response.getCode());
        assertEquals("取消成功", response.getMessage());
    }

    /**
     * 测试：重试任务
     */
    @Test
    void testRetryTask() {
        when(taskService.retry("task-001")).thenReturn(testTask);

        var response = taskController.retry("task-001");

        assertEquals(0, response.getCode());
        assertEquals("重试成功", response.getMessage());
    }

    /**
     * 测试：删除任务
     */
    @Test
    void testDeleteTask() {
        doNothing().when(taskService).delete("task-001");

        var response = taskController.delete("task-001");

        assertEquals(0, response.getCode());
        assertEquals("删除成功", response.getMessage());
        verify(taskService, times(1)).delete("task-001");
    }

    /**
     * 测试：获取任务类型列表
     */
    @Test
    void testGetTaskTypes() {
        var response = taskController.getTypes();

        assertEquals(0, response.getCode());
        assertNotNull(response.getData());
        assertTrue(response.getData().contains("template_match"));
        assertTrue(response.getData().contains("stream_control"));
    }

    /**
     * 测试：获取任务状态列表
     */
    @Test
    void testGetTaskStatuses() {
        var response = taskController.getStatuses();

        assertEquals(0, response.getCode());
        assertNotNull(response.getData());
        assertTrue(response.getData().contains("pending"));
        assertTrue(response.getData().contains("running"));
        assertTrue(response.getData().contains("completed"));
        assertTrue(response.getData().contains("failed"));
    }
}
