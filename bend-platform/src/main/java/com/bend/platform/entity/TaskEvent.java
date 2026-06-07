package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("task_event")
public class TaskEvent {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String taskId;
    private String merchantId;
    private String scope;
    private String phase;
    private String status;
    private String message;
    private String gameAccountId;
    private String module;
    private String payload;
    private String sessionId;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}
