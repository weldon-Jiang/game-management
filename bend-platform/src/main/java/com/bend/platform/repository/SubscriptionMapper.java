package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.Subscription;
import org.apache.ibatis.annotations.Mapper;

@Mapper
public interface SubscriptionMapper extends BaseMapper<Subscription> {
}
