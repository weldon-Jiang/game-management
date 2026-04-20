package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.AgentInstance;
import org.apache.ibatis.annotations.Mapper;

/**
 * Agent实例Mapper接口
 */
@Mapper
public interface AgentInstanceMapper extends BaseMapper<AgentInstance> {
}