package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.exception.BusinessException;
import com.bend.platform.service.AgentCallbackService;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.assertEquals;
import static org.junit.jupiter.api.Assertions.assertNotNull;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class AgentCallbackControllerTest {

    @Mock
    private AgentCallbackService agentCallbackService;

    @InjectMocks
    private AgentCallbackController controller;

    @Test
    void testReportProgress_Success() {
        Map<String, Object> payload = Map.of(
                "taskId", "task-001",
                "data", Map.of("status", "RUNNING", "step", "STEP1")
        );
        when(agentCallbackService.reportProgress(payload))
                .thenReturn(Map.of("received", true, "action", "CONTINUE"));

        ApiResponse<Map<String, Object>> response = controller.reportProgress(payload);

        assertEquals(200, response.getCode());
        assertNotNull(response.getData());
        assertEquals(true, response.getData().get("received"));
    }

    @Test
    void testReportProgress_BusinessError() {
        Map<String, Object> payload = Map.of("taskId", "task-001", "data", Map.of("status", "RUNNING"));
        when(agentCallbackService.reportProgress(payload))
                .thenThrow(new BusinessException(404, "任务不存在"));

        ApiResponse<Map<String, Object>> response = controller.reportProgress(payload);

        assertEquals(404, response.getCode());
    }

    @Test
    void testGetTaskInfo_Success() {
        when(agentCallbackService.getTaskInfo("task-001"))
                .thenReturn(Map.of("taskId", "task-001", "gameActionType", "daily_match"));

        ApiResponse<Map<String, Object>> response = controller.getTaskInfo("task-001");

        assertEquals(200, response.getCode());
        assertEquals("daily_match", response.getData().get("gameActionType"));
    }

    @Test
    void testGetGameAccountsStatusLegacy_Success() {
        when(agentCallbackService.getGameAccountsStatusLegacy("task-001"))
                .thenReturn(List.of(Map.of("id", "ga-001", "gamertag", "Player1")));

        ApiResponse<List<Map<String, Object>>> response = controller.getGameAccountsStatus("task-001");

        assertEquals(200, response.getCode());
        assertEquals(1, response.getData().size());
    }
}
