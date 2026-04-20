package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * Agent版本实体
 * 管理Agent的版本信息和更新
 */
@Data
@TableName("agent_version")
public class AgentVersion {
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String version;

    private String downloadUrl;

    private String md5Checksum;

    private String changelog;

    private Integer mandatory;

    private Integer forceRestart;

    private String minCompatibleVersion;

    private Integer status;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;

    @TableLogic
    private Boolean deleted;
}
