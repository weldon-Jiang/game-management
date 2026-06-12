SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

CREATE TABLE IF NOT EXISTS `streaming_account_auth_cache` (
    `streaming_account_id` VARCHAR(36) NOT NULL COMMENT '串流账号ID（streaming_account.id）',
    `merchant_id` VARCHAR(36) NOT NULL COMMENT '商户ID',
    `token_doc_encrypted` MEDIUMTEXT NOT NULL COMMENT 'AES 加密的 xblive token_doc JSON',
    `token_version` INT NOT NULL DEFAULT 0 COMMENT '乐观锁版本',
    `auth_state` VARCHAR(16) NOT NULL DEFAULT 'valid' COMMENT 'valid/refresh_needed/expired',
    `last_auth_agent_id` VARCHAR(64) DEFAULT NULL COMMENT '最近写入 Agent ID',
    `last_auth_time` DATETIME DEFAULT NULL COMMENT '最近认证或刷新时间',
    `xhome_expires_at` DATETIME DEFAULT NULL COMMENT 'xHome gsToken 预估过期时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`streaming_account_id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_auth_state` (`auth_state`),
    KEY `idx_xhome_expires_at` (`xhome_expires_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='串流账号 xblive 认证 Token 平台缓存';
