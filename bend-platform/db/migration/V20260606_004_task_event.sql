-- Task event timeline for monitoring and audit

CREATE TABLE IF NOT EXISTS `task_event` (
    `id` VARCHAR(64) NOT NULL COMMENT '事件ID',
    `task_id` VARCHAR(64) NOT NULL COMMENT '任务ID',
    `merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '商户ID',
    `scope` VARCHAR(32) DEFAULT 'task' COMMENT 'task/session/game_account/module',
    `phase` VARCHAR(64) DEFAULT NULL COMMENT '阶段',
    `status` VARCHAR(32) DEFAULT NULL COMMENT '状态',
    `message` VARCHAR(512) DEFAULT NULL COMMENT '消息',
    `game_account_id` VARCHAR(64) DEFAULT NULL COMMENT '游戏账号ID',
    `module` VARCHAR(64) DEFAULT NULL COMMENT '模块名',
    `payload` JSON DEFAULT NULL COMMENT '扩展数据',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_task_id` (`task_id`),
    KEY `idx_scope` (`scope`),
    KEY `idx_created_time` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务事件时间线';
