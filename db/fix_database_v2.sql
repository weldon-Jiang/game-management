-- ================================================
-- 数据库修复脚本 v2.0 (兼容版)
-- ================================================
-- 注意：MySQL 不支持 DROP COLUMN IF EXISTS
-- 执行时请确认列是否存在
-- ================================================

USE bend_platform;

-- ================================================
-- 1. xbox_host 修复 - 移除多余列
-- ================================================
-- 如果列存在则删除（如果不存在会报错，可忽略）

-- 移除 current_game
-- ALTER TABLE xbox_host DROP COLUMN current_game;

-- 移除 current_account
-- ALTER TABLE xbox_host DROP COLUMN current_account;

-- 移除 model
-- ALTER TABLE xbox_host DROP COLUMN model;

-- 移除 mac_address
-- ALTER TABLE xbox_host DROP COLUMN mac_address;

-- 移除 agent_id (改名后不再需要)
-- ALTER TABLE xbox_host DROP COLUMN agent_id;

-- ================================================
-- 2. activation_code 修复 - 移除冗余列
-- ================================================
-- 如果列存在则删除

-- 移除 vip_type
-- ALTER TABLE activation_code DROP COLUMN vip_type;

-- 移除 vip_config_id
-- ALTER TABLE activation_code DROP COLUMN vip_config_id;

-- ================================================
-- 验证表结构
-- ================================================
-- SELECT 'xbox_host 表结构:' AS '';
-- DESCRIBE xbox_host;

-- SELECT 'activation_code 表结构:' AS '';
-- DESCRIBE activation_code;
