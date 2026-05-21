/*
 * Agent任务历史数据清理脚本
 * 
 * 功能说明：
 * - 清理指定日期之前的任务历史数据
 * - 包含主任务表和子任务表（task_game_account_status）
 * - 可配置保留天数
 * 
 * 适用场景：
 * - 定期清理历史任务数据，释放数据库空间
 * - 测试环境数据清理
 * 
 * 使用方法：
 * 1. 修改保留天数配置（默认保留30天）
 * 2. 在MySQL中执行此脚本
 * 
 * 注意事项：
 * - 建议在执行前备份数据库
 * - 建议在低峰期执行
 * - 执行后无法恢复，请谨慎操作
 */

-- ==============================================
-- 配置参数
-- ==============================================
SET @retention_days = 30;  -- 保留最近N天的数据
SET @cutoff_date = DATE_SUB(CURDATE(), INTERVAL @retention_days DAY);

SELECT CONCAT('清理 ', @retention_days, ' 天前的任务数据，截止日期: ', @cutoff_date) AS '清理配置';

-- ==============================================
-- 1. 统计待清理数据量
-- ==============================================
SELECT '=== 待清理数据统计 ===' AS '统计项';

-- 主任务表待清理数量
SELECT COUNT(*) AS '待清理主任务数' 
FROM task 
WHERE completed_time < @cutoff_date 
  AND status IN ('completed', 'failed', 'cancelled', 'stopped')
  AND deleted = 0;

-- 子任务表待清理数量
SELECT COUNT(*) AS '待清理子任务数' 
FROM task_game_account_status 
WHERE task_id IN (
    SELECT id FROM task 
    WHERE completed_time < @cutoff_date 
      AND status IN ('completed', 'failed', 'cancelled', 'stopped')
      AND deleted = 0
);

-- ==============================================
-- 2. 执行清理
-- ==============================================
SELECT '=== 开始清理 ===' AS '操作';

-- 先清理子任务表（外键依赖）
DELETE FROM task_game_account_status 
WHERE task_id IN (
    SELECT id FROM task 
    WHERE completed_time < @cutoff_date 
      AND status IN ('completed', 'failed', 'cancelled', 'stopped')
      AND deleted = 0
);

SELECT ROW_COUNT() AS '已清理子任务数';

-- 再清理主任务表
DELETE FROM task 
WHERE completed_time < @cutoff_date 
  AND status IN ('completed', 'failed', 'cancelled', 'stopped')
  AND deleted = 0;

SELECT ROW_COUNT() AS '已清理主任务数';

-- ==============================================
-- 3. 验证清理结果
-- ==============================================
SELECT '=== 清理完成验证 ===' AS '验证项';

SELECT COUNT(*) AS '剩余主任务数' FROM task WHERE deleted = 0;
SELECT COUNT(*) AS '剩余子任务数' FROM task_game_account_status;

SELECT '任务历史数据清理完成！' AS '结果';

-- ==============================================
-- 可选：清理自动化使用记录（如果需要）
-- ==============================================
-- DELETE FROM automation_usage 
-- WHERE created_time < @cutoff_date;
-- SELECT ROW_COUNT() AS '已清理自动化使用记录数';
