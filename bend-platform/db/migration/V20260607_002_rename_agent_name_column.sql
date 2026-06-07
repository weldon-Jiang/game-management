-- 将误加的 name 列重命名为 agent_name（若已存在 name 列）
SET @has_name := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'agent_instance'
      AND COLUMN_NAME = 'name'
);
SET @has_agent_name := (
    SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'agent_instance'
      AND COLUMN_NAME = 'agent_name'
);
SET @sql := IF(
    @has_name > 0 AND @has_agent_name = 0,
    'ALTER TABLE `agent_instance` CHANGE COLUMN `name` `agent_name` VARCHAR(64) DEFAULT NULL COMMENT ''Agent显示名称''',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
