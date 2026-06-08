package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.AutomationUsage;
import org.apache.ibatis.annotations.Mapper;

/**
 * 自动化用量记录Mapper接口
 */
@Mapper
public interface AutomationUsageMapper extends BaseMapper<AutomationUsage> {
}
