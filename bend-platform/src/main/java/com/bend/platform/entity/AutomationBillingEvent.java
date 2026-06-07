package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.FieldFill;
import com.baomidou.mybatisplus.annotation.IdType;
import com.baomidou.mybatisplus.annotation.TableField;
import com.baomidou.mybatisplus.annotation.TableId;
import com.baomidou.mybatisplus.annotation.TableName;
import lombok.Data;

import java.time.LocalDateTime;

/**
 * 自动化可计费事件。
 *
 * <p>按任务类型、计费单元与单元序号记录 Agent Step4 上报的真实可计费动作。
 * 唯一键由 task/session/gameAccount/gameActionType/billingUnit/unitIndex 组成，用于保证
 * Agent 重试或网络重放不会重复扣点。</p>
 */
@Data
@TableName("automation_billing_event")
public class AutomationBillingEvent {

    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    private String merchantId;
    private String taskId;
    private String sessionId;
    private String streamingAccountId;
    private String gameAccountId;
    private String gameActionType;
    private String billingUnit;
    private Integer unitIndex;
    private String idempotentKey;
    private Integer pointsDeducted;
    private Integer coinsDelta;
    private String status;
    private String payload;

    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}
