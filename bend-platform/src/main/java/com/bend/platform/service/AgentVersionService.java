package com.bend.platform.service;

import com.baomidou.mybatisplus.core.metadata.IPage;
import com.bend.platform.dto.AgentVersionPageRequest;
import com.bend.platform.entity.AgentVersion;
import java.util.List;

/**
 * Agent版本服务接口
 */
public interface AgentVersionService {

    AgentVersion create(AgentVersion version);

    AgentVersion findById(String id);

    AgentVersion findByVersion(String version);

    List<AgentVersion> findAll();

    List<AgentVersion> findActive();

    IPage<AgentVersion> findPage(AgentVersionPageRequest request);

    AgentVersion findLatest();

    AgentVersion findLatestMandatory();

    AgentVersion findUpdate(String currentVersion);

    AgentVersion publish(AgentVersion version);

    void unpublish(String id);

    void delete(String id);
}
