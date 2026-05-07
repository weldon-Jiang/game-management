-- 修复 merchant_balance 表结构
USE bend_platform;

-- 如果表不存在则创建
CREATE TABLE IF NOT EXISTS merchant_balance (
    id VARCHAR(36) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(36) NOT NULL UNIQUE COMMENT '商户ID',
    balance INT DEFAULT 0 COMMENT '当前点数',
    total_recharged INT DEFAULT 0 COMMENT '累计充值',
    total_consumed INT DEFAULT 0 COMMENT '累计消耗',
    version INT DEFAULT 0 COMMENT '乐观锁版本号',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商户点数账户表';

-- 如果表已存在但缺少字段，则添加字段
ALTER TABLE merchant_balance 
ADD COLUMN IF NOT EXISTS created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间' AFTER version;

-- 检查表结构
DESCRIBE merchant_balance;
