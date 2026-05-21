USE bend_platform;

-- 添加 current_step 字段
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                   WHERE TABLE_SCHEMA = 'bend_platform' 
                   AND TABLE_NAME = 'task' 
                   AND COLUMN_NAME = 'current_step');
SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE task ADD COLUMN current_step VARCHAR(50) DEFAULT NULL COMMENT ''当前执行步骤''', 
              'SELECT ''current_step already exists'' AS result');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加 step_status 字段
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                   WHERE TABLE_SCHEMA = 'bend_platform' 
                   AND TABLE_NAME = 'task' 
                   AND COLUMN_NAME = 'step_status');
SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE task ADD COLUMN step_status VARCHAR(20) DEFAULT NULL COMMENT ''步骤状态''', 
              'SELECT ''step_status already exists'' AS result');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 添加 progress_message 字段
SET @col_exists = (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS 
                   WHERE TABLE_SCHEMA = 'bend_platform' 
                   AND TABLE_NAME = 'task' 
                   AND COLUMN_NAME = 'progress_message');
SET @sql = IF(@col_exists = 0, 
              'ALTER TABLE task ADD COLUMN progress_message VARCHAR(512) DEFAULT NULL COMMENT ''进度消息''', 
              'SELECT ''progress_message already exists'' AS result');
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SELECT 'Columns added successfully' AS result;