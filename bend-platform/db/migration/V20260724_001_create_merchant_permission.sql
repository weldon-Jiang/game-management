-- ================================================
-- 商户使用权限(Permission)表
-- 与 License(软件授权)解耦:
--   - License: 软件授权凭证（终身有效，防拷贝/机器绑定）
--   - Permission: 使用权限（会到期，控制商户能否操作）
--
-- 分控校验时两步检查:
--   ① License 是否有效(active,未吊销,机器匹配)
--   ② Permission 是否有效(active,未到期,未停用)
--   任一失败即拒绝操作
-- ================================================
USE bend_platform;

CREATE TABLE IF NOT EXISTS `merchant_permission` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '所属商户ID',
    `status` VARCHAR(20) NOT NULL DEFAULT 'active' COMMENT '状态: active-有效, expired-已到期, suspended-已停用',
    `expire_at` DATETIME NOT NULL COMMENT '到期时间',
    `max_agents` INT DEFAULT 5 COMMENT '最大Agent数量',
    `max_tasks` INT DEFAULT 50 COMMENT '最大并发任务数',
    `features` TEXT DEFAULT NULL COMMENT '功能特性(JSON)',
    `offline_grace_hours` INT DEFAULT 24 COMMENT '离线宽限小时数',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_merchant_id` (`merchant_id`),
    KEY `idx_status` (`status`),
    KEY `idx_expire_at` (`expire_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户使用权限(Permission)表';

-- merchant_license 表注释更新: 去掉 expire_at 的业务含义
-- 注意: 不删除已有列以兼容历史数据，代码层面不再读写以下列:
--   expire_at, max_agents, max_tasks, features (已迁移到 merchant_permission)
ALTER TABLE merchant_license MODIFY COLUMN `expire_at` DATETIME NULL COMMENT '已废弃(迁移到 merchant_permission)，保留列兼容历史数据';
ALTER TABLE merchant_license MODIFY COLUMN `max_agents` INT DEFAULT NULL COMMENT '已废弃(迁移到 merchant_permission)，保留列兼容历史数据';
ALTER TABLE merchant_license MODIFY COLUMN `max_tasks` INT DEFAULT NULL COMMENT '已废弃(迁移到 merchant_permission)，保留列兼容历史数据';
ALTER TABLE merchant_license MODIFY COLUMN `features` TEXT DEFAULT NULL COMMENT '已废弃(迁移到 merchant_permission)，保留列兼容历史数据';
