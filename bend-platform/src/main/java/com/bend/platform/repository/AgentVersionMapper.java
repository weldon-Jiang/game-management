package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.AgentVersion;
import org.apache.ibatis.annotations.Mapper;

/**
 * Agent版本Mapper
 */
@Mapper
public interface AgentVersionMapper extends BaseMapper<AgentVersion> {
}
