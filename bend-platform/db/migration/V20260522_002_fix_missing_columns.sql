USE bend_platform;

-- 添加 game_action_type 字段到 task 表
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                   WHERE TABLE_SCHEMA = 'bend_platform' 
                   AND TABLE_NAME = 'task' 
                   AND COLUMN_NAME = 'game_action_type');
SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE task ADD COLUMN game_action_type VARCHAR(50) DEFAULT ''daily_match'' COMMENT ''游戏操作类型''', 
              'SELECT ''game_action_type already exists'' AS result');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加 os_type 字段到 agent_instance 表
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                   WHERE TABLE_SCHEMA = 'bend_platform' 
                   AND TABLE_NAME = 'agent_instance' 
                   AND COLUMN_NAME = 'os_type');
SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE agent_instance ADD COLUMN os_type VARCHAR(50) DEFAULT NULL COMMENT ''操作系统类型''', 
              'SELECT ''os_type already exists'' AS result');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 显示结果
SELECT 'Migration completed' AS result;