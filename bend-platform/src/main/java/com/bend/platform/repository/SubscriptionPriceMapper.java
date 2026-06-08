package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.SubscriptionPrice;
import org.apache.ibatis.annotations.Mapper;

/**
 * 订阅定价Mapper接口
 */
@Mapper
public interface SubscriptionPriceMapper extends BaseMapper<SubscriptionPrice> {
}
