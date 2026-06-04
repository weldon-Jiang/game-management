-- Rename game_account fields to remove xbox prefix
-- Date: 2026-06-04
-- Description: Rename xbox_game_name to game_name, xbox_live_email to email, xbox_live_password_encrypted to password_encrypted

-- Drop old unique keys
ALTER TABLE `game_account` DROP INDEX `uk_xbox_game_name`;
ALTER TABLE `game_account` DROP INDEX `uk_xbox_live_email`;

-- Rename columns
ALTER TABLE `game_account` CHANGE COLUMN `xbox_game_name` `game_name` VARCHAR(64) DEFAULT NULL COMMENT '游戏昵称';
ALTER TABLE `game_account` CHANGE COLUMN `xbox_live_email` `email` VARCHAR(255) DEFAULT NULL COMMENT '登录邮箱';
ALTER TABLE `game_account` CHANGE COLUMN `xbox_live_password_encrypted` `password_encrypted` VARCHAR(512) DEFAULT NULL COMMENT '加密后的密码';

-- Add new unique keys
ALTER TABLE `game_account` ADD UNIQUE KEY `uk_game_name` (`game_name`);
ALTER TABLE `game_account` ADD UNIQUE KEY `uk_email` (`email`);
