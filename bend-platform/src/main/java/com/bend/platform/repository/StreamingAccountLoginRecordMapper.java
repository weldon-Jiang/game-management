package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.StreamingAccountLoginRecord;
import org.apache.ibatis.annotations.Mapper;

/**
 * 流媒体账号登录记录Mapper接口
 */
@Mapper
public interface StreamingAccountLoginRecordMapper extends BaseMapper<StreamingAccountLoginRecord> {
}