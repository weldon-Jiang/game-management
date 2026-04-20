package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 系统告警实体
 *
 * 功能说明：
 * - 记录系统产生的各类告警信息
 * - 支持告警级别分类和状态管理
 * - 用于告警历史查询和分析
 *
 * 告警级别：
 * - CRITICAL: 严重（系统不可用）
 * - HIGH: 高（需要立即处理）
 * - MEDIUM: 中（需要关注）
 * - LOW: 低（提示信息）
 *
 * 告警类型：
 * - AGENT_OFFLINE: Agent离线
 * - TASK_FAILED: 任务失败
 * - HIGH_CPU: CPU过高
 * - HIGH_MEMORY: 内存过高
 * - HIGH_ERROR_RATE: 错误率过高
 * - AGENT_VERSION_MISMATCH: Agent版本不匹配
 * - XBOX_CONNECTION_FAILED: Xbox连接失败
 * - AUTH_FAILURE: 认证失败
 *
 * 告警状态：
 * - TRIGGERED: 已触发
 * - ACKNOWLEDGED: 已确认
 * - RESOLVED: 已解决
 * - IGNORED: 已忽略
 */
@Data
@TableName("system_alert")
public class SystemAlert {

    /**
     * 主键ID
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * 告警编码
     * 用于唯一标识特定类型的告警
     */
    private String alertCode;

    /**
     * 告警名称
     */
    private String alertName;

    /**
     * 告警级别
     * CRITICAL/HIGH/MEDIUM/LOW
     */
    private String severity;

    /**
     * 告警类型
     */
    private String alertType;

    /**
     * 告警消息
     */
    private String message;

    /**
     * 告警详情（JSON格式）
     */
    private String details;

    /**
     * 关联的商户ID
     * 用于多租户告警隔离
     */
    private String merchantId;

    /**
     * 关联的Agent ID
     */
    private String agentId;

    /**
     * 关联的任务ID
     */
    private String taskId;

    /**
     * 告警状态
     * TRIGGERED/ACKNOWLEDGED/RESOLVED/IGNORED
     */
    private String status;

    /**
     * 触发时间
     */
    private LocalDateTime triggeredAt;

    /**
     * 确认时间
     */
    private LocalDateTime acknowledgedAt;

    /**
     * 确认人ID
     */
    private String acknowledgedBy;

    /**
     * 解决时间
     */
    private LocalDateTime resolvedAt;

    /**
     * 解决人ID
     */
    private String resolvedBy;

    /**
     * 解决备注
     */
    private String resolutionNote;

    /**
     * 备注说明
     */
    private String remark;

    /**
     * 创建时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime createdAt;

    /**
     * 更新时间
     */
    @TableField(fill = FieldFill.INSERT_UPDATE)
    private LocalDateTime updatedAt;
}
