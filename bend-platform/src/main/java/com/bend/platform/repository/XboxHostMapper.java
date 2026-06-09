package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.XboxHost;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Update;

import java.time.LocalDateTime;

/**
 * Xbox主机Mapper接口
 */
@Mapper
public interface XboxHostMapper extends BaseMapper<XboxHost> {

    @Select("SELECT * FROM xbox_host WHERE merchant_id = #{merchantId} AND xbox_id = #{xboxId} AND deleted = 1")
    XboxHost selectDeletedByMerchantAndXboxId(
            @Param("merchantId") String merchantId,
            @Param("xboxId") String xboxId);

    @Delete("DELETE FROM xbox_host WHERE id = #{id}")
    int physicalDeleteById(@Param("id") String id);

    /**
     * CAS 锁定：未锁、已过期或同一 agent+task 重入时可成功。
     */
    @Update("UPDATE xbox_host SET locked = 1, locked_by_agent_id = #{agentId}, locked_by_task_id = #{taskId}, "
            + "locked_time = NOW(), lock_expires_time = #{expireTime} "
            + "WHERE id = #{id} AND merchant_id = #{merchantId} AND deleted = 0 AND ("
            + "locked = 0 OR lock_expires_time IS NULL OR lock_expires_time < NOW() OR "
            + "(locked_by_agent_id = #{agentId} AND locked_by_task_id = #{taskId}))")
    int casLock(
            @Param("merchantId") String merchantId,
            @Param("id") String id,
            @Param("agentId") String agentId,
            @Param("taskId") String taskId,
            @Param("expireTime") LocalDateTime expireTime);

    /** 仅持有 agent+task 且同商户可解锁。 */
    @Update("UPDATE xbox_host SET locked = 0, locked_by_agent_id = NULL, locked_by_task_id = NULL, "
            + "locked_time = NULL, lock_expires_time = NULL "
            + "WHERE id = #{id} AND merchant_id = #{merchantId} AND deleted = 0 "
            + "AND locked_by_agent_id = #{agentId} AND locked_by_task_id = #{taskId}")
    int casUnlock(
            @Param("merchantId") String merchantId,
            @Param("id") String id,
            @Param("agentId") String agentId,
            @Param("taskId") String taskId);
}