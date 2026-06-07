package com.bend.platform.controller;

import com.bend.platform.dto.ApiResponse;
import com.bend.platform.entity.TaskEvent;
import com.bend.platform.dto.StartStreamingRequest;
import com.bend.platform.dto.StartTaskAutomationRequest;
import com.bend.platform.dto.TaskPauseRequest;
import com.bend.platform.service.TaskControlService;
import com.bend.platform.util.UserContext;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.Map;

@RestController
@RequiredArgsConstructor
public class TaskControlController {

    private final TaskControlService taskControlService;

    @PostMapping("/api/streaming-accounts/{streamingAccountId}/tasks/start-streaming")
    public ApiResponse<Map<String, Object>> startStreaming(
            @PathVariable String streamingAccountId,
            @Valid @RequestBody StartStreamingRequest request) {
        String merchantId = UserContext.getMerchantId();
        Map<String, Object> result = taskControlService.startStreaming(
                streamingAccountId, request, UserContext.getUserId(), merchantId);
        return ApiResponse.success("串流任务已创建", result);
    }

    @PostMapping("/api/tasks/{taskId}/start-automation")
    public ApiResponse<Map<String, Object>> startAutomation(
            @PathVariable String taskId,
            @Valid @RequestBody StartTaskAutomationRequest request) {
        Map<String, Object> result = taskControlService.startAutomation(
                taskId, request, UserContext.getMerchantId());
        return ApiResponse.success("自动化已启动", result);
    }

    @PostMapping("/api/tasks/{taskId}/pause")
    public ApiResponse<Void> pause(
            @PathVariable String taskId,
            @RequestBody(required = false) TaskPauseRequest request) {
        if (request == null) {
            request = new TaskPauseRequest();
        }
        taskControlService.pauseTask(taskId, request, UserContext.getMerchantId());
        return ApiResponse.success("任务已暂停", null);
    }

    @PostMapping("/api/tasks/{taskId}/resume")
    public ApiResponse<Void> resume(@PathVariable String taskId) {
        taskControlService.resumeTask(taskId, UserContext.getMerchantId());
        return ApiResponse.success("任务已恢复", null);
    }

    @PostMapping("/api/tasks/{taskId}/cancel")
    public ApiResponse<Void> cancel(@PathVariable String taskId) {
        taskControlService.cancelTask(taskId, UserContext.getMerchantId());
        return ApiResponse.success("任务已取消", null);
    }

    @PostMapping("/api/tasks/{taskId}/terminate")
    public ApiResponse<Void> terminate(@PathVariable String taskId) {
        taskControlService.terminateTask(taskId, UserContext.getMerchantId());
        return ApiResponse.success("任务已终止", null);
    }

    @PostMapping("/api/tasks/{taskId}/window/{action}")
    public ApiResponse<Void> windowControl(
            @PathVariable String taskId,
            @PathVariable String action) {
        taskControlService.windowControl(taskId, action, UserContext.getMerchantId());
        return ApiResponse.success(null);
    }

    @PostMapping("/api/tasks/{taskId}/skip-game-account/{gameAccountId}")
    public ApiResponse<Void> skipGameAccount(
            @PathVariable String taskId,
            @PathVariable String gameAccountId) {
        taskControlService.skipGameAccount(taskId, gameAccountId, UserContext.getMerchantId());
        return ApiResponse.success(null);
    }

    @PostMapping("/api/tasks/{taskId}/reconnect-stream")
    public ApiResponse<Void> reconnectStream(@PathVariable String taskId) {
        taskControlService.reconnectStream(taskId, UserContext.getMerchantId());
        return ApiResponse.success(null);
    }

    @GetMapping("/api/tasks/{taskId}/detail")
    public ApiResponse<Map<String, Object>> getDetail(@PathVariable String taskId) {
        return ApiResponse.success(
                taskControlService.getTaskDetail(taskId, UserContext.getMerchantId()));
    }

    @GetMapping("/api/tasks/{taskId}/events")
    public ApiResponse<List<TaskEvent>> getEvents(
            @PathVariable String taskId,
            @RequestParam(defaultValue = "50") int limit) {
        return ApiResponse.success(
                taskControlService.getTaskEvents(taskId, UserContext.getMerchantId(), limit));
    }

    @GetMapping("/api/agents/{agentId}/active-tasks")
    public ApiResponse<List<Map<String, Object>>> activeTasks(@PathVariable String agentId) {
        return ApiResponse.success(
                taskControlService.getActiveTasks(agentId, UserContext.getMerchantId()));
    }
}
