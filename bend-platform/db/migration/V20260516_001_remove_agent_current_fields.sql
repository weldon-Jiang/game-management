-- =============================================
-- 数据库迁移：从agent_instance表移除current_streaming_id和current_task_id字段
-- 说明：任务状态应该通过task表和task_game_account_status表来查询，
--       不应该在agent_instance表中维护这些动态字段
-- =============================================

USE `bend_platform`;

-- 检查字段是否存在，如果存在则删除
SET @dbname = DATABASE();
SET @tablename = 'agent_instance';
SET @columnname1 = 'current_streaming_id';
SET @columnname2 = 'current_task_id';

SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE table_name = @tablename
        AND table_schema = @dbname
        AND column_name = @columnname1
    ) > 0,
    CONCAT('ALTER TABLE `', @tablename, '` DROP COLUMN `', @columnname1, '`;'),
    'SELECT ''Column ', @columnname1, ' does not exist'' AS message;'
));

PREPARE stmt FROM @preparedStatement;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @preparedStatement = (SELECT IF(
    (
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE table_name = @tablename
        AND table_schema = @dbname
        AND column_name = @columnname2
    ) > 0,
    CONCAT('ALTER TABLE `', @tablename, '` DROP COLUMN `', @columnname2, '`;'),
    'SELECT ''Column ', @columnname2, ' does not exist'' AS message;'
));

PREPARE stmt FROM @preparedStatement;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- 验证迁移结果
SELECT 
    'Migration completed successfully!' AS status,
    NOW() AS migration_time;
