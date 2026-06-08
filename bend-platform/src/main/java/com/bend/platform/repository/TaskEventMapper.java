package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.TaskEvent;
import org.apache.ibatis.annotations.Mapper;

/**
 * 任务事件Mapper接口
 */
@Mapper
public interface TaskEventMapper extends BaseMapper<TaskEvent> {
}
