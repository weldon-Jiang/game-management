package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.ActivationCodeBatch;
import org.apache.ibatis.annotations.Mapper;

/**
 * 激活码批次Mapper接口
 */
@Mapper
public interface ActivationCodeBatchMapper extends BaseMapper<ActivationCodeBatch> {
}