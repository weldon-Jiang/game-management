package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.StreamingAccount;
import org.apache.ibatis.annotations.Mapper;

/**
 * 流媒体账号Mapper接口
 */
@Mapper
public interface StreamingAccountMapper extends BaseMapper<StreamingAccount> {
}