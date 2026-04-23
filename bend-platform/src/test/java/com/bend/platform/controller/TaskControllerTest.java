package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.Task;
import com.bend.platform.service.TaskService;
import com.bend.platform.websocket.WebSocketMessageService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

/**
 * TaskController 单元测试
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

    @BeforeEach
    void setUp() {
        testTask = new Task();
        testTask.setId("task-001");
        testTask.setName("测试任务");
        testTask.setType("stream_control");
        testTask.setStatus("pending");
    }

    @Test
    void testCreateTask() {
        when(taskService.create(any(Task.class))).thenReturn(testTask);

        ApiResponse<Task> response = taskController.create(testTask);

        assertNotNull(response);
        assertEquals(200, response.getCode());
        assertEquals("创建成功", response.getMessage());
        verify(taskService, times(1)).create(any(Task.class));
    }

    @Test
    void testGetTaskById() {
        when(taskService.findById("task-001")).thenReturn(testTask);

        ApiResponse<Task> response = taskController.getById("task-001");

        assertNotNull(response);
        assertEquals(200, response.getCode());
        assertEquals("task-001", response.getData().getId());
    }

    @Test
    void testGetTaskNotFound() {
        when(taskService.findById("non-existent")).thenReturn(null);

        ApiResponse<Task> response = taskController.getById("non-existent");

        assertEquals(404, response.getCode());
    }

    @Test
    void testListTasksByAgent() {
        List<Task> tasks = Arrays.asList(testTask);
        when(taskService.findByAgentId("agent-001")).thenReturn(tasks);

        ApiResponse<List<Task>> response = taskController.listByAgent("agent-001");

        assertNotNull(response);
        assertEquals(200, response.getCode());
        assertEquals(1, response.getData().size());
    }

    @Test
    void testListPendingTasksByAgent() {
        List<Task> tasks = Arrays.asList(testTask);
        when(taskService.findPendingByAgentId("agent-001")).thenReturn(tasks);

        ApiResponse<List<Task>> response = taskController.listPendingByAgent("agent-001");

        assertNotNull(response);
        assertEquals(200, response.getCode());
        assertEquals(1, response.getData().size());
    }

    @Test
    void testAssignTaskToOnlineAgent() {
        when(messageService.isAgentOnline("agent-001")).thenReturn(true);
        when(taskService.assignToAgent("task-001", "agent-001")).thenReturn(testTask);

        ApiResponse<Task> response = taskController.assign("task-001", "agent-001");

        assertEquals(200, response.getCode());
        assertEquals("分配成功", response.getMessage());
    }

    @Test
    void testAssignTaskToOfflineAgent() {
        when(messageService.isAgentOnline("agent-001")).thenReturn(false);

        ApiResponse<Task> response = taskController.assign("task-001", "agent-001");

        assertEquals(400, response.getCode());
        assertEquals("Agent不在线", response.getMessage());
    }

    @Test
    void testStartTask() {
        when(taskService.start("task-001")).thenReturn(testTask);

        ApiResponse<Task> response = taskController.start("task-001");

        assertEquals(200, response.getCode());
        assertEquals("开始执行", response.getMessage());
    }

    @Test
    void testCompleteTask() {
        when(taskService.complete(eq("task-001"), anyString())).thenReturn(testTask);

        Map<String, String> resultData = new HashMap<>();
        resultData.put("result", "执行成功");
        ApiResponse<Task> response = taskController.complete("task-001", resultData);

        assertEquals(200, response.getCode());
        assertEquals("任务完成", response.getMessage());
    }

    @Test
    void testFailTask() {
        when(taskService.fail(eq("task-001"), anyString())).thenReturn(testTask);

        Map<String, String> errorData = new HashMap<>();
        errorData.put("errorMessage", "执行失败");
        ApiResponse<Task> response = taskController.fail("task-001", errorData);

        assertEquals(200, response.getCode());
        assertEquals("标记失败", response.getMessage());
    }

    @Test
    void testCancelTask() {
        when(taskService.cancel("task-001")).thenReturn(testTask);

        ApiResponse<Task> response = taskController.cancel("task-001");

        assertEquals(200, response.getCode());
        assertEquals("取消成功", response.getMessage());
    }

    @Test
    void testRetryTask() {
        when(taskService.retry("task-001")).thenReturn(testTask);

        ApiResponse<Task> response = taskController.retry("task-001");

        assertEquals(200, response.getCode());
        assertEquals("重试成功", response.getMessage());
    }

    @Test
    void testDeleteTask() {
        doNothing().when(taskService).delete("task-001");

        ApiResponse<Void> response = taskController.delete("task-001");

        assertEquals(200, response.getCode());
        assertEquals("删除成功", response.getMessage());
        verify(taskService, times(1)).delete("task-001");
    }

    @Test
    void testGetTaskTypes() {
        ApiResponse<List<String>> response = taskController.getTypes();

        assertEquals(200, response.getCode());
        assertNotNull(response.getData());
        assertTrue(response.getData().contains("template_match"));
        assertTrue(response.getData().contains("stream_control"));
    }

    @Test
    void testGetTaskStatuses() {
        ApiResponse<List<String>> response = taskController.getStatuses();

        assertEquals(200, response.getCode());
        assertNotNull(response.getData());
        assertTrue(response.getData().contains("pending"));
        assertTrue(response.getData().contains("running"));
        assertTrue(response.getData().contains("completed"));
        assertTrue(response.getData().contains("failed"));
    }
}
