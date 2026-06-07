package com.bend.platform.service;

import com.bend.platform.dto.StartStreamingRequest;
import com.bend.platform.dto.StartTaskAutomationRequest;
import com.bend.platform.dto.TaskPauseRequest;

import java.util.List;
import java.util.Map;

public interface TaskControlService {

    Map<String, Object> startStreaming(String streamingAccountId, StartStreamingRequest request,
                                       String userId, String merchantId);

    Map<String, Object> startAutomation(String taskId, StartTaskAutomationRequest request, String merchantId);

    void pauseTask(String taskId, TaskPauseRequest request, String merchantId);

    void resumeTask(String taskId, String merchantId);

    void cancelTask(String taskId, String merchantId);

    void terminateTask(String taskId, String merchantId);

    void windowControl(String taskId, String action, String merchantId);

    void skipGameAccount(String taskId, String gameAccountId, String merchantId);

    void reconnectStream(String taskId, String merchantId);

    Map<String, Object> getTaskDetail(String taskId, String merchantId);

    java.util.List<com.bend.platform.entity.TaskEvent> getTaskEvents(String taskId, String merchantId, int limit);

    List<Map<String, Object>> getActiveTasks(String agentId, String merchantId);
}
