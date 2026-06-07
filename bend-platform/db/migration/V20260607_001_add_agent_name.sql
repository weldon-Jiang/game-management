-- Agent 显示名称：同一商户下不可重复（原表无预设名称字段，新增 agent_name）
ALTER TABLE `agent_instance`
    ADD COLUMN `agent_name` VARCHAR(64) DEFAULT NULL COMMENT 'Agent显示名称' AFTER `agent_id`;

CREATE UNIQUE INDEX `uk_merchant_agent_name` ON `agent_instance` (`merchant_id`, `agent_name`);
