-- ================================================
-- game_account 表结构修复脚本（直接执行版）
-- ================================================
-- 复制以下内容到 MySQL 客户端直接执行

-- 添加 merchant_id
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `merchant_id` VARCHAR(64) NOT NULL DEFAULT 'system-admin' COMMENT '商户ID' AFTER `streaming_id`;

-- 添加 agent_id
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `agent_id` VARCHAR(64) DEFAULT NULL COMMENT '当前绑定的Agent ID' AFTER `locked_xbox_id`;

-- 添加 is_primary
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `is_primary` TINYINT(1) DEFAULT 0 COMMENT '是否为主账号' AFTER `agent_id`;

-- 添加 is_active
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否激活' AFTER `is_primary`;

-- 添加 priority
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `priority` INT DEFAULT 0 COMMENT '使用优先级' AFTER `is_active`;

-- 添加 daily_match_limit
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `daily_match_limit` INT DEFAULT 0 COMMENT '每日比赛限制场次' AFTER `priority`;

-- 添加 today_match_count
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `today_match_count` INT DEFAULT 0 COMMENT '今日已完成场次' AFTER `daily_match_limit`;

-- 添加 total_match_count
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `total_match_count` INT DEFAULT 0 COMMENT '总比赛场次' AFTER `today_match_count`;

-- 添加 last_used_at
ALTER TABLE game_account ADD COLUMN IF NOT EXISTS `last_used_at` DATETIME DEFAULT NULL COMMENT '最后使用时间' AFTER `total_match_count`;

-- 验证结果
SHOW COLUMNS FROM game_account;
