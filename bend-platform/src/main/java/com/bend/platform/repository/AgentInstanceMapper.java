package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.AgentInstance;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

@Mapper
public interface AgentInstanceMapper extends BaseMapper<AgentInstance> {

    @Select("SELECT * FROM agent_instance WHERE agent_id = #{agentId} AND deleted = 0 LIMIT 1")
    AgentInstance selectByAgentId(@Param("agentId") String agentId);
}
