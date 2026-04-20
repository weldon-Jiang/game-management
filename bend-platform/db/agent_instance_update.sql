-- Agent实例表更新脚本
-- 添加新字段以支持完整的Agent生命周期管理

-- 添加 agent_secret 字段
ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS agent_secret VARCHAR(255) COMMENT 'Agent密钥';

-- 添加 merchant_id 字段
ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS merchant_id VARCHAR(64) COMMENT '所属商户ID';

-- 添加 registration_code 字段
ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS registration_code VARCHAR(64) COMMENT '注册码';

-- 添加 version 字段
ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS version VARCHAR(32) COMMENT 'Agent版本';

-- 添加 last_online_time 字段
ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS last_online_time DATETIME COMMENT '最后上线时间';

-- 添加 uninstall_reason 字段
ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS uninstall_reason VARCHAR(255) COMMENT '卸载原因';

-- 添加 deleted 字段（逻辑删除）
ALTER TABLE agent_instance ADD COLUMN IF NOT EXISTS deleted TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记';

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_agent_instance_merchant_id ON agent_instance(merchant_id);
CREATE INDEX IF NOT EXISTS idx_agent_instance_status ON agent_instance(status);
CREATE INDEX IF NOT EXISTS idx_agent_instance_deleted ON agent_instance(deleted);
