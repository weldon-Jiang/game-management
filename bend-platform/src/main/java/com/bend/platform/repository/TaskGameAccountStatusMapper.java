package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.TaskGameAccountStatus;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import java.util.List;

/**
 * 任务游戏账号状态Mapper接口
 */
@Mapper
public interface TaskGameAccountStatusMapper extends BaseMapper<TaskGameAccountStatus> {

    /** 查询任务下全部账号状态记录。 */
    @Select("SELECT * FROM task_game_account_status WHERE task_id = #{taskId}")
    List<TaskGameAccountStatus> findByTaskId(@Param("taskId") String taskId);

    /** 按任务 ID 与主状态筛选账号记录。 */
    @Select("SELECT * FROM task_game_account_status WHERE task_id = #{taskId} AND status = #{status}")
    List<TaskGameAccountStatus> findByTaskIdAndStatus(@Param("taskId") String taskId, @Param("status") String status);

    /**
     * 查询商户下指定游戏账号是否被活跃任务占用（启动自动化冲突检测）。
     */
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
