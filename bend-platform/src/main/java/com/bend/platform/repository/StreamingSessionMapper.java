package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.StreamingSession;
import org.apache.ibatis.annotations.Mapper;

/**
 * 串流会话Mapper接口
 */
@Mapper
public interface StreamingSessionMapper extends BaseMapper<StreamingSession> {
}
