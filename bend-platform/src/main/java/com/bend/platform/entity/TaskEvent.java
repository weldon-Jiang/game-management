package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 任务事件流水：Agent 回调与平台控制面写入，供详情页时间线展示。
 * scope/phase/sessionId 区分任务级、会话级与账号级事件。
 */
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
