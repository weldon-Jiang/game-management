package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.MerchantGroup;
import org.apache.ibatis.annotations.Mapper;

/**
 * 商户VIP分组Mapper接口
 */
@Mapper
public interface MerchantGroupMapper extends BaseMapper<MerchantGroup> {
}
