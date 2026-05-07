-- 修复错误的数据修复脚本
USE bend_platform;

-- 查看当前错误的数据
SELECT 
    m.id,
    m.name,
    m.total_points,
    mb.balance,
    mb.total_recharged
FROM merchant m
LEFT JOIN merchant_balance mb ON m.id = mb.merchant_id
WHERE m.name = '新商户2';

-- 方案1：如果 merchant_balance.total_recharged 是0，但 balance 是3000
-- 说明激活码充值没有正确累计 total_recharged
UPDATE merchant_balance mb
INNER JOIN merchant m ON mb.merchant_id = m.id
SET 
    mb.total_recharged = mb.balance
WHERE m.name = '新商户2';

-- 同时同步到 merchant 表
UPDATE merchant m
INNER JOIN merchant_balance mb ON m.id = mb.merchant_id
SET m.total_points = mb.total_recharged
WHERE m.name = '新商户2';

-- 验证修复结果
SELECT 
    m.id,
    m.name,
    m.total_points,
    mb.balance,
    mb.total_recharged,
    CASE 
        WHEN m.total_points = mb.total_recharged THEN '✓ 一致' 
        ELSE '✗ 不一致' 
    END AS check_result
FROM merchant m
LEFT JOIN merchant_balance mb ON m.id = mb.merchant_id
WHERE m.name = '新商户2';
