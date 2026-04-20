package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.SystemAlert;
import org.apache.ibatis.annotations.Mapper;

/**
 * 系统告警Mapper
 */
@Mapper
public interface SystemAlertMapper extends BaseMapper<SystemAlert> {
}
