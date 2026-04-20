-- Agent版本表
-- 用于管理Agent的版本信息和更新

CREATE TABLE IF NOT EXISTS `agent_version` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `version` VARCHAR(32) NOT NULL COMMENT '版本号',
    `download_url` VARCHAR(512) NOT NULL COMMENT '下载URL',
    `md5_checksum` VARCHAR(64) DEFAULT NULL COMMENT 'MD5校验码',
    `changelog` TEXT COMMENT '更新日志',
    `mandatory` TINYINT(1) DEFAULT 0 COMMENT '是否强制更新：0-否，1-是',
    `force_restart` TINYINT(1) DEFAULT 0 COMMENT '是否需要重启：0-否，1-是',
    `min_compatible_version` VARCHAR(32) DEFAULT NULL COMMENT '最低兼容版本',
    `status` TINYINT(1) DEFAULT 0 COMMENT '状态：0-未发布，1-已发布',
    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_version` (`version`),
    KEY `idx_status` (`status`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent版本表';
