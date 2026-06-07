package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 任务内单个游戏账号的执行状态。
 *
 * <p>一条任务可能绑定多个游戏账号，本实体用于记录每个账号在当前
 * streaming session 中的准备、开通、比赛和结算进度。前端任务详情页和
 * 计费事件都依赖这些字段展示账号级进度。
 */
@Data
@TableName("task_game_account_status")
public class TaskGameAccountStatus {

    /** 状态记录主键。 */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /** 所属自动化任务 ID。 */
    private String taskId;

    /** 当前执行的游戏账号 ID。 */
    private String gameAccountId;

    /** 游戏账号所属的串流账号 ID。 */
    private String streamingAccountId;

    /** 账号级主状态，取值见 {@code TaskGameAccountStatusEnum}。 */
    private String status;

    /** 当前长寿命串流会话 ID，用于区分同一任务的多轮自动化。 */
    private String sessionId;
    /** 账号在当前会话中的细分阶段，如 pending/provisioning/gaming/completed。 */
    private String phase;
    /** Step4 实际执行的自动化类型。 */
    private String gameActionType;
    /** 当前比赛序号，从 1 开始，供前端展示本账号比赛进度。 */
    private Integer matchIndex;
    /** 本账号本轮计划执行的比赛总数。 */
    private Integer matchTotal;
    /** 账号开通/档案绑定阶段，如 creating_profile、binding_profile。 */
    private String provisioningPhase;
    /** 当前开通步骤序号。 */
    private Integer provisioningStep;
    /** 开通步骤总数。 */
    private Integer provisioningStepTotal;
    /** 当前开通阶段展示给前端的说明。 */
    private String provisioningMessage;
    /** 当前占用账号的模块，如 provisioning、step4、manual_control。 */
    private String activeModule;

    /** 当前任务内已成功完成的比赛或计费单元数量。 */
    private Integer completedCount;

    /** 当前任务内失败次数。 */
    private Integer failedCount;

    /** 当前任务内计划或累计比赛数量，兼容旧字段展示。 */
    private Integer totalMatches;

    /** 最近一场比赛完成或失败的时间。 */
    private LocalDateTime lastMatchTime;

    /** 账号开始被当前任务处理的时间。 */
    private LocalDateTime startedTime;

    /** 账号进入终态的时间。 */
    private LocalDateTime completedTime;

    /** 账号级失败原因或最后错误消息。 */
    private String errorMessage;

    /** 记录创建时间，由 MyBatis 自动填充。 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;

    /** 记录更新时间，由 MyBatis 自动填充。 */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedTime;

    /** 前端展示用游戏账号名称，非表字段。 */
    @TableField(exist = false)
    private String gameAccountName;

    /** 前端展示用串流账号名称，非表字段。 */
    @TableField(exist = false)
    private String streamingAccountName;

    /** 游戏账号每日比赛上限，非表字段。 */
    @TableField(exist = false)
    private Integer dailyMatchLimit;

    /** 游戏账号今日已完成比赛数，非表字段。 */
    @TableField(exist = false)
    private Integer todayMatchCount;

    /** 游戏账号累计金币，非表字段。 */
    @TableField(exist = false)
    private Integer totalCoins;

    /** 游戏账号今日金币，非表字段。 */
    @TableField(exist = false)
    private Integer todayCoins;

    /** 当前 DR 等级，非表字段。 */
    @TableField(exist = false)
    private String drLevel;

    /** 同账号再次自动化的冷却小时数，非表字段。 */
    @TableField(exist = false)
    private Integer cooldownHours;

    /** 今日最后一次完成计费事件时间，非表字段。 */
    @TableField(exist = false)
    private LocalDateTime todayLastCompletedTime;
}
