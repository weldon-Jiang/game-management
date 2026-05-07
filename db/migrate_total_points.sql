-- 数据迁移脚本（防止数据丢失）
USE bend_platform;

-- 第一步：确保所有商户都有 balance 记录
INSERT IGNORE INTO merchant_balance (id, merchant_id, balance, total_recharged, total_consumed, version, created_time, updated_time)
SELECT UUID(), id, 0, COALESCE(total_points, 0), 0, 0, NOW(), NOW()
FROM merchant
WHERE NOT EXISTS (
    SELECT 1 FROM merchant_balance WHERE merchant_balance.merchant_id = merchant.id
);

-- 第二步：把 merchant.total_points 同步到 merchant_balance.total_recharged
UPDATE merchant_balance mb
INNER JOIN merchant m ON mb.merchant_id = m.id
SET mb.total_recharged = m.total_points
WHERE m.total_points IS NOT NULL 
AND mb.total_recharged < m.total_points;

-- 第三步：（可选）备份后可以删除 merchant.total_points 列
-- ALTER TABLE merchant DROP COLUMN total_points;
