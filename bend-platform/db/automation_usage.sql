-- 自动化任务使用记录表
-- 记录启动自动化任务时的使用情况和扣点信息

USE bend_platform;

CREATE TABLE IF NOT EXISTS `automation_usage` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `user_id` VARCHAR(64) NOT NULL COMMENT '用户ID',
    `task_id` VARCHAR(64) NOT NULL COMMENT '任务ID',
    `streaming_account_id` VARCHAR(64) NOT NULL COMMENT '流媒体账号ID',
    `streaming_account_name` VARCHAR(128) DEFAULT NULL COMMENT '流媒体账号名称',
    `game_accounts_count` INT DEFAULT 0 COMMENT '游戏账号数量',
    `hosts_count` INT DEFAULT 0 COMMENT '主机数量',
    `resource_type` VARCHAR(32) DEFAULT NULL COMMENT '使用的资源类型：window/account/host',
    `resource_id` VARCHAR(64) DEFAULT NULL COMMENT '资源ID',
    `resource_name` VARCHAR(128) DEFAULT NULL COMMENT '资源名称',
    `charge_mode` VARCHAR(32) DEFAULT 'per_use' COMMENT '扣点模式：per_use-按次, monthly-包月',
    `points_deducted` INT DEFAULT 0 COMMENT '扣减的点数',
    `subscription_id` VARCHAR(64) DEFAULT NULL COMMENT '关联的订阅ID（如果是包月模式）',
    `usage_time` DATETIME DEFAULT NULL COMMENT '使用时间',
    `remark` VARCHAR(512) DEFAULT NULL COMMENT '备注',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_task_id` (`task_id`),
    KEY `idx_streaming_account_id` (`streaming_account_id`),
    KEY `idx_usage_time` (`usage_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自动化任务使用记录表';
