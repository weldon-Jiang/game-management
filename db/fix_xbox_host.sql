-- ================================================
-- xbox_host 表结构修复脚本
-- ================================================
-- 修复问题：表结构与 XboxHost 实体不匹配
-- 执行前请备份数据！

USE bend_platform;

-- ================================================
-- 1. 添加缺失的列
-- ================================================

-- 添加 merchant_id (如果不存在)
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `merchant_id` VARCHAR(64) NOT NULL DEFAULT 'system-admin' COMMENT '商户ID' AFTER `id`;

-- 添加 xbox_id (如果不存在) - Xbox主机ID
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `xbox_id` VARCHAR(128) NOT NULL COMMENT 'Xbox主机ID' AFTER `merchant_id`;

-- 添加 bound_streaming_account_id (如果不存在)
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `bound_streaming_account_id` VARCHAR(64) DEFAULT NULL COMMENT '绑定的流媒体账号ID' AFTER `status`;

-- 添加 bound_gamertag (如果不存在)
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `bound_gamertag` VARCHAR(64) DEFAULT NULL COMMENT '绑定的Gamertag' AFTER `bound_streaming_account_id`;

-- 添加 power_state (如果不存在)
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `power_state` VARCHAR(16) DEFAULT NULL COMMENT '电源状态: on/off' AFTER `bound_gamertag`;

-- 添加 locked_by_agent_id (如果不存在)
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `locked_by_agent_id` VARCHAR(64) DEFAULT NULL COMMENT '锁定Agent ID' AFTER `power_state`;

-- 添加 locked_at (如果不存在)
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `locked_at` DATETIME DEFAULT NULL COMMENT '锁定时间' AFTER `locked_by_agent_id`;

-- 添加 lock_expires_at (如果不存在)
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `lock_expires_at` DATETIME DEFAULT NULL COMMENT '锁定过期时间' AFTER `locked_at`;

-- 添加 last_seen_at (如果不存在)
ALTER TABLE xbox_host ADD COLUMN IF NOT EXISTS `last_seen_at` DATETIME DEFAULT NULL COMMENT '最后发现时间' AFTER `lock_expires_at`;

-- ================================================
-- 2. 移除多余的列
-- ================================================

-- 注意：这些列可能包含数据，移除前请确认
ALTER TABLE xbox_host DROP COLUMN IF EXISTS `current_game`;
ALTER TABLE xbox_host DROP COLUMN IF EXISTS `current_account`;
ALTER TABLE xbox_host DROP COLUMN IF EXISTS `model`;
ALTER TABLE xbox_host DROP COLUMN IF EXISTS `mac_address`;

-- ================================================
-- 3. 重命名 agent_id 为 locked_by_agent_id (如果需要保留锁定语义)
-- ================================================
-- 由于 agent_id 可能已有数据，先尝试添加新列再删除旧列
-- 如果 agent_id 列存在，将其值迁移到 locked_by_agent_id
-- UPDATE xbox_host SET locked_by_agent_id = agent_id WHERE agent_id IS NOT NULL;
-- ALTER TABLE xbox_host DROP COLUMN IF EXISTS `agent_id`;

-- ================================================
-- 4. 更新索引
-- ================================================
-- 添加缺失的索引
ALTER TABLE xbox_host ADD INDEX IF NOT EXISTS `idx_merchant_id` (`merchant_id`);
ALTER TABLE xbox_host ADD INDEX IF NOT EXISTS `idx_bound_streaming_account_id` (`bound_streaming_account_id`);
ALTER TABLE xbox_host ADD INDEX IF NOT EXISTS `idx_locked_by_agent_id` (`locked_by_agent_id`);

-- ================================================
-- 5. 验证修复结果
-- ================================================
SHOW COLUMNS FROM xbox_host;
