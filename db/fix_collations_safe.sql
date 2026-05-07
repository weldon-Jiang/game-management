-- Bend Platform 数据库排序规则统一脚本（安全版）
-- 执行前请先备份数据库
-- 执行方式: mysql -h localhost -P 3306 -u weldon -p bend_platform < db/fix_collations_safe.sql

USE bend_platform;

-- 1. 先查看当前所有表的排序规则
SELECT 
    TABLE_NAME,
    TABLE_COLLATION
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'bend_platform'
ORDER BY TABLE_NAME;

-- 2. 生成动态 SQL 来统一所有现有表的排序规则
SET FOREIGN_KEY_CHECKS = 0;

-- 安全地更新表排序规则的存储过程
DELIMITER $$

DROP PROCEDURE IF EXISTS fix_table_collation$$

CREATE PROCEDURE fix_table_collation(IN table_name VARCHAR(100))
BEGIN
    DECLARE sql_stmt VARCHAR(1000);
    DECLARE CONTINUE HANDLER FOR SQLEXCEPTION 
        SELECT CONCAT('Warning: Could not update ', table_name) AS warning;
    
    SET sql_stmt = CONCAT('ALTER TABLE `', table_name, '` CONVERT TO CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci');
    SET @sql = sql_stmt;
    PREPARE stmt FROM @sql;
    EXECUTE stmt;
    DEALLOCATE PREPARE stmt;
    SELECT CONCAT('Updated: ', table_name) AS status;
END$$

DELIMITER ;

-- 为所有现有表调用存储过程
CALL fix_table_collation('agent_instance');
CALL fix_table_collation('agent_version');
CALL fix_table_collation('activation_code');
CALL fix_table_collation('activation_code_batch');
CALL fix_table_collation('device_binding');
CALL fix_table_collation('game_account');
CALL fix_table_collation('merchant');
CALL fix_table_collation('merchant_balance');
CALL fix_table_collation('merchant_group');
CALL fix_table_collation('merchant_registration_code');
CALL fix_table_collation('merchant_user');
CALL fix_table_collation('operation_log');
CALL fix_table_collation('point_transaction');
CALL fix_table_collation('recharge_card');
CALL fix_table_collation('recharge_card_batch');
CALL fix_table_collation('recharge_record');
CALL fix_table_collation('streaming_account');
CALL fix_table_collation('streaming_account_login_record');
CALL fix_table_collation('subscription');
CALL fix_table_collation('subscription_price');
CALL fix_table_collation('system_alert');
CALL fix_table_collation('system_metrics');
CALL fix_table_collation('task');
CALL fix_table_collation('template');
CALL fix_table_collation('xbox_host');

-- 清理存储过程
DROP PROCEDURE IF EXISTS fix_table_collation;

SET FOREIGN_KEY_CHECKS = 1;

-- 3. 再次确认所有表的排序规则
SELECT 
    TABLE_NAME,
    TABLE_COLLATION
FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'bend_platform'
ORDER BY TABLE_NAME;

-- 4. 数据修复：同步 merchant.total_points 和 merchant_balance.total_recharged
SELECT m.id, m.name, m.total_points, mb.total_recharged 
FROM merchant m 
LEFT JOIN merchant_balance mb ON m.id = mb.merchant_id 
WHERE m.name = '新商户2';

UPDATE merchant m 
INNER JOIN merchant_balance mb ON m.id = mb.merchant_id 
SET m.total_points = mb.total_recharged 
WHERE m.name = '新商户2';

SELECT m.id, m.name, m.total_points, mb.total_recharged 
FROM merchant m 
LEFT JOIN merchant_balance mb ON m.id = mb.merchant_id 
WHERE m.name = '新商户2';
