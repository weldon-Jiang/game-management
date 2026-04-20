package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.AgentInstancePageRequest;
import com.bend.platform.entity.AgentInstance;

import java.util.List;

/**
 * Agent实例服务接口
 */
public interface AgentInstanceService {

    AgentInstance create(AgentInstance instance);

    AgentInstance findById(String id);

    AgentInstance findByAgentId(String agentId);

    List<AgentInstance> findAll();

    IPage<AgentInstance> findAll(AgentInstancePageRequest request);

    List<AgentInstance> findAllByMerchantId(String merchantId);

    IPage<AgentInstance> findPageByMerchantId(String merchantId, AgentInstancePageRequest request);

    IPage<AgentInstance> findPageWithFilters(AgentInstancePageRequest request);

    boolean validateCredentials(String agentId, String agentSecret);

    void updateHeartbeat(String agentId);

    void updateHeartbeat(String agentId, String status, String currentTaskId, String currentStreamingId, String version);

    void updateStatus(String id, String status);

    void updateByAgentId(AgentInstance instance);

    void bindStreaming(String id, String streamingId);

    void unbindStreaming(String id);

    void bindTask(String id, String taskId);

    void unbindTask(String id);

    void delete(String id);

    void offlineByTimeout(int minutes);
}
