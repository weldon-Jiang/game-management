SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

ALTER TABLE `xbox_host`
    ADD COLUMN `locked_by_task_id` VARCHAR(36) DEFAULT NULL COMMENT '锁定任务ID' AFTER `locked_by_agent_id`;
