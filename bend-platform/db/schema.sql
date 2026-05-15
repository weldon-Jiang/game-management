-- Bend Platform 数据库初始化脚本
-- 执行方式: mysql -u root -p bend_platform < db/schema.sql

CREATE DATABASE IF NOT EXISTS bend_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bend_platform;

-- 设置字符集
SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;
SET collation_connection = 'utf8mb4_unicode_ci';

-- ---------------------------------------------
-- 商户表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `merchant` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `phone` VARCHAR(20) NOT NULL COMMENT '联系电话',
    `name` VARCHAR(100) DEFAULT NULL COMMENT '商户名称',
    `status` ENUM('active','expired','suspended') DEFAULT 'active' COMMENT '状态',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    `is_system` TINYINT(1) DEFAULT 0 COMMENT '是否系统内置',
    `total_amount` INT DEFAULT 0 COMMENT '累计消费金额',
    `vip_level` INT DEFAULT 0 COMMENT '当前VIP等级',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_phone` (`phone`),
    KEY `idx_status` (`status`),
    KEY `idx_vip_level` (`vip_level`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户表';

-- ---------------------------------------------
-- 商户用户表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `merchant_user` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(36) NOT NULL COMMENT '商户ID',
    `username` VARCHAR(50) NOT NULL COMMENT '用户名',
    `phone` VARCHAR(20) NOT NULL COMMENT '手机号',
    `password_hash` VARCHAR(255) NOT NULL COMMENT '密码哈希',
    `role` VARCHAR(30) DEFAULT 'operator' COMMENT '角色',
    `status` ENUM('active','disabled') DEFAULT 'active' COMMENT '状态',
    `total_recharged` INT DEFAULT 0 COMMENT '累计充值',
    `last_login_time` DATETIME DEFAULT NULL COMMENT '最后登录时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_phone` (`phone`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户用户表';

-- ---------------------------------------------
-- 商户注册码表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `merchant_registration_code` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(36) NOT NULL COMMENT '商户ID',
    `code` VARCHAR(50) NOT NULL COMMENT '注册码',
    `status` VARCHAR(20) NOT NULL DEFAULT 'unused' COMMENT '状态: unused-未使用',
    `used_by_agent_id` VARCHAR(50) DEFAULT NULL COMMENT '使用的Agent ID',
    `agent_id` VARCHAR(50) DEFAULT NULL COMMENT '绑定的Agent实例ID',
    `created_time` DATETIME NOT NULL COMMENT '创建时间',
    `expire_time` DATETIME DEFAULT NULL COMMENT '过期时间',
    `used_time` DATETIME DEFAULT NULL COMMENT '使用时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户注册码表';

-- ---------------------------------------------
-- 流媒体账号表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `streaming_account` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(36) NOT NULL COMMENT '商户ID',
    `name` VARCHAR(100) NOT NULL COMMENT '账号名称',
    `email` VARCHAR(255) NOT NULL COMMENT '账号邮箱',
    `password_encrypted` VARCHAR(512) DEFAULT NULL COMMENT '加密后的密码',
    `auth_code` VARCHAR(512) DEFAULT NULL COMMENT '认证码',
    `status` ENUM('idle','ready','running','paused','error') DEFAULT 'idle' COMMENT '状态',
    `agent_id` VARCHAR(64) DEFAULT NULL COMMENT '当前绑定的Agent ID',
    `last_error_code` VARCHAR(20) DEFAULT NULL COMMENT '最近错误代码',
    `last_error_message` TEXT DEFAULT NULL COMMENT '最近错误信息',
    `last_error_time` DATETIME DEFAULT NULL COMMENT '最近错误发生时间',
    `error_retry_count` INT DEFAULT 0 COMMENT '错误重试次数',
    `last_heartbeat` DATETIME DEFAULT NULL COMMENT '最后心跳时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_email` (`email`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_agent_id` (`agent_id`),
    KEY `idx_status` (`status`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='流媒体账号表';

-- ---------------------------------------------
-- 游戏账号表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `game_account` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `streaming_id` VARCHAR(36) DEFAULT NULL COMMENT '关联的流媒体账号ID',
    `xbox_game_name` VARCHAR(64) DEFAULT NULL COMMENT 'Xbox游戏名称',
    `xbox_live_email` VARCHAR(255) DEFAULT NULL COMMENT 'Xbox登录邮箱',
    `xbox_live_password_encrypted` VARCHAR(512) DEFAULT NULL COMMENT '加密后的Xbox密码',
    `locked_xbox_id` BIGINT DEFAULT NULL COMMENT '锁定的Xbox ID',
    `is_primary` TINYINT(1) DEFAULT 0 COMMENT '是否为主账号',
    `is_active` TINYINT(1) DEFAULT 1 COMMENT '是否激活',
    `priority` INT DEFAULT 0 COMMENT '使用优先级',
    `daily_match_limit` INT DEFAULT 3 COMMENT '每日比赛限制场次',
    `today_match_count` INT DEFAULT 0 COMMENT '今日已完成场次',
    `total_match_count` INT DEFAULT 0 COMMENT '总比赛场次',
    `last_used_time` DATETIME DEFAULT NULL COMMENT '最后使用时间',
    `agent_id` VARCHAR(64) DEFAULT NULL COMMENT '绑定的Agent ID',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_xbox_game_name` (`xbox_game_name`),
    UNIQUE KEY `uk_xbox_live_email` (`xbox_live_email`),
    KEY `idx_streaming_id` (`streaming_id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_locked_xbox_id` (`locked_xbox_id`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='游戏账号表';

-- ---------------------------------------------
-- Agent版本表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `agent_version` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `version` VARCHAR(32) NOT NULL COMMENT '版本号',
    `download_url` VARCHAR(512) NOT NULL COMMENT '下载URL',
    `md5_checksum` VARCHAR(64) DEFAULT NULL COMMENT 'MD5校验码',
    `changelog` TEXT DEFAULT NULL COMMENT '更新日志',
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
    `max_concurrent_tasks` INT DEFAULT 5 COMMENT '最大并发任务数',
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
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `name` VARCHAR(128) NOT NULL COMMENT '任务名称',
    `description` VARCHAR(512) DEFAULT NULL COMMENT '任务描述',
    `type` VARCHAR(32) NOT NULL COMMENT '任务类型',
    `target_agent_id` VARCHAR(64) DEFAULT NULL COMMENT '目标Agent ID',
    `streaming_account_id` VARCHAR(64) DEFAULT NULL COMMENT '关联的流媒体账号ID',
    `game_account_id` VARCHAR(64) DEFAULT NULL COMMENT '关联的游戏账号ID',
    `status` VARCHAR(16) DEFAULT 'pending' COMMENT '状态：pending-待执行,running-执行中,completed-已完成,failed-失败,cancelled-已取消',
    `priority` INT DEFAULT 0 COMMENT '优先级',
    `params` TEXT DEFAULT NULL COMMENT '任务参数JSON',
    `result` TEXT DEFAULT NULL COMMENT '任务结果JSON',
    `error_message` VARCHAR(512) DEFAULT NULL COMMENT '错误信息',
    `created_by` VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    `assigned_time` DATETIME DEFAULT NULL COMMENT '分配时间',
    `started_time` DATETIME DEFAULT NULL COMMENT '开始执行时间',
    `completed_time` DATETIME DEFAULT NULL COMMENT '完成时间',
    `expire_time` DATETIME DEFAULT NULL COMMENT '过期时间',
    `retry_count` INT DEFAULT 0 COMMENT '重试次数',
    `max_retries` INT DEFAULT 3 COMMENT '最大重试次数',
    `timeout_seconds` INT DEFAULT 3600 COMMENT '超时时间(秒)',
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
-- 激活码批次表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `activation_code_batch` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `batch_name` VARCHAR(128) NOT NULL COMMENT '批次名称',
    `total_count` INT NOT NULL COMMENT '生成总数',
    `used_count` INT DEFAULT 0 COMMENT '已使用数量',
    `remaining_count` INT DEFAULT 0 COMMENT '剩余数量',
    `points` INT DEFAULT NULL COMMENT '充值点数',
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
    `code` VARCHAR(50) NOT NULL COMMENT '激活码',
    `subscription_type` VARCHAR(30) DEFAULT 'points' COMMENT '订阅类型：points-点数充值',
    `bound_resource_type` VARCHAR(30) DEFAULT NULL COMMENT '绑定资源类型',
    `bound_resource_ids` TEXT DEFAULT NULL COMMENT '绑定资源ID列表(JSON)',
    `bound_resource_names` TEXT DEFAULT NULL COMMENT '绑定资源名称列表(JSON)',
    `duration_days` INT DEFAULT 30 COMMENT '有效期天数',
    `original_price` INT DEFAULT NULL COMMENT '原价(分)',
    `discount_price` INT DEFAULT NULL COMMENT '实付价格(分)',
    `points_amount` INT DEFAULT NULL COMMENT '点数金额',
    `start_time` DATETIME DEFAULT NULL COMMENT '开始时间',
    `end_time` DATETIME DEFAULT NULL COMMENT '结束时间',
    `status` VARCHAR(20) DEFAULT 'unused' COMMENT '状态：unused-未使用',
    `used_by` VARCHAR(64) DEFAULT NULL COMMENT '使用者',
    `used_time` DATETIME DEFAULT NULL COMMENT '使用时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_code` (`code`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='激活码表';

-- ---------------------------------------------
-- Xbox主机表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `xbox_host` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(36) NOT NULL COMMENT '商户ID',
    `xbox_id` VARCHAR(64) NOT NULL COMMENT 'Xbox主机ID',
    `name` VARCHAR(100) DEFAULT NULL COMMENT '主机名称',
    `ip_address` VARCHAR(45) DEFAULT NULL COMMENT 'IP地址',
    `bound_streaming_account_id` VARCHAR(36) DEFAULT NULL COMMENT '绑定的流媒体账号ID',
    `bound_gamertag` VARCHAR(50) DEFAULT NULL COMMENT '绑定的Gamertag',
    `power_state` ENUM('On','Off','Standby') DEFAULT 'Off' COMMENT '电源状态',
    `locked_by_agent_id` VARCHAR(36) DEFAULT NULL COMMENT '锁定Agent ID',
    `locked_time` DATETIME DEFAULT NULL COMMENT '锁定时间',
    `lock_expires_time` DATETIME DEFAULT NULL COMMENT '锁定过期时间',
    `status` ENUM('idle','streaming','error') DEFAULT 'idle' COMMENT '状态',
    `last_seen_time` DATETIME DEFAULT NULL COMMENT '最后发现时间',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    `mac_address` VARCHAR(17) DEFAULT NULL COMMENT 'MAC地址',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_xbox_id` (`xbox_id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_bound_streaming_account_id` (`bound_streaming_account_id`),
    KEY `idx_locked_by_agent_id` (`locked_by_agent_id`),
    KEY `idx_status` (`status`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Xbox主机表';

-- ---------------------------------------------
-- VIP分组表 (VIP等级配置)
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `merchant_group` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `name` VARCHAR(64) NOT NULL COMMENT '分组名称',
    `vip_level` INT DEFAULT 1 COMMENT 'VIP等级',
    `amount_threshold` INT DEFAULT 0 COMMENT '升级到此VIP等级需要的累计消费金额阈值',
    `window_original_price` INT NOT NULL DEFAULT 10000 COMMENT '流媒体账号原价',
    `window_discount_price` INT NOT NULL DEFAULT 10000 COMMENT '流媒体账号折后价',
    `account_original_price` INT NOT NULL DEFAULT 5000 COMMENT '游戏账号原价',
    `account_discount_price` INT NOT NULL DEFAULT 5000 COMMENT '游戏账号折后价',
    `host_original_price` INT NOT NULL DEFAULT 20000 COMMENT 'Xbox主机原价',
    `host_discount_price` INT NOT NULL DEFAULT 20000 COMMENT 'Xbox主机折后价',
    `full_original_price` INT NOT NULL DEFAULT 30000 COMMENT '全功能包月原价',
    `full_discount_price` INT NOT NULL DEFAULT 30000 COMMENT '全功能包月折后价',
    `points_original_price` INT NOT NULL DEFAULT 500 COMMENT '点数原价',
    `points_discount_price` INT NOT NULL DEFAULT 500 COMMENT '点数折后价',
    `discount_rate` DECIMAL(5,2) DEFAULT 1.00 COMMENT '折扣比例',
    `unbind_refund_rate` DECIMAL(5,2) DEFAULT 0.50 COMMENT '解绑返还比例',
    `max_unbind_per_week` INT DEFAULT 2 COMMENT '每周解绑上限次数',
    `features` TEXT DEFAULT NULL COMMENT '功能特性(JSON)',
    `host_price` DECIMAL(10,2) DEFAULT 20.00 COMMENT '主机单价',
    `window_price` DECIMAL(10,2) DEFAULT 15.00 COMMENT '窗口单价',
    `account_price` DECIMAL(10,2) DEFAULT 10.00 COMMENT '账号单价',
    `status` VARCHAR(16) DEFAULT 'active' COMMENT '状态',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    `package_price` DECIMAL(10,2) DEFAULT NULL COMMENT '套餐价格',
    `package_duration_days` INT DEFAULT 30 COMMENT '套餐时长(天)',
    `description` VARCHAR(512) DEFAULT NULL COMMENT '描述',
    PRIMARY KEY (`id`),
    KEY `idx_vip_level` (`vip_level`),
    KEY `idx_amount_threshold` (`amount_threshold`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='VIP分组表';

-- ---------------------------------------------
-- 订阅表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `subscription` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `user_id` VARCHAR(64) DEFAULT NULL COMMENT '用户ID',
    `activation_code_id` VARCHAR(64) DEFAULT NULL COMMENT '激活码ID',
    `subscription_type` VARCHAR(32) NOT NULL COMMENT '订阅类型：points-点数充值,window_account-流媒体账号包月,account-游戏账号包月,host-Xbox主机包月,full-全功能包月',
    `bound_resource_type` VARCHAR(32) DEFAULT NULL COMMENT '绑定资源类型',
    `bound_resource_ids` TEXT DEFAULT NULL COMMENT '绑定资源ID列表(JSON)',
    `bound_resource_names` TEXT DEFAULT NULL COMMENT '绑定资源名称列表(JSON)',
    `start_time` DATETIME NOT NULL COMMENT '开始时间',
    `end_time` DATETIME NOT NULL COMMENT '过期时间',
    `original_price` INT DEFAULT NULL COMMENT '原价(分)',
    `discount_price` INT DEFAULT NULL COMMENT '实付价格(分)',
    `status` VARCHAR(20) DEFAULT 'active' COMMENT '状态：active-有效,expired-已过期,cancelled-已取消',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status` (`status`),
    KEY `idx_expire_time` (`end_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订阅表';

-- ---------------------------------------------
-- 订阅定价配置表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `subscription_price` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `group_id` VARCHAR(64) DEFAULT NULL COMMENT 'VIP分组ID',
    `type` VARCHAR(32) DEFAULT NULL COMMENT '订阅类型',
    `price` INT DEFAULT NULL COMMENT '价格(点数)',
    `duration_days` INT DEFAULT NULL COMMENT '时长(天)',
    `status` VARCHAR(16) DEFAULT NULL COMMENT '状态',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_group_id` (`group_id`),
    KEY `idx_type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订阅定价配置表';

-- ---------------------------------------------
-- 充值卡表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `recharge_card` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '商户ID',
    `card_type` VARCHAR(32) DEFAULT NULL COMMENT '卡类型',
    `batch_id` VARCHAR(64) DEFAULT NULL COMMENT '批次ID',
    `card_no` VARCHAR(64) NOT NULL COMMENT '卡号',
    `card_pwd` VARCHAR(128) DEFAULT NULL COMMENT '卡密',
    `denomination` INT DEFAULT NULL COMMENT '面额(点数)',
    `bonus_points` INT DEFAULT NULL COMMENT '赠送点数',
    `points_to_grant` INT DEFAULT NULL COMMENT '发放点数',
    `price` DECIMAL(10,2) DEFAULT NULL COMMENT '售价',
    `status` VARCHAR(16) DEFAULT NULL COMMENT '状态：unused-未使用,sold-已售出,used-已使用,expired-已过期',
    `sold_to_merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '售出商户ID',
    `sold_by_user_id` VARCHAR(64) DEFAULT NULL COMMENT '售出人ID',
    `sold_time` DATETIME DEFAULT NULL COMMENT '售出时间',
    `used_by_merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '使用商户ID',
    `used_by_user_id` VARCHAR(64) DEFAULT NULL COMMENT '使用用户ID',
    `used_time` DATETIME DEFAULT NULL COMMENT '使用时间',
    `expire_time` DATETIME DEFAULT NULL COMMENT '过期时间',
    `used_recharge_record_id` VARCHAR(64) DEFAULT NULL COMMENT '使用的充值记录ID',
    `remark` VARCHAR(512) DEFAULT NULL COMMENT '备注',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_card_no` (`card_no`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_batch_id` (`batch_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值卡表';

-- ---------------------------------------------
-- 操作日志表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `operation_log` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `user_id` VARCHAR(64) DEFAULT NULL COMMENT '操作用户ID',
    `merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '商户ID',
    `action` VARCHAR(64) DEFAULT NULL COMMENT '操作动作',
    `target_type` VARCHAR(64) DEFAULT NULL COMMENT '操作对象类型',
    `target_id` VARCHAR(64) DEFAULT NULL COMMENT '操作对象ID',
    `before_value` TEXT DEFAULT NULL COMMENT '修改前值',
    `after_value` TEXT DEFAULT NULL COMMENT '修改后值',
    `ip_address` VARCHAR(64) DEFAULT NULL COMMENT 'IP地址',
    `user_agent` VARCHAR(512) DEFAULT NULL COMMENT 'User-Agent',
    `description` VARCHAR(512) DEFAULT NULL COMMENT '操作描述',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_action` (`action`),
    KEY `idx_target_type` (`target_type`),
    KEY `idx_created_time` (`created_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='操作日志表';

-- ---------------------------------------------
-- 自动化任务使用记录表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `automation_usage` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `user_id` VARCHAR(64) NOT NULL COMMENT '用户ID',
    `task_id` VARCHAR(64) NOT NULL COMMENT '任务ID',
    `streaming_account_id` VARCHAR(64) NOT NULL COMMENT '流媒体账号ID',
    `streaming_account_name` VARCHAR(128) DEFAULT NULL COMMENT '流媒体账号名称',
    `game_accounts_count` INT DEFAULT 0 COMMENT '游戏账号数量',
    `hosts_count` INT DEFAULT 0 COMMENT '主机数量',
    `resource_type` VARCHAR(32) DEFAULT NULL COMMENT '使用的资源类型',
    `resource_id` VARCHAR(64) DEFAULT NULL COMMENT '资源ID',
    `resource_name` VARCHAR(128) DEFAULT NULL COMMENT '资源名称',
    `charge_mode` VARCHAR(32) DEFAULT 'per_use' COMMENT '扣点模式',
    `points_deducted` INT DEFAULT 0 COMMENT '扣减的点数',
    `subscription_id` VARCHAR(64) DEFAULT NULL COMMENT '关联的订阅ID',
    `usage_time` DATETIME DEFAULT NULL COMMENT '使用时间',
    `remark` VARCHAR(512) DEFAULT NULL COMMENT '备注',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_task_id` (`task_id`),
    KEY `idx_streaming_account_id` (`streaming_account_id`),
    KEY `idx_usage_time` (`usage_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自动化任务使用记录表';

-- ---------------------------------------------
-- 任务游戏账号完成状态表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `task_game_account_status` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `task_id` VARCHAR(64) NOT NULL COMMENT '任务ID',
    `game_account_id` VARCHAR(64) NOT NULL COMMENT '游戏账号ID',
    `streaming_account_id` VARCHAR(64) DEFAULT NULL COMMENT '流媒体账号ID',
    `status` VARCHAR(16) DEFAULT 'pending' COMMENT '状态：pending-待执行,running-执行中,completed-已完成,failed-失败,skipped-跳过',
    `completed_count` INT DEFAULT 0 COMMENT '已完成场次',
    `failed_count` INT DEFAULT 0 COMMENT '失败场次',
    `total_matches` INT DEFAULT 0 COMMENT '总场次',
    `last_match_time` DATETIME DEFAULT NULL COMMENT '最后比赛时间',
    `started_time` DATETIME DEFAULT NULL COMMENT '开始执行时间',
    `completed_time` DATETIME DEFAULT NULL COMMENT '完成时间',
    `error_message` VARCHAR(512) DEFAULT NULL COMMENT '错误信息',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_task_game_account` (`task_id`, `game_account_id`),
    KEY `idx_task_id` (`task_id`),
    KEY `idx_game_account_id` (`game_account_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务游戏账号完成状态表';

-- ---------------------------------------------
-- 商户点数账户表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `merchant_balance` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) NOT NULL COMMENT '商户ID',
    `balance` INT DEFAULT 0 COMMENT '当前余额',
    `total_recharged` INT DEFAULT 0 COMMENT '累计充值',
    `total_consumed` INT DEFAULT 0 COMMENT '累计消费',
    `version` INT DEFAULT 0 COMMENT '乐观锁版本号',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_merchant_id` (`merchant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户点数账户表';

-- ---------------------------------------------
-- 设备绑定记录表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `device_binding` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '商户ID',
    `user_id` VARCHAR(64) DEFAULT NULL COMMENT '用户ID',
    `type` VARCHAR(32) DEFAULT NULL COMMENT '设备类型',
    `device_id` VARCHAR(128) NOT NULL COMMENT '设备ID',
    `device_name` VARCHAR(128) DEFAULT NULL COMMENT '设备名称',
    `device_model` VARCHAR(128) DEFAULT NULL COMMENT '设备型号',
    `bound_subscription_id` VARCHAR(64) DEFAULT NULL COMMENT '绑定的订阅ID',
    `bound_time` DATETIME DEFAULT NULL COMMENT '绑定时间',
    `unbound_time` DATETIME DEFAULT NULL COMMENT '解绑时间',
    `is_active` TINYINT(1) DEFAULT NULL COMMENT '是否激活',
    `unbind_count` INT DEFAULT 0 COMMENT '累计解绑次数',
    `last_unbind_time` DATETIME DEFAULT NULL COMMENT '最后解绑时间',
    `last_bind_subscription_id` VARCHAR(64) DEFAULT NULL COMMENT '最后绑定的订阅ID',
    `remark` VARCHAR(512) DEFAULT NULL COMMENT '备注',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `deleted` TINYINT(1) DEFAULT 0 COMMENT '逻辑删除标记',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_device_id` (`device_id`),
    KEY `idx_bound_subscription_id` (`bound_subscription_id`),
    KEY `idx_deleted` (`deleted`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备绑定记录表';

-- ---------------------------------------------
-- 点数变动记录表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `point_transaction` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '商户ID',
    `user_id` VARCHAR(64) DEFAULT NULL COMMENT '用户ID',
    `type` VARCHAR(32) DEFAULT NULL COMMENT '变动类型：recharge-充值,consume-消费,refund-退款',
    `points` INT DEFAULT NULL COMMENT '变动点数',
    `balance_before` INT DEFAULT NULL COMMENT '变动前余额',
    `balance_after` INT DEFAULT NULL COMMENT '变动后余额',
    `ref_subscription_id` VARCHAR(64) DEFAULT NULL COMMENT '关联订阅ID',
    `ref_device_binding_id` VARCHAR(64) DEFAULT NULL COMMENT '关联设备绑定ID',
    `ref_recharge_record_id` VARCHAR(64) DEFAULT NULL COMMENT '关联充值记录ID',
    `ref_recharge_card_id` VARCHAR(64) DEFAULT NULL COMMENT '关联充值卡ID',
    `description` VARCHAR(512) DEFAULT NULL COMMENT '描述',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_type` (`type`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='点数变动记录表';

-- ---------------------------------------------
-- 充值卡批次表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `recharge_card_batch` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `name` VARCHAR(128) DEFAULT NULL COMMENT '批次名称',
    `card_type` VARCHAR(16) NOT NULL COMMENT '卡类型',
    `target_merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '目标商户ID',
    `total_count` INT NOT NULL COMMENT '生成总数',
    `denomination` INT NOT NULL COMMENT '面额(点数)',
    `bonus_points` INT DEFAULT 0 COMMENT '赠送点数',
    `points_to_grant` INT NOT NULL COMMENT '总发放点数',
    `price` DECIMAL(10,2) DEFAULT NULL COMMENT '售价',
    `valid_days` INT DEFAULT 365 COMMENT '有效期(天)',
    `status` VARCHAR(16) DEFAULT 'pending' COMMENT '状态',
    `generated_count` INT DEFAULT 0 COMMENT '已生成数量',
    `sold_count` INT DEFAULT 0 COMMENT '已售数量',
    `used_count` INT DEFAULT 0 COMMENT '已使用数量',
    `created_by` VARCHAR(64) DEFAULT NULL COMMENT '创建人',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_status` (`status`),
    KEY `idx_target_merchant_id` (`target_merchant_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值卡批次表';

-- ---------------------------------------------
-- 充值记录表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `recharge_record` (
    `id` VARCHAR(64) NOT NULL COMMENT '主键ID',
    `merchant_id` VARCHAR(64) DEFAULT NULL COMMENT '商户ID',
    `user_id` VARCHAR(64) DEFAULT NULL COMMENT '用户ID',
    `amount` DECIMAL(10,2) DEFAULT NULL COMMENT '充值金额',
    `points` INT DEFAULT NULL COMMENT '充值点数',
    `bonus_points` INT DEFAULT NULL COMMENT '赠送点数',
    `payment_method` VARCHAR(32) DEFAULT NULL COMMENT '支付方式',
    `transaction_id` VARCHAR(128) DEFAULT NULL COMMENT '交易流水号',
    `status` VARCHAR(16) DEFAULT NULL COMMENT '状态',
    `remark` VARCHAR(512) DEFAULT NULL COMMENT '备注',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_user_id` (`user_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值记录表';

-- ---------------------------------------------
-- 流媒体账号Xbox登录记录表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `streaming_account_login_record` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `streaming_account_id` VARCHAR(36) NOT NULL COMMENT '流媒体账号ID',
    `xbox_host_id` VARCHAR(36) NOT NULL COMMENT 'Xbox主机ID',
    `logged_gamertag` VARCHAR(100) DEFAULT NULL COMMENT '登录的Gamertag',
    `logged_time` DATETIME DEFAULT NULL COMMENT '登录时间',
    `last_used_time` DATETIME DEFAULT NULL COMMENT '最后使用时间',
    `use_count` INT DEFAULT 0 COMMENT '使用次数',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    PRIMARY KEY (`id`),
    KEY `idx_streaming_account_id` (`streaming_account_id`),
    KEY `idx_xbox_host_id` (`xbox_host_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='流媒体账号Xbox登录记录表';

-- ---------------------------------------------
-- 系统监控指标表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `system_metrics` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `metric_type` VARCHAR(50) NOT NULL COMMENT '指标类型: jvm/system/business',
    `metric_name` VARCHAR(100) NOT NULL COMMENT '指标名称',
    `value` DOUBLE DEFAULT NULL COMMENT '指标值',
    `unit` VARCHAR(20) DEFAULT NULL COMMENT '单位: %/bytes/个/秒',
    `host_name` VARCHAR(100) DEFAULT NULL COMMENT '服务器主机名',
    `description` VARCHAR(255) DEFAULT NULL COMMENT '指标描述',
    `recorded_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间',
    PRIMARY KEY (`id`),
    KEY `idx_metric_type` (`metric_type`),
    KEY `idx_metric_name` (`metric_name`),
    KEY `idx_recorded_time` (`recorded_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统监控指标表';

-- ---------------------------------------------
-- 系统告警表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `system_alert` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `alert_code` VARCHAR(50) NOT NULL COMMENT '告警编码',
    `alert_name` VARCHAR(100) DEFAULT NULL COMMENT '告警名称',
    `severity` VARCHAR(20) NOT NULL COMMENT '告警级别: CRITICAL/HIGH/MEDIUM/LOW',
    `alert_type` VARCHAR(50) NOT NULL COMMENT '告警类型',
    `message` TEXT DEFAULT NULL COMMENT '告警消息',
    `details` JSON DEFAULT NULL COMMENT '告警详情',
    `merchant_id` VARCHAR(36) DEFAULT NULL COMMENT '关联商户ID',
    `agent_id` VARCHAR(36) DEFAULT NULL COMMENT '关联Agent ID',
    `task_id` VARCHAR(36) DEFAULT NULL COMMENT '关联任务ID',
    `status` VARCHAR(20) DEFAULT 'TRIGGERED' COMMENT '状态: TRIGGERED/ACKNOWLEDGED/RESOLVED/IGNORED',
    `triggered_time` DATETIME DEFAULT NULL COMMENT '触发时间',
    `acknowledged_time` DATETIME DEFAULT NULL COMMENT '确认时间',
    `acknowledged_by` VARCHAR(36) DEFAULT NULL COMMENT '确认人ID',
    `resolved_time` DATETIME DEFAULT NULL COMMENT '解决时间',
    `resolved_by` VARCHAR(36) DEFAULT NULL COMMENT '解决人ID',
    `resolution_note` TEXT DEFAULT NULL COMMENT '解决备注',
    `remark` TEXT DEFAULT NULL COMMENT '备注',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_alert_type` (`alert_type`),
    KEY `idx_severity` (`severity`),
    KEY `idx_status` (`status`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_agent_id` (`agent_id`),
    KEY `idx_triggered_time` (`triggered_time`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='系统告警表';

-- ---------------------------------------------
-- 模板表
-- ---------------------------------------------
CREATE TABLE IF NOT EXISTS `template` (
    `id` VARCHAR(36) NOT NULL COMMENT '主键ID',
    `merchant_id` BIGINT NOT NULL COMMENT '商户ID',
    `category` VARCHAR(100) NOT NULL COMMENT '分类',
    `name` VARCHAR(100) NOT NULL COMMENT '模板名称',
    `version` VARCHAR(20) NOT NULL COMMENT '版本',
    `content_type` ENUM('image','json','script') NOT NULL COMMENT '内容类型',
    `file_path` VARCHAR(500) DEFAULT NULL COMMENT '文件路径',
    `file_size` BIGINT DEFAULT NULL COMMENT '文件大小',
    `checksum` VARCHAR(64) DEFAULT NULL COMMENT '校验码',
    `is_current` TINYINT(1) DEFAULT 1 COMMENT '是否当前版本',
    `changelog` TEXT DEFAULT NULL COMMENT '更新日志',
    `created_by` BIGINT DEFAULT NULL COMMENT '创建人',
    `created_time` DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_time` DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_merchant_id` (`merchant_id`),
    KEY `idx_is_current` (`is_current`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模板表';


-- =====================================================
-- 初始化VIP分组数据
-- =====================================================
INSERT INTO merchant_group (id, name, vip_level, amount_threshold, discount_rate, unbind_refund_rate, max_unbind_per_week, features, host_price, window_price, account_price, status)
VALUES
    ('group_vip0', '普通用户', 0, 0, 1.00, 0.50, 1, '{"maxAgents": 2, "maxTasks": 5}', 10.00, 5.00, 8.00, 'active'),
    ('group_vip1', 'VIP1', 1, 100, 0.95, 0.60, 2, '{"maxAgents": 5, "maxTasks": 20}', 9.50, 4.75, 7.60, 'active'),
    ('group_vip2', 'VIP2', 2, 500, 0.90, 0.70, 3, '{"maxAgents": 10, "maxTasks": 50}', 9.00, 4.50, 7.20, 'active'),
    ('group_vip3', 'VIP3', 3, 1000, 0.85, 0.80, 5, '{"maxAgents": 20, "maxTasks": 100}', 8.50, 4.25, 6.80, 'active');

INSERT INTO merchant (id, phone, name, status, created_time, updated_time, deleted, is_system, total_amount, vip_level)
VALUES ('f5d927c40f87f57ef0f4a484d8a823e9', '13800138000', '系统管理员', 'active', '2026-04-16 17:21:58', '2026-04-23 11:16:44', 0, 1, 0, 0);

INSERT INTO merchant_user (id, merchant_id, username, phone, password_hash, role, status, total_recharged, last_login_time, created_time, deleted)
VALUES ('f5d927c40f87f57ef0f4a484d8a823f9', 'f5d927c40f87f57ef0f4a484d8a823e9', 'admin', '13800138000', '5f59b6ec6019c1a1499fc241b5f578b1', 'platform_admin', 'active', 0, '2026-05-07 10:52:43', '2026-04-16 17:21:58', 0);
