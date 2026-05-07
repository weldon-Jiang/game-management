-- 快速修复数据一致性问题
USE bend_platform;

-- 查看当前数据状态
SELECT m.id, m.name, m.total_points, mb.balance, mb.total_recharged, mb.total_consumed 
FROM merchant m 
LEFT JOIN merchant_balance mb ON m.id = mb.merchant_id 
WHERE m.name = '新商户2';

-- 修复数据：将 merchant.total_points 设置为 merchant_balance.total_recharged
UPDATE merchant m 
INNER JOIN merchant_balance mb ON m.id = mb.merchant_id 
SET m.total_points = mb.total_recharged 
WHERE m.name = '新商户2';

-- 再次确认修复结果
SELECT m.id, m.name, m.total_points, mb.balance, mb.total_recharged, mb.total_consumed 
FROM merchant m 
LEFT JOIN merchant_balance mb ON m.id = mb.merchant_id 
WHERE m.name = '新商户2';
