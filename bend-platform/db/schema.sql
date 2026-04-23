-- Bend Platform 数据库初始化脚本
-- 执行方式: mysql -u root -p bend_platform < db/schema.sql

CREATE DATABASE IF NOT EXISTS bend_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bend_platform;

-- ---------------------------------------------
-- 商户表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `merchant` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `phone` VARCHAR(32) DEFAULT NULL COMMENT '联系电话',
    `name` VARCHAR(128) NOT NULL COMMENT '商户名称',
    `status` VARCHAR(16) DEFAULT NULL COMMENT '状态：active-正常,expired-过期,suspended-暂停',
    `expire_time` DATETIME DEFAULT NULL COMMENT '过期时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_phone` (`phone`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户表';

-- ---------------------------------------------
-- VIP配置表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `vip_config` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `vip_type` VARCHAR(32) NOT NULL COMMENT 'VIP类型',
    `vip_name` VARCHAR(64) NOT NULL COMMENT 'VIP名称',
    `price` DECIMAL(10,2) DEFAULT NULL COMMENT '价格',
    `duration_days` INT DEFAULT NULL COMMENT '时长(天)',
    `features` TEXT COMMENT '功能特性(JSON)',
    `is_default` TINYINT(1) DEFAULT 0 COMMENT '是否默认',
    `status` VARCHAR(16) DEFAULT NULL COMMENT '状态',
    `sort_order` INT DEFAULT 0 COMMENT '排序',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_vip_type` (`vip_type`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='VIP配置表';

-- ---------------------------------------------
-- 商户用户表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `merchant_user` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `username` VARCHAR(64) NOT NULL COMMENT '用户名',
    `phone` VARCHAR(32) DEFAULT NULL COMMENT '手机号',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `role` VARCHAR(32) DEFAULT NULL COMMENT '角色',
    `status` VARCHAR(16) DEFAULT NULL COMMENT '状态',
    `last_login_time` DATETIME DEFAULT NULL COMMENT '最后登录时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_username` (`username`),
    KEY `idx_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户用户表';

-- ---------------------------------------------
-- 商户注册码表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `merchant_registration_code` (
    `id` VARCHAR(36) NOT NULL PRIMARY KEY COMMENT '主键ID',
    `merchant_id` VARCHAR(36) NOT NULL COMMENT '商户ID',
    `code` VARCHAR(50) NOT NULL COMMENT '注册码',
    `status` VARCHAR(20) NOT NULL DEFAULT 'unused' COMMENT '状态: unused-未使用, used-已使用',
    `used_by_agent_id` VARCHAR(50) NULL COMMENT '使用的Agent ID',
    `agent_id` VARCHAR(50) NULL COMMENT '绑定的Agent实例ID',
    `created_time` DATETIME NOT NULL COMMENT '创建时间',
    `expire_time` DATETIME NULL COMMENT '过期时间',
    `used_time` DATETIME NULL COMMENT '使用时间',
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户注册码表';

-- ---------------------------------------------
-- 流媒体账号表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `streaming_account` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `name` VARCHAR(128) NOT NULL COMMENT '账号名称',
    `email` VARCHAR(128) NOT NULL COMMENT '账号邮箱',
    `password_encrypted` VARCHAR(512) DEFAULT NULL COMMENT '加密后的密码',
    `auth_code` VARCHAR(128) DEFAULT NULL COMMENT '认证码',
    `status` VARCHAR(16) DEFAULT 'active' COMMENT '状态：active-正常,inactive-未激活,error-错误,offline-离线',
    `agent_id` VARCHAR(64) DEFAULT NULL COMMENT '当前绑定的Agent ID',
    `last_error_code` VARCHAR(32) DEFAULT NULL COMMENT '最近错误代码',
    `last_error_message` VARCHAR(512) DEFAULT NULL COMMENT '最近错误信息',
    `last_error_time` DATETIME DEFAULT NULL COMMENT '最近错误发生时间',
    `error_retry_count` INT DEFAULT 0 COMMENT '错误重试次数',
    `last_heartbeat` DATETIME DEFAULT NULL COMMENT '最后心跳时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_email` (`email`),
    KEY `idx_status` (`status`),
    KEY `idx_agent_id` (`agent_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='流媒体账号表';

-- ---------------------------------------------
-- 游戏账号表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `game_account` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `streaming_id` VARCHAR(64) NOT NULL COMMENT '关联的流媒体账号ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `name` VARCHAR(128) NOT NULL COMMENT '账号名称',
    `xbox_gamertag` VARCHAR(64) DEFAULT NULL COMMENT 'Xbox Gamertag',
    `xbox_live_email` VARCHAR(128) DEFAULT NULL COMMENT 'Xbox登录邮箱',
    `xbox_live_password_encrypted` VARCHAR(512) DEFAULT NULL COMMENT '加密后的Xbox密码',
    `is_primary` TINYINT(1) DEFAULT 0 COMMENT '是否为主账号',
    `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否激活',
    `priority` INT DEFAULT 0 COMMENT '使用优先级',
    `daily_match_limit` INT DEFAULT 0 COMMENT '每日比赛限制场次',
    `today_match_count` INT DEFAULT 0 COMMENT '今日已完成场次',
    `total_match_count` INT DEFAULT 0 COMMENT '总比赛场次',
    `last_used_time` DATETIME DEFAULT NULL COMMENT '最后使用时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_streaming_id` (`streaming_id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_priority` (`priority`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='游戏账号表';

-- ---------------------------------------------
-- Agent版本表
-- ---------------------------------------------
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
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_version` (`version`),
    KEY `idx_status` (`status`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent版本表';

-- ---------------------------------------------
-- Agent实例表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `agent_instance` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `agent_id` VARCHAR(64) NOT NULL COMMENT 'Agent唯一标识符',
    `agent_secret` VARCHAR(255) DEFAULT NULL COMMENT 'Agent密钥',
    `merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '所属商户ID',
    `registration_code` VARCHAR(64) DEFAULT NULL COMMENT '注册码',
    `host` VARCHAR(64) DEFAULT NULL COMMENT 'Agent主机IP地址',
    `port` INT DEFAULT 8888 COMMENT 'Agent监听端口',
    `version` VARCHAR(32) DEFAULT NULL COMMENT 'Agent版本号',
    `status` VARCHAR(16) DEFAULT 'offline' COMMENT '状态：online-在线,offline-离线,uninstalled-已卸载',
    `current_streaming_id` VARCHAR(64) DEFAULT NULL COMMENT '当前流媒体账号ID',
    `current_task_id` VARCHAR(64) DEFAULT NULL COMMENT '当前任务ID',
    `last_heartbeat` DATETIME DEFAULT NULL COMMENT '最后心跳时间',
    `last_online_time` DATETIME DEFAULT NULL COMMENT '最后上线时间',
    `uninstall_reason` VARCHAR(255) DEFAULT NULL COMMENT '卸载原因',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_agent_id` (`agent_id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_status` (`status`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent实例表';

-- ---------------------------------------------
-- 任务表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `task` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `name` VARCHAR(128) NOT NULL COMMENT '任务名称',
    `description` VARCHAR(512) DEFAULT NULL COMMENT '任务描述',
    `type` VARCHAR(32) NOT NULL COMMENT '任务类型',
    `target_agent_id` VARCHAR(64) DEFAULT NULL COMMENT '目标Agent ID',
    `streaming_account_id` VARCHAR(64) DEFAULT NULL COMMENT '关联的流媒体账号ID',
    `game_account_id` VARCHAR(64) DEFAULT NULL COMMENT '关联的游戏账号ID',
    `status` VARCHAR(16) DEFAULT 'pending' COMMENT '状态：pending-待执行,running-执行中,completed-已完成,failed-失败,cancelled-已取消',
    `priority` INT DEFAULT 0 COMMENT '优先级',
    `params` TEXT COMMENT '任务参数JSON',
    `result` TEXT COMMENT '任务结果JSON',
    `error_message` VARCHAR(512) DEFAULT NULL COMMENT '错误信息',
    `created_by` VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    `assigned_time` DATETIME DEFAULT NULL COMMENT '分配时间',
    `started_time` DATETIME DEFAULT NULL COMMENT '开始执行时间',
    `completed_time` DATETIME DEFAULT NULL COMMENT '完成时间',
    `expire_time` DATETIME DEFAULT NULL COMMENT '过期时间',
    `retry_count` INT DEFAULT 0 COMMENT '重试次数',
    `max_retries` INT DEFAULT 3 COMMENT '最大重试次数',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    KEY `idx_target_agent` (`target_agent_id`),
    KEY `idx_streaming_account` (`streaming_account_id`),
    KEY `idx_game_account` (`game_account_id`),
    KEY `idx_status` (`status`),
    KEY `idx_type` (`type`),
    KEY `idx_created_time` (`created_time`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- ---------------------------------------------
-- 模板表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `template` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `name` VARCHAR(128) NOT NULL COMMENT '模板名称',
    `description` VARCHAR(512) DEFAULT NULL COMMENT '模板描述',
    `category` VARCHAR(32) DEFAULT NULL COMMENT '分类：button,menu,icon,scene,text,other',
    `image_url` VARCHAR(512) NOT NULL COMMENT '模板图片URL',
    `thumbnail_url` VARCHAR(512) DEFAULT NULL COMMENT '缩略图URL',
    `width` INT DEFAULT NULL COMMENT '图片宽度',
    `height` INT DEFAULT NULL COMMENT '图片高度',
    `match_threshold` DECIMAL(3,2) DEFAULT 0.80 COMMENT '匹配阈值',
    `game` VARCHAR(32) DEFAULT NULL COMMENT '所属游戏',
    `region` VARCHAR(32) DEFAULT NULL COMMENT '所属区域',
    `usage_count` INT DEFAULT 0 COMMENT '使用次数',
    `status` TINYINT(1) DEFAULT 1 COMMENT '状态：0-禁用，1-启用',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    KEY `idx_category` (`category`),
    KEY `idx_game` (`game`),
    KEY `idx_status` (`status`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模板表';

-- ---------------------------------------------
-- 激活码批次表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `activation_code_batch` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `batch_name` VARCHAR(128) NOT NULL COMMENT '批次名称',
    `total_count` INT NOT NULL COMMENT '生成总数',
    `used_count` INT DEFAULT 0 COMMENT '已使用数量',
    `remaining_count` INT DEFAULT 0 COMMENT '剩余数量',
    `vip_type` VARCHAR(32) DEFAULT NULL COMMENT 'VIP类型',
    `vip_config_id` VARCHAR(64) DEFAULT NULL COMMENT 'VIP配置ID',
    `status` VARCHAR(16) DEFAULT 'active' COMMENT '状态',
    `expire_time` DATETIME DEFAULT NULL COMMENT '过期时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='激活码批次表';

-- ---------------------------------------------
-- 激活码表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `activation_code` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '商户ID',
    `batch_id` VARCHAR(64) DEFAULT NULL COMMENT '批次ID',
    `code` VARCHAR(128) NOT NULL COMMENT '激活码',
    `status` VARCHAR(16) DEFAULT 'unused' COMMENT '状态：unused-未使用,used-已使用,expired-已过期',
    `used_by` VARCHAR(64) DEFAULT NULL COMMENT '使用者',
    `used_time` DATETIME DEFAULT NULL COMMENT '使用时间',
    `expire_time` DATETIME DEFAULT NULL COMMENT '过期时间',
    `generated_time` DATETIME DEFAULT NULL COMMENT '生成时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_batch_id` (`batch_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='激活码表';

-- ---------------------------------------------
-- 流媒体账号登录记录表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `streaming_account_login_record` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `streaming_account_id` VARCHAR(64) NOT NULL COMMENT '流媒体账号ID',
    `xbox_host_id` VARCHAR(64) DEFAULT NULL COMMENT 'Xbox主机ID',
    `logged_gamertag` VARCHAR(64) DEFAULT NULL COMMENT '登录的Gamertag',
    `logged_time` DATETIME DEFAULT NULL COMMENT '登录时间',
    `last_used_time` DATETIME DEFAULT NULL COMMENT '最后使用时间',
    `use_count` INT DEFAULT 0 COMMENT '使用次数',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_streaming_account_id` (`streaming_account_id`),
    KEY `idx_xbox_host_id` (`xbox_host_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='流媒体账号Xbox登录记录表';

-- ---------------------------------------------
-- Xbox主机表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `xbox_host` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `xbox_id` VARCHAR(128) NOT NULL COMMENT 'Xbox主机ID',
    `name` VARCHAR(128) DEFAULT NULL COMMENT '主机名称',
    `ip_address` VARCHAR(64) DEFAULT NULL COMMENT 'IP地址',
    `status` VARCHAR(16) DEFAULT 'offline' COMMENT '状态：online-在线,offline-离线,in_use-使用中,error-错误',
    `bound_streaming_account_id` VARCHAR(64) DEFAULT NULL COMMENT '绑定的流媒体账号ID',
    `bound_gamertag` VARCHAR(64) DEFAULT NULL COMMENT '绑定的Gamertag',
    `power_state` VARCHAR(16) DEFAULT NULL COMMENT '电源状态: on/off',
    `locked_by_agent_id` VARCHAR(64) DEFAULT NULL COMMENT '锁定Agent ID',
    `locked_time` DATETIME DEFAULT NULL COMMENT '锁定时间',
    `lock_expires_time` DATETIME DEFAULT NULL COMMENT '锁定过期时间',
    `last_seen_time` DATETIME DEFAULT NULL COMMENT '最后发现时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_xbox_id` (`xbox_id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_agent_id` (`locked_by_agent_id`),
    KEY `idx_status` (`status`),
    KEY `idx_bound_streaming_account_id` (`bound_streaming_account_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Xbox主机表';

-- ---------------------------------------------
-- 系统监控指标表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `system_metrics` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '主键（UUID）',
    `metric_type` VARCHAR(50) NOT NULL COMMENT '指标类型: jvm/system/business',
    `metric_name` VARCHAR(100) NOT NULL COMMENT '指标名称',
    `value` DOUBLE COMMENT '指标值',
    `unit` VARCHAR(20) COMMENT '单位: %/bytes/个/秒',
    `host_name` VARCHAR(100) COMMENT '服务器主机名',
    `description` VARCHAR(255) COMMENT '指标描述',
    `recorded_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    INDEX `idx_metric_type` (`metric_type`),
    INDEX `idx_metric_name` (`metric_name`),
    INDEX `idx_recorded_time` (`recorded_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统监控指标表';

-- ---------------------------------------------
-- 系统告警表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `system_alert` (
    `id` VARCHAR(36) PRIMARY KEY COMMENT '主键（UUID）',
    `alert_code` VARCHAR(50) NOT NULL COMMENT '告警编码',
    `alert_name` VARCHAR(100) COMMENT '告警名称',
    `severity` VARCHAR(20) NOT NULL COMMENT '告警级别: CRITICAL/HIGH/MEDIUM/LOW',
    `alert_type` VARCHAR(50) NOT NULL COMMENT '告警类型',
    `message` TEXT COMMENT '告警消息',
    `details` JSON COMMENT '告警详情',
    `merchant_id` VARCHAR(36) COMMENT '关联商户ID',
    `agent_id` VARCHAR(36) COMMENT '关联Agent ID',
    `task_id` VARCHAR(36) COMMENT '关联任务ID',
    `status` VARCHAR(20) DEFAULT 'TRIGGERED' COMMENT '状态: TRIGGERED/ACKNOWLEDGED/RESOLVED/IGNORED',
    `triggered_time` DATETIME COMMENT '触发时间',
    `acknowledged_time` DATETIME COMMENT '确认时间',
    `acknowledged_by` VARCHAR(36) COMMENT '确认人ID',
    `resolved_time` DATETIME COMMENT '解决时间',
    `resolved_by` VARCHAR(36) COMMENT '解决人ID',
    `resolution_note` TEXT COMMENT '解决备注',
    `remark` TEXT COMMENT '备注',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX `idx_alert_type` (`alert_type`),
    INDEX `idx_severity` (`severity`),
    INDEX `idx_status` (`status`),
    INDEX `idx_merchant_id` (`merchant_id`),
    INDEX `idx_agent_id` (`agent_id`),
    INDEX `idx_triggered_time` (`triggered_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统告警表';

-- ---------------------------------------------
-- 批量插入初始化数据（可选）
-- ---------------------------------------------
-- INSERT INTO bend_platform.merchant (id, phone, name, status, expire_time, created_at, updated_at) VALUES ('f5d927c40f87f57ef0f4a484d8a823e9', '13800138000', '系统管理员', 'active', '2099-12-31 23:59:59', '2026-04-16 17:21:58', '2026-04-23 11:16:44');
-- INSERT INTO bend_platform.merchant_user (id, merchant_id, username, phone, password_hash, role, status, last_login_at, created_at) VALUES ('f5d927c40f87f57ef0f4a484d8a823f9', 'f5d927c40f87f57ef0f4a484d8a823e9', 'admin', '13800138000', 'bc9c6ebfa285976aa94186fe90103bc7', 'platform_admin', 'active', '2026-04-23 10:53:00', '2026-04-16 17:21:58');

