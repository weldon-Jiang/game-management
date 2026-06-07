-- Idempotent Step4 billing events reported by Agent

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

CREATE TABLE IF NOT EXISTS `automation_billing_event` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `task_id` VARCHAR(64) NOT NULL COMMENT '任务ID',
    `session_id` VARCHAR(64) DEFAULT NULL COMMENT '串流会话ID',
    `streaming_account_id` VARCHAR(64) DEFAULT NULL COMMENT '流媒体账号ID',
    `game_account_id` VARCHAR(64) NOT NULL COMMENT '游戏账号ID',
    `game_action_type` VARCHAR(50) NOT NULL COMMENT '任务类型',
    `billing_unit` VARCHAR(50) NOT NULL COMMENT '计费单元',
    `unit_index` INT NOT NULL COMMENT '计费单元序号',
    `idempotent_key` VARCHAR(255) NOT NULL COMMENT '幂等键',
    `points_deducted` INT DEFAULT 0 COMMENT '扣减点数',
    `coins_delta` INT DEFAULT 0 COMMENT '本事件金币变化',
    `status` VARCHAR(32) DEFAULT 'recorded' COMMENT '事件状态',
    `payload` JSON DEFAULT NULL COMMENT '原始上报',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_billing_event_unit` (`task_id`, `session_id`, `game_account_id`, `game_action_type`, `billing_unit`, `unit_index`),
    UNIQUE KEY `uk_billing_event_idempotent` (`idempotent_key`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_task_id` (`task_id`),
    KEY `idx_game_account_id` (`game_account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自动化计费事件表';
