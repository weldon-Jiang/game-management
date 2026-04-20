-- streaming_account 表结构修复
-- 添加缺失的 agent_id 列

-- 添加列（如果已存在会报错，可忽略）
ALTER TABLE streaming_account
ADD COLUMN agent_id VARCHAR(64) DEFAULT NULL COMMENT '当前绑定的Agent ID'
AFTER `status`;

-- 添加索引（如果已存在会报错，可忽略）
ALTER TABLE streaming_account
ADD INDEX idx_agent_id (`agent_id`);
