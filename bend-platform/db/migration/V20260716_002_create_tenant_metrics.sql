-- ================================================
-- 分控汇总指标表(总控库)
-- 分控定时(每5-10min)上报自身运行汇总,总控按 merchant_id 存储做监控大盘。
-- 注意:分控在局域网、总控在公网,数据只能由分控主动出站上报(复用license校验通道)。
-- ================================================
USE bend_platform;

CREATE TABLE IF NOT EXISTS `tenant_metrics` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `license_key` VARCHAR(128) NOT NULL COMMENT '授权密钥(鉴权+标识)',
    `report_at` DATETIME NOT NULL COMMENT '分控上报时间(分控本地时间)',
    `received_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '总控接收时间',
    `online_agent_count` INT DEFAULT 0 COMMENT '在线Agent数',
    `total_agent_count` INT DEFAULT 0 COMMENT 'Agent总数',
    `today_task_count` INT DEFAULT 0 COMMENT '今日任务数',
    `running_task_count` INT DEFAULT 0 COMMENT '执行中任务数',
    `today_points_consumed` INT DEFAULT 0 COMMENT '今日已消费点数',
    `balance` INT DEFAULT 0 COMMENT '当前点数余额',
    `license_status` VARCHAR(32) DEFAULT NULL COMMENT '分控license状态: ONLINE/OFFLINE_GRACE/EXPIRED',
    `platform_version` VARCHAR(32) DEFAULT NULL COMMENT '分控版本号',
    `extra` TEXT DEFAULT NULL COMMENT '扩展指标(JSON)',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_merchant_report` (`merchant_id`, `report_at`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_report_at` (`report_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分控汇总指标表';
