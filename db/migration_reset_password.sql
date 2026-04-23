-- ================================================
-- 数据库修复迁移脚本
-- ================================================
-- 执行顺序：
-- 1. 先执行 Section 1: 修复 game_account 表结构
-- 2. 再执行 Section 2: 重置用户密码
-- ================================================

-- ================================================
-- Section 1: 修复 game_account 表结构
-- ================================================
-- 问题：game_account 表缺少 merchant_id 列
-- 原因：migration.sql 中 game_account 表定义没有 merchant_id
-- 修复：添加 merchant_id 列

-- 检查 merchant_id 列是否存在，不存在则添加
SET @column_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
    AND TABLE_NAME = 'game_account'
    AND COLUMN_NAME = 'merchant_id'
);

-- 添加 merchant_id 列（如果不存在）
SET @sql = IF(@column_exists = 0,
    'ALTER TABLE game_account ADD COLUMN `merchant_id` VARCHAR(64) NOT NULL DEFAULT ''system-admin'' COMMENT ''商户ID'' AFTER `streaming_id`',
    'SELECT ''merchant_id 列已存在，跳过添加'' AS result'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 验证表结构
DESCRIBE game_account;

-- ================================================
-- Section 2: 重置用户密码
-- ================================================
-- 使用说明：
-- 1. 确保后端 application.yml 中 AES_SECRET=0sedzo/xcWVHjwKvJAk4lg==
-- 2. 执行此脚本将所有用户密码重置为 admin123
-- 3. 用户登录后请立即修改密码

-- 使用 AES_SECRET=0sedzo/xcWVHjwKvJAk4lg== 加密 "admin123" 后的密文
-- 密文 (hex): bc9c6ebfa285976aa94186fe90103bc7

-- 重置所有商户用户的密码为 admin123
-- UPDATE merchant_user
-- SET password_hash = 'bc9c6ebfa285976aa94186fe90103bc7'
-- WHERE status = 'active';

-- -- 验证结果
-- SELECT id, username, phone, role, status,
--        CASE
--            WHEN password_hash = 'bc9c6ebfa285976aa94186fe90103bc7' THEN '已重置'
--            ELSE '未重置'
--        END AS password_status
-- FROM merchant_user;

-- ================================================
-- Section 3: 验证 game_account 数据
-- ================================================
-- 检查 game_account 表数据
SELECT id, streaming_id, merchant_id, name, xbox_gamertag, is_active
FROM game_account
LIMIT 10;
