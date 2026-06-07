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

    @Select({
            "<script>",
            "SELECT s.* FROM task_game_account_status s",
            "JOIN task t ON t.id = s.task_id",
            "WHERE t.merchant_id = #{merchantId}",
            "AND t.deleted = 0",
            "AND t.status IN ('pending', 'running', 'paused')",
            "AND s.status NOT IN ('completed', 'failed', 'cancelled', 'skipped', 'timeout')",
            "AND s.game_account_id IN",
            "<foreach collection='gameAccountIds' item='id' open='(' separator=',' close=')'>",
            "#{id}",
            "</foreach>",
            "</script>"
    })
    List<TaskGameAccountStatus> findActiveOccupancies(
            @Param("merchantId") String merchantId,
            @Param("gameAccountIds") List<String> gameAccountIds);
}
