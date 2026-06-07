-- Repair comments for environments that ran V005/V006 before utf8mb4 client charset was enforced

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

ALTER TABLE `game_account`
    MODIFY COLUMN `cooldown_hours` INT DEFAULT 23 COMMENT '自动化最小间隔小时',
    MODIFY COLUMN `total_coins` INT DEFAULT 0 COMMENT '累计金币',
    MODIFY COLUMN `today_coins` INT DEFAULT 0 COMMENT '今日金币',
    MODIFY COLUMN `dr_level` VARCHAR(64) DEFAULT NULL COMMENT 'DR等级',
    MODIFY COLUMN `today_last_completed_time` DATETIME DEFAULT NULL COMMENT '今日最后完成时间';

ALTER TABLE `automation_billing_event` COMMENT='自动化计费事件表';

ALTER TABLE `automation_billing_event`
    MODIFY COLUMN `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    MODIFY COLUMN `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    MODIFY COLUMN `task_id` VARCHAR(64) NOT NULL COMMENT '任务ID',
    MODIFY COLUMN `session_id` VARCHAR(64) DEFAULT NULL COMMENT '串流会话ID',
    MODIFY COLUMN `streaming_account_id` VARCHAR(64) DEFAULT NULL COMMENT '流媒体账号ID',
    MODIFY COLUMN `game_account_id` VARCHAR(64) NOT NULL COMMENT '游戏账号ID',
    MODIFY COLUMN `game_action_type` VARCHAR(50) NOT NULL COMMENT '任务类型',
    MODIFY COLUMN `billing_unit` VARCHAR(50) NOT NULL COMMENT '计费单元',
    MODIFY COLUMN `unit_index` INT NOT NULL COMMENT '计费单元序号',
    MODIFY COLUMN `idempotent_key` VARCHAR(255) NOT NULL COMMENT '幂等键',
    MODIFY COLUMN `points_deducted` INT DEFAULT 0 COMMENT '扣减点数',
    MODIFY COLUMN `coins_delta` INT DEFAULT 0 COMMENT '本事件金币变化',
    MODIFY COLUMN `status` VARCHAR(32) DEFAULT 'recorded' COMMENT '事件状态',
    MODIFY COLUMN `payload` JSON DEFAULT NULL COMMENT '原始上报',
    MODIFY COLUMN `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
