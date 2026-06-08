package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.PointTransaction;
import org.apache.ibatis.annotations.Mapper;

/**
 * 点数流水Mapper接口
 */
@Mapper
public interface PointTransactionMapper extends BaseMapper<PointTransaction> {
}
