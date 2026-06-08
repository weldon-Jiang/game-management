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

    /** 计费事件所属商户，用于余额扣减隔离。 */
    private String merchantId;
    /** 关联自动化任务 ID。 */
    private String taskId;
    /** 长寿命任务的多轮串流会话 ID，参与幂等键生成。 */
    private String sessionId;
    /** 串流账号 ID，便于按窗口资源追溯计费。 */
    private String streamingAccountId;
    /** 实际完成可计费动作的游戏账号 ID。 */
    private String gameAccountId;
    /** Step4 生效的自动化类型，如 squad_battle / auction_transfer。 */
    private String gameActionType;
    /** 计费单元：match_completed 或 transfer_round 等。 */
    private String billingUnit;
    /** 同一任务/账号/单元下的序号，从 1 递增。 */
    private Integer unitIndex;
    /** 幂等键，数据库唯一约束防止 Agent 重试重复扣点。 */
    private String idempotentKey;
    /** 本次事件实际扣除点数，0 表示订阅/月度免费。 */
    private Integer pointsDeducted;
    /** 本次事件带来的金币变化，可为 0。 */
    private Integer coinsDelta;
    /** 事件状态，如 recorded / duplicate。 */
    private String status;
    /** Agent 原始 payload JSON，便于审计与排错。 */
    private String payload;

    /** 记录创建时间，由 MyBatis 自动填充。 */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdTime;
}
