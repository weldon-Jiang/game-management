package com.bend.platform.controller;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.GameAccount;
import com.bend.platform.entity.Task;
import com.bend.platform.repository.TaskMapper;
import com.bend.platform.service.GameAccountService;
import com.bend.platform.service.TaskService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.Arrays;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
class AgentCallbackControllerTest {

    @Mock
    private TaskService taskService;

    @Mock
    private GameAccountService gameAccountService;

    @Mock
    private TaskMapper taskMapper;

    @InjectMocks
    private AgentCallbackController controller;

    private Task testTask;
    private GameAccount testGameAccount1;
    private GameAccount testGameAccount2;

    @BeforeEach
    void setUp() {
        testTask = new Task();
        testTask.setId("task-001");
        testTask.setName("测试任务");
        testTask.setStreamingAccountId("sa-001");
        testTask.setStatus("running");

        testGameAccount1 = new GameAccount();
        testGameAccount1.setId("ga-001");
        testGameAccount1.setXboxGameName("Player1");
        testGameAccount1.setTodayMatchCount(2);
        testGameAccount1.setDailyMatchLimit(3);

        testGameAccount2 = new GameAccount();
        testGameAccount2.setId("ga-002");
        testGameAccount2.setXboxGameName("Player2");
        testGameAccount2.setTodayMatchCount(3);
        testGameAccount2.setDailyMatchLimit(3);
    }

    @Test
    void testGetGameAccountsStatus_Success() {
        when(taskService.findById("task-001")).thenReturn(testTask);
        when(gameAccountService.findByStreamingId("sa-001"))
            .thenReturn(Arrays.asList(testGameAccount1, testGameAccount2));

        ApiResponse<List<Map<String, Object>>> response = controller.getGameAccountsStatus("task-001");

        assertEquals(200, response.getCode());
        assertNotNull(response.getData());
        assertEquals(2, response.getData().size());

        Map<String, Object> ga1Status = response.getData().get(0);
        assertEquals("ga-001", ga1Status.get("id"));
        assertEquals("Player1", ga1Status.get("gamertag"));
        assertEquals(2, ga1Status.get("completedCount"));
        assertEquals(3, ga1Status.get("targetMatches"));
        assertEquals(false, ga1Status.get("completed"));
    }

    @Test
    void testGetGameAccountsStatus_TaskNotFound() {
        when(taskService.findById("non-existent")).thenReturn(null);

        ApiResponse<List<Map<String, Object>>> response = controller.getGameAccountsStatus("non-existent");

        assertEquals(404, response.getCode());
        assertNull(response.getData());
    }

    @Test
    void testGetGameAccountsStatus_NoStreamingAccount() {
        testTask.setStreamingAccountId(null);
        when(taskService.findById("task-001")).thenReturn(testTask);

        ApiResponse<List<Map<String, Object>>> response = controller.getGameAccountsStatus("task-001");

        assertEquals(400, response.getCode());
    }

    @Test
    void testReportMatchComplete_Success() {
        when(gameAccountService.findById("ga-001")).thenReturn(testGameAccount1);
        when(taskService.findById("task-001")).thenReturn(testTask);
        when(gameAccountService.findByStreamingId("sa-001"))
            .thenReturn(Arrays.asList(testGameAccount1, testGameAccount2));
        doNothing().when(gameAccountService).update(any(), any());

        ApiResponse<Map<String, Object>> response = controller.reportMatchComplete(
            "task-001", "ga-001", 3);

        assertEquals(200, response.getCode());
        assertNotNull(response.getData());
        assertEquals(true, response.getData().get("allCompleted"));

        verify(gameAccountService).update(eq("ga-001"), any(GameAccount.class));
    }

    @Test
    void testReportMatchComplete_GameAccountNotFound() {
        when(gameAccountService.findById("non-existent")).thenReturn(null);

        ApiResponse<Map<String, Object>> response = controller.reportMatchComplete(
            "task-001", "non-existent", 3);

        assertEquals(404, response.getCode());
    }

    @Test
    void testReportMatchComplete_TaskNotFound() {
        when(gameAccountService.findById("ga-001")).thenReturn(testGameAccount1);
        when(taskService.findById("non-existent")).thenReturn(null);

        ApiResponse<Map<String, Object>> response = controller.reportMatchComplete(
            "non-existent", "ga-001", 3);

        assertEquals(404, response.getCode());
    }

    @Test
    void testReportMatchComplete_NotAllCompleted() {
        testGameAccount1.setTodayMatchCount(2);
        testGameAccount2.setTodayMatchCount(2);

        when(gameAccountService.findById("ga-001")).thenReturn(testGameAccount1);
        when(taskService.findById("task-001")).thenReturn(testTask);
        when(gameAccountService.findByStreamingId("sa-001"))
            .thenReturn(Arrays.asList(testGameAccount1, testGameAccount2));
        doNothing().when(gameAccountService).update(any(), any());

        ApiResponse<Map<String, Object>> response = controller.reportMatchComplete(
            "task-001", "ga-001", 3);

        assertEquals(200, response.getCode());
        assertEquals(false, response.getData().get("allCompleted"));
    }

    @Test
    void testReportTaskProgress_Completed() {
        when(taskService.findById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Map<String, Object> progressData = Map.of(
            "step", "STEP4",
            "status", "COMPLETED",
            "message", "任务完成"
        );

        ApiResponse<Void> response = controller.reportTaskProgress("task-001", progressData);

        assertEquals(200, response.getCode());
        assertEquals("completed", testTask.getStatus());
        verify(taskMapper, times(1)).updateById(testTask);
    }

    @Test
    void testReportTaskProgress_Failed() {
        when(taskService.findById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Map<String, Object> progressData = Map.of(
            "step", "STEP2",
            "status", "FAILED",
            "message", "Xbox连接失败"
        );

        ApiResponse<Void> response = controller.reportTaskProgress("task-001", progressData);

        assertEquals(200, response.getCode());
        assertEquals("failed", testTask.getStatus());
        assertEquals("Xbox连接失败", testTask.getErrorMessage());
        verify(taskMapper, times(1)).updateById(testTask);
    }

    @Test
    void testReportTaskProgress_Running() {
        testTask.setStatus("pending");
        when(taskService.findById("task-001")).thenReturn(testTask);
        when(taskMapper.updateById(any(Task.class))).thenReturn(1);

        Map<String, Object> progressData = Map.of(
            "step", "STEP1",
            "status", "RUNNING",
            "message", "登录中"
        );

        ApiResponse<Void> response = controller.reportTaskProgress("task-001", progressData);

        assertEquals(200, response.getCode());
        assertEquals("running", testTask.getStatus());
        assertNotNull(testTask.getStartedTime());
        verify(taskMapper, times(1)).updateById(testTask);
    }

    @Test
    void testReportTaskProgress_TaskNotFound() {
        when(taskService.findById("non-existent")).thenReturn(null);

        Map<String, Object> progressData = Map.of(
            "step", "STEP1",
            "status", "RUNNING"
        );

        ApiResponse<Void> response = controller.reportTaskProgress("non-existent", progressData);

        assertEquals(404, response.getCode());
    }
}
