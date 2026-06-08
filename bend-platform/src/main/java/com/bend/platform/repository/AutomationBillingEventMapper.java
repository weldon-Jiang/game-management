package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.AutomationBillingEvent;
import org.apache.ibatis.annotations.Mapper;

/**
 * 自动化计费事件Mapper接口
 */
@Mapper
public interface AutomationBillingEventMapper extends BaseMapper<AutomationBillingEvent> {
}
