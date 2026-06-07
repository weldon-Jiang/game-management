package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.StreamingSession;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface StreamingSessionMapper extends BaseMapper<StreamingSession> {
}
