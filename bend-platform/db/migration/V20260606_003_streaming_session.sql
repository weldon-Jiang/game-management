-- Streaming session + task control fields (two-phase lifecycle)

CREATE TABLE IF NOT EXISTS `streaming_session` (
    `id` VARCHAR(64) NOT NULL COMMENT '会话ID',
    `task_id` VARCHAR(64) NOT NULL COMMENT '关联任务ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `streaming_account_id` VARCHAR(64) NOT NULL COMMENT '串流账号ID',
    `xbox_host_id` VARCHAR(36) DEFAULT NULL COMMENT '平台主机ID',
    `console_server_id` VARCHAR(64) DEFAULT NULL COMMENT 'GSSV serverId',
    `target_agent_id` VARCHAR(64) DEFAULT NULL COMMENT '执行Agent',
    `phase` VARCHAR(32) DEFAULT 'opening' COMMENT '会话阶段',
    `input_mode` VARCHAR(16) DEFAULT 'virtual' COMMENT 'physical/virtual',
    `decode_mode` VARCHAR(16) DEFAULT 'auto' COMMENT 'gpu/cpu/auto',
    `power_state` VARCHAR(32) DEFAULT NULL COMMENT '电源状态',
    `game_action_type` VARCHAR(50) DEFAULT NULL COMMENT '就绪后选择的自动化类型',
    `game_action_locked_at` DATETIME DEFAULT NULL COMMENT '开始自动化时间',
    `error_code` VARCHAR(64) DEFAULT NULL,
    `error_message` VARCHAR(512) DEFAULT NULL,
    `started_time` DATETIME DEFAULT NULL,
    `ready_time` DATETIME DEFAULT NULL,
    `closed_time` DATETIME DEFAULT NULL,
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP,
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (`id`),
    KEY `idx_streaming_account` (`streaming_account_id`),
    KEY `idx_task_id` (`task_id`),
    KEY `idx_phase` (`phase`),
    KEY `idx_agent` (`target_agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='串流会话表';

ALTER TABLE `task`
    ADD COLUMN `session_id` VARCHAR(64) DEFAULT NULL COMMENT '串流会话ID' AFTER `streaming_account_id`,
    ADD COLUMN `session_phase` VARCHAR(32) DEFAULT NULL COMMENT '会话阶段快照' AFTER `session_id`,
    ADD COLUMN `game_action_pending` TINYINT(1) DEFAULT 0 COMMENT '等待选手动化类型' AFTER `session_phase`,
    ADD COLUMN `pause_mode` VARCHAR(32) DEFAULT NULL COMMENT '暂停模式 immediate/after_match' AFTER `game_action_pending`,
    ADD COLUMN `window_visible` TINYINT(1) DEFAULT 1 COMMENT '窗口可见快照' AFTER `pause_mode`;

ALTER TABLE `task_game_account_status`
    ADD COLUMN `session_id` VARCHAR(64) DEFAULT NULL COMMENT '串流会话ID' AFTER `streaming_account_id`,
    ADD COLUMN `phase` VARCHAR(32) DEFAULT 'pending' COMMENT '执行阶段' AFTER `status`,
    ADD COLUMN `game_action_type` VARCHAR(50) DEFAULT NULL AFTER `phase`,
    ADD COLUMN `match_index` INT DEFAULT 0 AFTER `game_action_type`,
    ADD COLUMN `match_total` INT DEFAULT 0 AFTER `match_index`,
    ADD COLUMN `provisioning_phase` VARCHAR(32) DEFAULT NULL AFTER `match_total`,
    ADD COLUMN `provisioning_step` INT DEFAULT NULL AFTER `provisioning_phase`,
    ADD COLUMN `provisioning_step_total` INT DEFAULT NULL AFTER `provisioning_step`,
    ADD COLUMN `provisioning_message` VARCHAR(512) DEFAULT NULL AFTER `provisioning_step_total`,
    ADD COLUMN `active_module` VARCHAR(64) DEFAULT NULL AFTER `provisioning_message`;
