package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.TaskGameAccountStatus;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;

@Mapper
public interface TaskGameAccountStatusMapper extends BaseMapper<TaskGameAccountStatus> {

    @Select("SELECT * FROM task_game_account_status WHERE task_id = #{taskId}")
    List<TaskGameAccountStatus> findByTaskId(@Param("taskId") String taskId);

    @Select("SELECT * FROM task_game_account_status WHERE task_id = #{taskId} AND status = #{status}")
    List<TaskGameAccountStatus> findByTaskIdAndStatus(@Param("taskId") String taskId, @Param("status") String status);
}
