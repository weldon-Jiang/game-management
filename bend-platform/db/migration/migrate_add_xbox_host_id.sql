-- 添加Xbox主机ID字段到task表
-- 用于记录Agent执行任务时使用的Xbox主机

USE bend_platform;

-- 添加xbox_host_id字段
ALTER TABLE task
ADD COLUMN xbox_host_id VARCHAR(36) DEFAULT NULL COMMENT '使用的Xbox主机ID' AFTER game_account_id;

-- 添加索引以提高查询性能
CREATE INDEX idx_xbox_host_id ON task(xbox_host_id);

-- 添加备注说明
SELECT 'Migration completed: Added xbox_host_id column to task table' AS status;
