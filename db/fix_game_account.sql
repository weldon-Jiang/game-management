-- ================================================
-- 游戏账号表结构修复脚本
-- ================================================
-- 检查并添加所有缺失的列

USE bend_platform;

-- ================================================
-- Section 1: 检查 game_account 表当前结构
-- ================================================
DESCRIBE game_account;

-- ================================================
-- Section 2: 添加所有缺失的列
-- ================================================

-- 添加 merchant_id (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'merchant_id');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `merchant_id` VARCHAR(64) NOT NULL DEFAULT ''system-admin'' COMMENT ''商户ID'' AFTER `streaming_id`',
    'SELECT ''merchant_id 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 agent_id (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'agent_id');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `agent_id` VARCHAR(64) DEFAULT NULL COMMENT ''当前绑定的Agent ID'' AFTER `locked_xbox_id`',
    'SELECT ''agent_id 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 is_primary (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'is_primary');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `is_primary` TINYINT(1) DEFAULT 0 COMMENT ''是否为主账号'' AFTER `agent_id`',
    'SELECT ''is_primary 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 is_active (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'is_active');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `is_active` TINYINT(1) DEFAULT 1 COMMENT ''是否激活'' AFTER `is_primary`',
    'SELECT ''is_active 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 priority (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'priority');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `priority` INT DEFAULT 0 COMMENT ''使用优先级'' AFTER `is_active`',
    'SELECT ''priority 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 daily_match_limit (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'daily_match_limit');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `daily_match_limit` INT DEFAULT 0 COMMENT ''每日比赛限制场次'' AFTER `priority`',
    'SELECT ''daily_match_limit 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 today_match_count (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'today_match_count');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `today_match_count` INT DEFAULT 0 COMMENT ''今日已完成场次'' AFTER `daily_match_limit`',
    'SELECT ''today_match_count 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 total_match_count (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'total_match_count');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `total_match_count` INT DEFAULT 0 COMMENT ''总比赛场次'' AFTER `today_match_count`',
    'SELECT ''total_match_count 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 last_used_at (如果不存在)
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'game_account' AND COLUMN_NAME = 'last_used_at');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `last_used_at` DATETIME DEFAULT NULL COMMENT ''最后使用时间'' AFTER `total_match_count`',
    'SELECT ''last_used_at 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ================================================
-- Section 3: 验证修复后的表结构
-- ================================================
DESCRIBE game_account;

-- ================================================
-- Section 4: 测试查询
-- ================================================
SELECT id, streaming_id, merchant_id, name, xbox_gamertag, is_active, agent_id
FROM game_account
LIMIT 10;
