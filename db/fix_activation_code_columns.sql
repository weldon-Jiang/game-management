-- 修复 activation_code 表缺失字段
USE bend_platform;

-- 检查表结构
DESCRIBE activation_code;

-- 添加缺失的字段
ALTER TABLE activation_code 
ADD COLUMN IF NOT EXISTS duration_days INT DEFAULT NULL COMMENT '订阅时长(天)' AFTER target_name,
ADD COLUMN IF NOT EXISTS daily_price DECIMAL(10,2) DEFAULT NULL COMMENT '每日价格' AFTER duration_days,
ADD COLUMN IF NOT EXISTS points_amount INT DEFAULT NULL COMMENT '点数数量' AFTER daily_price;

-- 验证修复结果
DESCRIBE activation_code;
