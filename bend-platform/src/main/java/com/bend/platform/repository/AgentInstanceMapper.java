package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.AgentInstance;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * Agent实例Mapper接口
 */
@Mapper
public interface AgentInstanceMapper extends BaseMapper<AgentInstance> {

    /** 按 agentId 查询未逻辑删除的实例。 */
    @Select("SELECT * FROM agent_instance WHERE agent_id = #{agentId} AND deleted = 0 LIMIT 1")
    AgentInstance selectByAgentId(@Param("agentId") String agentId);

    /** 按 agentId 查询（含已删除），用于注册/恢复场景。 */
    @Select("SELECT * FROM agent_instance WHERE agent_id = #{agentId} LIMIT 1")
    AgentInstance selectByAgentIdIncludeDeleted(@Param("agentId") String agentId);
}
