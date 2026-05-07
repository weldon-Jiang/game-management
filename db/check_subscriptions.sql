-- 检查订阅记录
USE bend_platform;

-- 查看所有订阅
SELECT * FROM subscription;

-- 查看新商户2的所有订阅
SELECT 
    s.*,
    m.name as merchant_name
FROM subscription s
LEFT JOIN merchant m ON s.merchant_id = m.id
WHERE m.name = '新商户2';

-- 查看所有设备绑定
SELECT * FROM device_binding;

-- 查看新商户2的设备绑定
SELECT 
    db.*,
    m.name as merchant_name
FROM device_binding db
LEFT JOIN merchant m ON db.merchant_id = m.id
WHERE m.name = '新商户2';
