-- 完整修复数据库表结构
USE bend_platform;

-- 1. 检查并添加 activation_code_batch 表的缺失字段
DESCRIBE activation_code_batch;

-- 添加缺失字段
ALTER TABLE activation_code_batch 
ADD COLUMN IF NOT EXISTS points_amount INT DEFAULT NULL COMMENT '点数数量' AFTER points;

-- 验证修复结果
DESCRIBE activation_code_batch;

-- 2. 检查并添加 activation_code 表的缺失字段
DESCRIBE activation_code;

ALTER TABLE activation_code 
ADD COLUMN IF NOT EXISTS duration_days INT DEFAULT NULL COMMENT '订阅时长(天)' AFTER target_name,
ADD COLUMN IF NOT EXISTS daily_price DECIMAL(10,2) DEFAULT NULL COMMENT '每日价格' AFTER duration_days,
ADD COLUMN IF NOT EXISTS points_amount INT DEFAULT NULL COMMENT '点数数量' AFTER daily_price;

-- 验证修复结果
DESCRIBE activation_code;

SELECT 'Database structure fixed!' AS message;
