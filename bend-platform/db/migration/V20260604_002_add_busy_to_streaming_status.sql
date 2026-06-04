-- 修改 streaming_account 表的 status 字段，添加 'busy' 状态
-- 问题：原 status ENUM 不包含 'busy'，导致同步 status 和 task_status 时失败

-- 1. 修改 status 字段类型，添加 'busy'
ALTER TABLE streaming_account
MODIFY COLUMN `status` ENUM('idle', 'ready', 'running', 'paused', 'error', 'busy') DEFAULT 'idle' COMMENT '状态';

-- 2. 同时更新 schema.sql 中的定义
UPDATE schema_version SET version = 'V20260604_002', description = 'add busy to streaming_account status enum', applied_at = NOW() WHERE version = 'V20260604_001';
