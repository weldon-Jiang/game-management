package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.ActivationCode;
import org.apache.ibatis.annotations.Mapper;

/**
 * 激活码Mapper接口
 */
@Mapper
public interface ActivationCodeMapper extends BaseMapper<ActivationCode> {
}