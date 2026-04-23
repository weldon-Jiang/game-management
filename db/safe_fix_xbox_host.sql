-- ================================================
-- xbox_host 安全修复脚本
-- ================================================
-- 检查每个列是否存在，只添加缺失的列

USE bend_platform;

-- 添加 merchant_id
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'merchant_id');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN merchant_id VARCHAR(64) NOT NULL DEFAULT ''system-admin'' COMMENT ''商户ID'' AFTER id', 'SELECT ''merchant_id 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 xbox_id
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'xbox_id');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN xbox_id VARCHAR(128) NOT NULL COMMENT ''Xbox主机ID'' AFTER merchant_id', 'SELECT ''xbox_id 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 bound_streaming_account_id
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'bound_streaming_account_id');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN bound_streaming_account_id VARCHAR(64) DEFAULT NULL COMMENT ''绑定的流媒体账号ID''', 'SELECT ''bound_streaming_account_id 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 bound_gamertag
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'bound_gamertag');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN bound_gamertag VARCHAR(64) DEFAULT NULL COMMENT ''绑定的Gamertag''', 'SELECT ''bound_gamertag 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 power_state
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'power_state');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN power_state VARCHAR(16) DEFAULT NULL COMMENT ''电源状态: on/off''', 'SELECT ''power_state 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 locked_by_agent_id
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'locked_by_agent_id');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN locked_by_agent_id VARCHAR(64) DEFAULT NULL COMMENT ''锁定Agent ID''', 'SELECT ''locked_by_agent_id 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 locked_at
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'locked_at');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN locked_at DATETIME DEFAULT NULL COMMENT ''锁定时间''', 'SELECT ''locked_at 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 lock_expires_at
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'lock_expires_at');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN lock_expires_at DATETIME DEFAULT NULL COMMENT ''锁定过期时间''', 'SELECT ''lock_expires_at 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- 添加 last_seen_at
SET @exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'xbox_host' AND COLUMN_NAME = 'last_seen_at');
SET @sql = IF(@exists = 0, 'ALTER TABLE xbox_host ADD COLUMN last_seen_at DATETIME DEFAULT NULL COMMENT ''最后发现时间''', 'SELECT ''last_seen_at 已存在'' as result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

SELECT 'xbox_host 修复完成!' AS result;
