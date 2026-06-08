package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.Task;
import org.apache.ibatis.annotations.Mapper;

/**
 * 自动化任务Mapper接口
 */
@Mapper
public interface TaskMapper extends BaseMapper<Task> {
}
