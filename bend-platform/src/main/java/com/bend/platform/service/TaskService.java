package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.TaskPageRequest;
import com.bend.platform.entity.Task;
import java.util.List;

/**
 * 任务服务接口
 */
public interface TaskService {

    Task create(Task task);

    Task findById(String id);

    List<Task> findByAgentId(String agentId);

    List<Task> findPendingByAgentId(String agentId);

    IPage<Task> findPage(TaskPageRequest request);

    Task assignToAgent(String taskId, String agentId);

    Task start(String taskId);

    Task complete(String taskId, String result);

    Task fail(String taskId, String errorMessage);

    Task cancel(String taskId);

    Task retry(String taskId);

    void delete(String id);

    void cancelByStreamingAccountId(String streamingAccountId);

    List<Task> findByStreamingAccountId(String streamingAccountId);
}
