-- ================================================
-- 修复 activation_code 表中多余的 vip_type 字段
-- 执行时间：2026-05-06
-- ================================================
-- 问题：activation_code 和 activation_code_batch 表中存在 vip_type 字段
-- 但代码中已经不再使用，需要从数据库中删除
-- ================================================
-- 注意：MySQL 不支持 DROP COLUMN IF EXISTS
-- 如果字段不存在会报错，可忽略错误继续执行
-- ================================================

USE bend_platform;

-- 删除 activation_code 表的 vip_type 字段（如果存在）
-- 这是一个可选操作，如果字段不存在会报错，可以忽略
-- ALTER TABLE activation_code DROP COLUMN vip_type;

-- 删除 activation_code_batch 表的 vip_type 字段（如果存在）
-- 这是一个可选操作，如果字段不存在会报错，可以忽略
-- ALTER TABLE activation_code_batch DROP COLUMN vip_type;

-- ================================================
-- 验证表结构（取消注释以查看当前结构）
-- ================================================
-- SELECT 'activation_code 表结构:' AS '';
-- DESCRIBE activation_code;

-- SELECT 'activation_code_batch 表结构:' AS '';
-- DESCRIBE activation_code_batch;

-- ================================================
-- 如果上面的 ALTER TABLE 语句报错，可以使用以下存储过程
-- ================================================
DELIMITER //

DROP PROCEDURE IF EXISTS safe_drop_column//

CREATE PROCEDURE safe_drop_column(
    IN table_name VARCHAR(64),
    IN column_name VARCHAR(64)
)
BEGIN
    DECLARE column_exists INT DEFAULT 0;

    SELECT COUNT(*) INTO column_exists
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = table_name
      AND COLUMN_NAME = column_name;

    IF column_exists > 0 THEN
        SET @sql = CONCAT('ALTER TABLE ', table_name, ' DROP COLUMN ', column_name);
        PREPARE stmt FROM @sql;
        EXECUTE stmt;
        DEALLOCATE PREPARE stmt;
        SELECT CONCAT('已删除 ', table_name, '.', column_name) AS result;
    ELSE
        SELECT CONCAT(table_name, '.', column_name, ' 不存在，跳过') AS result;
    END IF;
END//

DELIMITER ;

-- 调用存储过程删除字段
CALL safe_drop_column('activation_code', 'vip_type');
CALL safe_drop_column('activation_code_batch', 'vip_type');

-- 清理存储过程
DROP PROCEDURE IF EXISTS safe_drop_column;