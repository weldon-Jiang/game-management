-- ================================================
-- 商户授权(License)表
-- 用于总控平台对分控(租户)的授权管理:
--   - 每个分控包打包时生成一条 license 记录
--   - 分控启动 + 每30分钟向总控校验 license 有效性
--   - 支持到期、吊销、机器绑定、离线宽限
-- 编码段: 25xxx (License)
-- ================================================
USE bend_platform;

CREATE TABLE IF NOT EXISTS `merchant_license` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '所属商户ID',
    `license_key` VARCHAR(128) NOT NULL COMMENT '授权密钥(分控校验时携带)',
    `license_secret` VARCHAR(255) NOT NULL COMMENT '授权密钥哈希(用于服务端校验license_key)',
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态: active-有效, expired-已过期, revoked-已吊销, pending-未激活',
    `expire_at` DATETIME NOT NULL COMMENT '到期时间',
    `max_agents` INT DEFAULT 5 COMMENT '最大Agent数量',
    `max_tasks` INT DEFAULT 50 COMMENT '最大并发任务数',
    `features` TEXT DEFAULT NULL COMMENT '功能特性(JSON)',
    `bound_machine_fingerprint` VARCHAR(255) DEFAULT NULL COMMENT '绑定的机器指纹(首次激活时写入)',
    `activated_at` DATETIME DEFAULT NULL COMMENT '首次激活时间',
    `last_verified_at` DATETIME DEFAULT NULL COMMENT '分控最近一次校验时间',
    `last_verify_ip` VARCHAR(64) DEFAULT NULL COMMENT '分控最近一次校验来源IP',
    `offline_grace_hours` INT DEFAULT 24 COMMENT '离线宽限小时数(总控不可达时允许继续运行的时长)',
    `revoked_at` DATETIME DEFAULT NULL COMMENT '吊销时间',
    `revoke_reason` VARCHAR(512) DEFAULT NULL COMMENT '吊销原因',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_license_key` (`license_key`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_status` (`status`),
    KEY `idx_expire_at` (`expire_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户授权(License)表';

-- 分控本地缓存最近一次校验结果(签名后),用于离线宽限判断
-- 注意: 该表主要存在于分控库,总控库也可建(记录校验日志),但分控靠本地缓存判活
CREATE TABLE IF NOT EXISTS `license_verify_cache` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `license_key` VARCHAR(128) NOT NULL COMMENT '授权密钥',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `valid` TINYINT(1) NOT NULL DEFAULT 0 COMMENT '校验结果: 1-有效 0-无效',
    `expire_at` DATETIME DEFAULT NULL COMMENT '授权到期时间(校验返回)',
    `features` TEXT DEFAULT NULL COMMENT '功能特性JSON(校验返回)',
    `verified_at` DATETIME NOT NULL COMMENT '本次校验时间(总控服务器时间,签名内)',
    `signature` VARCHAR(512) NOT NULL COMMENT '校验结果签名(防伪造)',
    `raw_payload` TEXT DEFAULT NULL COMMENT '原始签名前JSON',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_license_key` (`license_key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分控License校验缓存(离线宽限用)';
