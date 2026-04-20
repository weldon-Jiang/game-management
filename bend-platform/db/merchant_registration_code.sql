-- Bend Platform 数据库表
-- 商户注册码表

CREATE TABLE IF NOT EXISTS `merchant_registration_code` (
  `id` VARCHAR(36) NOT NULL PRIMARY KEY COMMENT '主键ID',
  `merchant_id` VARCHAR(36) NOT NULL COMMENT '商户ID',
  `code` VARCHAR(50) NOT NULL COMMENT '注册码',
  `status` VARCHAR(20) NOT NULL DEFAULT 'unused' COMMENT '状态: unused-未使用, used-已使用',
  `used_by_agent_id` VARCHAR(50) NULL COMMENT '使用的Agent ID',
  `agent_id` VARCHAR(50) NULL COMMENT '绑定的Agent实例ID',
  `created_at` DATETIME NOT NULL COMMENT '创建时间',
  `expire_time` DATETIME NULL COMMENT '过期时间',
  `used_at` DATETIME NULL COMMENT '使用时间',
  UNIQUE KEY `uk_code` (`code`),
  KEY `idx_merchant_id` (`merchant_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户注册码表';
