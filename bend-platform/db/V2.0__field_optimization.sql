-- =====================================================
-- 数据库字段优化迁移脚本 v2.0
-- 日期: 2026-05-31
-- 说明: 优化XboxHost表、Task表、TaskGameAccountStatus表字段
-- =====================================================

USE bend_platform;

-- =====================================================
-- 1. XboxHost表优化：添加 locked 布尔字段
-- =====================================================

-- 添加 locked 字段（用于前端快速判断锁定状态）
ALTER TABLE xbox_host
ADD COLUMN `locked` TINYINT(1) DEFAULT 0 COMMENT '是否被锁定' AFTER `lock_expires_time`;

-- 为现有数据设置正确的 locked 值（根据 locked_by_agent_id 和 lock_expires_time）
UPDATE xbox_host
SET locked = 1
WHERE locked_by_agent_id IS NOT NULL
  AND lock_expires_time IS NOT NULL
  AND lock_expires_time > NOW();

-- 添加索引优化锁定状态查询
CREATE INDEX idx_locked ON xbox_host(`locked`);
CREATE INDEX idx_locked_by_agent_id ON xbox_host(`locked_by_agent_id`);

-- =====================================================
-- 2. XboxHost表：添加 port, live_id 字段（如果不存在）
-- =====================================================

-- 注意：这些字段在 schema.sql 中已经定义，此处跳过
-- 如果schema未包含，运行以下语句：
-- ALTER TABLE xbox_host ADD COLUMN `port` INT DEFAULT 5050 COMMENT 'SmartGlass端口' AFTER `ip_address`;
-- ALTER TABLE xbox_host ADD COLUMN `live_id` VARCHAR(128) DEFAULT NULL COMMENT 'Xbox Live ID' AFTER `port`;

-- =====================================================
-- 3. Task表：添加 status CHECK约束
-- =====================================================

-- MySQL 8.0+ 支持 CHECK 约束
-- 注意：如果MySQL版本低于8.0，此约束会被忽略但不会报错
ALTER TABLE task
ADD CONSTRAINT chk_task_status
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout', 'paused'));

-- =====================================================
-- 4. TaskGameAccountStatus表：添加 status CHECK约束
-- =====================================================

ALTER TABLE task_game_account_status
ADD CONSTRAINT chk_task_game_account_status
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'skipped', 'game_preparing', 'gaming'));

-- =====================================================
-- 5. StreamingAccount表：添加 status CHECK约束
-- =====================================================

ALTER TABLE streaming_account
ADD CONSTRAINT chk_streaming_account_status
CHECK (status IN ('idle', 'ready', 'running', 'paused', 'error'));

-- =====================================================
-- 6. 更新 xbox_host 表的 status 字段 CHECK约束（如果需要）
-- =====================================================

-- 注意：xbox_host 表的 status 字段已经是 ENUM 类型，跳过

-- =====================================================
-- 验证迁移结果
-- =====================================================

-- 查看 xbox_host 表结构
DESCRIBE xbox_host;

-- 查看 task 表的 CHECK 约束（MySQL 8.0+）
SELECT CONSTRAINT_NAME, TABLE_NAME, CHECK_CLAUSE
FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS
WHERE TABLE_SCHEMA = 'bend_platform';

-- 统计 locked 字段的值分布
SELECT locked, COUNT(*) as count
FROM xbox_host
GROUP BY locked;

-- =====================================================
-- 回滚脚本（如需回滚）
-- =====================================================

-- ALTER TABLE xbox_host DROP COLUMN `locked`;
-- ALTER TABLE task DROP CONSTRAINT chk_task_status;
-- ALTER TABLE task_game_account_status DROP CONSTRAINT chk_task_game_account_status;
-- ALTER TABLE streaming_account DROP CONSTRAINT chk_streaming_account_status;
