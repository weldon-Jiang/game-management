package com.bend.platform.service;

import com.bend.platform.entity.AgentInstance;

public interface AgentLoadControlService {

    boolean canAcceptTask(String agentId);

    void incrementTaskCount(String agentId, String taskId);

    void decrementTaskCount(String agentId, String taskId);

    int getCurrentTaskCount(String agentId);

    AgentInstance getAgentWithLoadInfo(String agentId);
}
