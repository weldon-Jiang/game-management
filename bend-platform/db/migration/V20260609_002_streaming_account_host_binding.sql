SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

CREATE TABLE IF NOT EXISTS `streaming_account_host_binding` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(36) NOT NULL COMMENT '商户ID',
    `streaming_account_id` VARCHAR(36) NOT NULL COMMENT '流媒体账号ID',
    `xbox_host_id` VARCHAR(36) NOT NULL COMMENT '主机ID（xbox_host.id）',
    `source` VARCHAR(32) NOT NULL DEFAULT 'manual' COMMENT '来源：manual/cloud_sync/stream_success',
    `status` VARCHAR(16) NOT NULL DEFAULT 'active' COMMENT '状态：active/inactive',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_account_host` (`streaming_account_id`, `xbox_host_id`),
    KEY `idx_streaming_account` (`streaming_account_id`),
    KEY `idx_xbox_host` (`xbox_host_id`),
    KEY `idx_merchant` (`merchant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='流媒体账号与主机 M:N 绑定表';

INSERT INTO `streaming_account_host_binding` (
    `id`, `merchant_id`, `streaming_account_id`, `xbox_host_id`, `source`, `status`, `created_time`, `updated_time`
)
SELECT
    UUID(),
    `merchant_id`,
    `bound_streaming_account_id`,
    `id`,
    'manual',
    'active',
    NOW(),
    NOW()
FROM `xbox_host`
WHERE `bound_streaming_account_id` IS NOT NULL
  AND `deleted` = 0;
