package com.bend.platform.repository;

import com.baomidou.mybatisplus.core.mapper.BaseMapper;
import com.bend.platform.entity.XboxHost;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Param;
import org.apache.ibatis.annotations.Select;

/**
 * Xbox主机Mapper接口
 */
@Mapper
public interface XboxHostMapper extends BaseMapper<XboxHost> {

    @Select("SELECT * FROM xbox_host WHERE xbox_id = #{xboxId} AND deleted = 1")
    XboxHost selectDeletedByXboxId(@Param("xboxId") String xboxId);

    @Delete("DELETE FROM xbox_host WHERE id = #{id}")
    int physicalDeleteById(@Param("id") String id);
}