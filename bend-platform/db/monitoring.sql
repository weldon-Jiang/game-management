-- =====================================================
-- 系统监控和告警相关表
-- =====================================================

-- ---------------------------------------------
-- 系统监控指标表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS system_metrics (
    id VARCHAR(36) PRIMARY KEY COMMENT '主键（UUID）',
    metric_type VARCHAR(50) NOT NULL COMMENT '指标类型: jvm/system/business',
    metric_name VARCHAR(100) NOT NULL COMMENT '指标名称',
    value DOUBLE COMMENT '指标值',
    unit VARCHAR(20) COMMENT '单位: %/bytes/个/秒',
    host_name VARCHAR(100) COMMENT '服务器主机名',
    description VARCHAR(255) COMMENT '指标描述',
    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    INDEX idx_metric_type (metric_type),
    INDEX idx_metric_name (metric_name),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统监控指标表';

-- ---------------------------------------------
-- 系统告警表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS system_alert (
    id VARCHAR(36) PRIMARY KEY COMMENT '主键（UUID）',
    alert_code VARCHAR(50) NOT NULL COMMENT '告警编码',
    alert_name VARCHAR(100) COMMENT '告警名称',
    severity VARCHAR(20) NOT NULL COMMENT '告警级别: CRITICAL/HIGH/MEDIUM/LOW',
    alert_type VARCHAR(50) NOT NULL COMMENT '告警类型',
    message TEXT COMMENT '告警消息',
    details JSON COMMENT '告警详情',
    merchant_id VARCHAR(36) COMMENT '关联商户ID',
    agent_id VARCHAR(36) COMMENT '关联Agent ID',
    task_id VARCHAR(36) COMMENT '关联任务ID',
    status VARCHAR(20) DEFAULT 'TRIGGERED' COMMENT '状态: TRIGGERED/ACKNOWLEDGED/RESOLVED/IGNORED',
    triggered_at DATETIME COMMENT '触发时间',
    acknowledged_at DATETIME COMMENT '确认时间',
    acknowledged_by VARCHAR(36) COMMENT '确认人ID',
    resolved_at DATETIME COMMENT '解决时间',
    resolved_by VARCHAR(36) COMMENT '解决人ID',
    resolution_note TEXT COMMENT '解决备注',
    remark TEXT COMMENT '备注',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_alert_type (alert_type),
    INDEX idx_severity (severity),
    INDEX idx_status (status),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_agent_id (agent_id),
    INDEX idx_triggered_at (triggered_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统告警表';
