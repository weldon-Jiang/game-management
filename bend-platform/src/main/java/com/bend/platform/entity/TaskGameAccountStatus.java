package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

@Data
@TableName("task_game_account_status")
public class TaskGameAccountStatus {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String taskId;

    private String gameAccountId;

    private String streamingAccountId;

    private String status;

    private Integer completedCount;

    private Integer failedCount;

    private Integer totalMatches;

    private LocalDateTime lastMatchTime;

    private LocalDateTime startedTime;

    private LocalDateTime completedTime;

    private String errorMessage;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;

    @TableField(exist = false)
    private String gameAccountName;

    @TableField(exist = false)
    private String streamingAccountName;
}
