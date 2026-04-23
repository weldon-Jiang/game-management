package com.bend.platform.entity;

import com.baomidou.mybatisplus.annotation.*;
import lombok.Data;
import java.time.LocalDateTime;

/**
 * 系统监控指标实体
 *
 * 功能说明：
 * - 记录系统运行时的各项性能指标
 * - 用于监控面板展示和趋势分析
 * - 支持指标历史查询
 *
 * 指标类型：
 * - cpu: CPU使用率
 * - memory: 内存使用率
 * - disk: 磁盘使用率
 * - agent_online: 在线Agent数量
 * - task_running: 运行中任务数
 * - task_success_rate: 任务成功率
 * - response_time: 平均响应时间
 * - concurrent_connections: 并发连接数
 */
@Data
@TableName("system_metrics")
public class SystemMetrics {

    /**
     * 主键ID
     */
    @TableId(type = IdType.ASSIGN_UUID)
    private String id;

    /**
     * 指标类型
     * cpu/memory/disk/agent_online/task_running/success_rate/response_time
     */
    private String metricType;

    /**
     * 指标名称
     */
    private String metricName;

    /**
     * 指标值
     */
    private Double value;

    /**
     * 指标单位
     * %/个/秒/ms
     */
    private String unit;

    /**
     * 服务器主机名
     * 用于多服务器部署时区分
     */
    private String hostName;

    /**
     * 备注说明
     */
    private String description;

    /**
     * 记录时间
     */
    @TableField(fill = FieldFill.INSERT)
    private LocalDateTime recordedTime;
}
