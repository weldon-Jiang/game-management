package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 操作日志实体
 * 用于记录系统操作审计日志
 */
@Data
@TableName("operation_log")
public class OperationLog {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String userId;

    private String merchantId;

    private String action;

    private String targetType;

    private String targetId;

    private String beforeValue;

    private String afterValue;

    private String ipAddress;

    private String userAgent;

    private String description;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}
