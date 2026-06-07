-- Extend game account source data for task limits and billing metrics

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

ALTER TABLE `game_account`
    ADD COLUMN `cooldown_hours` INT DEFAULT 23 COMMENT '自动化最小间隔小时' AFTER `today_match_count`,
    ADD COLUMN `total_coins` INT DEFAULT 0 COMMENT '累计金币' AFTER `total_match_count`,
    ADD COLUMN `today_coins` INT DEFAULT 0 COMMENT '今日金币' AFTER `total_coins`,
    ADD COLUMN `dr_level` VARCHAR(64) DEFAULT NULL COMMENT 'DR等级' AFTER `today_coins`,
    ADD COLUMN `today_last_completed_time` DATETIME DEFAULT NULL COMMENT '今日最后完成时间' AFTER `dr_level`;
