package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.StreamingAccountAuthCache;
import org.apache.ibatis.annotations.Mapper;

/**
 * 串流账号 xblive Token 缓存 Mapper。
 */
@Mapper
public interface StreamingAccountAuthCacheMapper extends BaseMapper<StreamingAccountAuthCache> {
}
