-- ================================================
-- 数据库表结构修复脚本
-- ================================================
-- 用于修复 tables.sql(实际数据库) 与 schema.sql(目标结构) 不一致的问题
-- 执行方式: mysql -u root -p bend_platform < fix_all_tables.sql
-- ================================================

USE bend_platform;

-- ================================================
-- 1. 修复 activation_code_batch 表
-- ================================================
-- 问题：实际数据库缺少 vip_config_id 列

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'activation_code_batch' AND COLUMN_NAME = 'vip_config_id');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE activation_code_batch ADD COLUMN `vip_config_id` VARCHAR(64) DEFAULT NULL COMMENT ''VIP配置ID'' AFTER `vip_type`',
    'SELECT ''vip_config_id 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ================================================
-- 2. 修复 streaming_account_login_record 表
-- ================================================
-- 问题：实际数据库缺少 created_time 列

SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'streaming_account_login_record' AND COLUMN_NAME = 'created_time');
SET @sql = IF(@col_exists = 0,
    'ALTER TABLE streaming_account_login_record ADD COLUMN `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT ''创建时间''',
    'SELECT ''created_time 已存在'' AS result');
PREPARE stmt FROM @sql; EXECUTE stmt; DEALLOCATE PREPARE stmt;

-- ================================================
-- 3. 修复 activation_code 表
-- ================================================
-- 问题：schema.sql 移除了 vip_type 和 vip_config_id，但实际数据库有这些列
-- 注意：这些列可以保留，不影响功能（代码已不再使用）

-- ================================================
-- 4. 验证修复
-- ================================================
SELECT 'activation_code_batch 表结构:' AS '';
DESCRIBE activation_code_batch;

SELECT 'streaming_account_login_record 表结构:' AS '';
DESCRIBE streaming_account_login_record;

SELECT '修复完成!' AS result;
