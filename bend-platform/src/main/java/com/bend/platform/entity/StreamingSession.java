package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;

import java.time.LocalDateTime;

@Data
@TableName("streaming_session")
public class StreamingSession {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String taskId;
    private String merchantId;
    private String streamingAccountId;
    private String xboxHostId;
    private String consoleServerId;
    private String targetAgentId;
    private String phase;
    private String inputMode;
    private String decodeMode;
    private String powerState;
    private String gameActionType;
    private LocalDateTime gameActionLockedAt;
    private String errorCode;
    private String errorMessage;
    private LocalDateTime startedTime;
    private LocalDateTime readyTime;
    private LocalDateTime closedTime;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;
}
