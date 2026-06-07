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

    private String sessionId;
    private String phase;
    private String gameActionType;
    private Integer matchIndex;
    private Integer matchTotal;
    private String provisioningPhase;
    private Integer provisioningStep;
    private Integer provisioningStepTotal;
    private String provisioningMessage;
    private String activeModule;

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

    @TableField(exist = false)
    private Integer dailyMatchLimit;

    @TableField(exist = false)
    private Integer todayMatchCount;

    @TableField(exist = false)
    private Integer totalCoins;

    @TableField(exist = false)
    private Integer todayCoins;

    @TableField(exist = false)
    private String drLevel;

    @TableField(exist = false)
    private Integer cooldownHours;

    @TableField(exist = false)
    private LocalDateTime todayLastCompletedTime;
}
