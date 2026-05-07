-- Bend Platform 数据库建表脚本（完整版）
-- 数据库: bend_platform
-- 字符集: utf8mb4
-- 排序规则: utf8mb4_unicode_ci
-- 主键ID: 使用UUID

CREATE DATABASE IF NOT EXISTS bend_platform DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bend_platform;

-- =====================================================
-- 商户表
-- =====================================================
CREATE TABLE IF NOT EXISTS merchant (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    phone VARCHAR(20) NOT NULL UNIQUE COMMENT '手机号',
    name VARCHAR(100) COMMENT '商户名称',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/expired/suspended',
    expire_time DATETIME COMMENT '账号过期时间',
    total_points INT DEFAULT 0 COMMENT '累计点数',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_phone (phone),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户表';

-- =====================================================
-- 商户用户表（商户子账号）
-- =====================================================
CREATE TABLE IF NOT EXISTS merchant_user (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    username VARCHAR(50) NOT NULL COMMENT '用户名',
    phone VARCHAR(20) NOT NULL COMMENT '手机号',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    role VARCHAR(30) DEFAULT 'operator' COMMENT '角色: owner/admin/operator/platform_admin',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/disabled',
    last_login_at DATETIME COMMENT '最后登录时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_phone (phone),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户用户表';

-- =====================================================
-- 商户注册码表
-- =====================================================
CREATE TABLE IF NOT EXISTS merchant_registration_code (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    code VARCHAR(50) NOT NULL UNIQUE COMMENT '注册码',
    merchant_id VARCHAR(64) COMMENT '关联商户ID（使用后绑定）',
    status VARCHAR(20) DEFAULT 'unused' COMMENT '状态: unused/used/expired',
    expire_time DATETIME COMMENT '过期时间',
    used_by VARCHAR(64) COMMENT '使用者ID',
    used_time DATETIME COMMENT '使用时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_code (code),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户注册码表';

-- =====================================================
-- 商户余额表
-- =====================================================
CREATE TABLE IF NOT EXISTS merchant_balance (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL UNIQUE COMMENT '商户ID',
    balance INT DEFAULT 0 COMMENT '当前余额',
    total_recharged INT DEFAULT 0 COMMENT '累计充值',
    total_consumed INT DEFAULT 0 COMMENT '累计消费',
    version INT DEFAULT 0 COMMENT '版本号（乐观锁）',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户余额表';

-- =====================================================
-- 商户组表
-- =====================================================
CREATE TABLE IF NOT EXISTS merchant_group (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    name VARCHAR(100) NOT NULL COMMENT '组名称',
    description TEXT COMMENT '描述',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='商户组表';

-- =====================================================
-- 串流账号表（包含状态和错误字段）
-- =====================================================
CREATE TABLE IF NOT EXISTS streaming_account (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    name VARCHAR(100) NOT NULL COMMENT '账号名称',
    email VARCHAR(255) NOT NULL COMMENT '邮箱',
    password_encrypted VARCHAR(512) COMMENT '加密密码',
    auth_code VARCHAR(512) COMMENT '认证码',
    status VARCHAR(20) DEFAULT 'idle' COMMENT '状态: idle/busy/error',
    last_error_code VARCHAR(20) COMMENT '最后错误码',
    last_error_message TEXT COMMENT '最后错误信息',
    last_error_at DATETIME COMMENT '最后错误时间',
    error_retry_count INT DEFAULT 0 COMMENT '错误重试次数',
    last_heartbeat DATETIME COMMENT '最后心跳时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_email (email),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='串流账号表';

-- =====================================================
-- 串流账号Xbox登录记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS streaming_account_login_record (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    streaming_account_id VARCHAR(64) NOT NULL COMMENT '串流账号ID',
    xbox_host_id VARCHAR(64) NOT NULL COMMENT 'Xbox主机ID',
    logged_gamertag VARCHAR(100) COMMENT '登录时使用的Gamertag',
    logged_at DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '首次登录时间',
    last_used_at DATETIME COMMENT '最后使用时间',
    use_count INT DEFAULT 0 COMMENT '使用次数',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_streaming_account_id (streaming_account_id),
    INDEX idx_xbox_host_id (xbox_host_id),
    UNIQUE KEY uk_streaming_xbox (streaming_account_id, xbox_host_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='串流账号Xbox登录记录表';

-- =====================================================
-- 游戏账号表
-- =====================================================
CREATE TABLE IF NOT EXISTS game_account (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    streaming_id VARCHAR(64) NOT NULL COMMENT '所属串流账号ID',
    name VARCHAR(100) NOT NULL COMMENT '游戏账号名称',
    xbox_gamertag VARCHAR(50) NOT NULL COMMENT 'Xbox Gamertag',
    xbox_live_email VARCHAR(255) COMMENT 'Xbox Live 邮箱',
    xbox_live_password_encrypted VARCHAR(512) COMMENT '密码加密存储',
    locked_xbox_id VARCHAR(64) COMMENT '当前登录的Xbox主机ID',
    is_primary TINYINT(1) DEFAULT 0 COMMENT '是否主账号',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    priority INT DEFAULT 0 COMMENT '优先级',
    daily_match_limit INT DEFAULT 3 COMMENT '每日比赛次数限制',
    today_match_count INT DEFAULT 0 COMMENT '今日已完成比赛数',
    total_match_count INT DEFAULT 0 COMMENT '历史总比赛数',
    last_used_at DATETIME COMMENT '最后使用时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_streaming_id (streaming_id),
    INDEX idx_locked_xbox_id (locked_xbox_id),
    UNIQUE KEY uk_gamertag (xbox_gamertag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='游戏账号表';

-- =====================================================
-- Xbox主机表
-- =====================================================
CREATE TABLE IF NOT EXISTS xbox_host (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    xbox_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Xbox唯一标识',
    name VARCHAR(100) COMMENT 'Xbox名称',
    ip_address VARCHAR(45) COMMENT 'IP地址',
    mac_address VARCHAR(17) COMMENT 'MAC地址',
    bound_streaming_account_id VARCHAR(64) COMMENT '绑定的串流账号ID',
    bound_gamertag VARCHAR(50) COMMENT '绑定的Gamertag',
    power_state VARCHAR(20) DEFAULT 'Off' COMMENT '电源状态: On/Off/Standby',
    locked_by_agent_id VARCHAR(64) COMMENT '持有锁的Agent ID',
    locked_at DATETIME COMMENT '锁定时间',
    lock_expires_at DATETIME COMMENT '锁过期时间',
    status VARCHAR(20) DEFAULT 'offline' COMMENT '状态: online/offline/error',
    last_seen_at DATETIME COMMENT '最后在线时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_bound_streaming_id (bound_streaming_account_id),
    INDEX idx_power_state (power_state),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Xbox主机表';

-- =====================================================
-- Agent实例表
-- =====================================================
CREATE TABLE IF NOT EXISTS agent_instance (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    agent_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Agent唯一标识',
    host VARCHAR(255) NOT NULL COMMENT '主机地址',
    port INT NOT NULL COMMENT '端口',
    status VARCHAR(20) DEFAULT 'offline' COMMENT '状态: online/offline/busy',
    current_streaming_id VARCHAR(64) COMMENT '当前执行的串流账号ID',
    current_task_id VARCHAR(64) COMMENT '当前任务ID',
    last_heartbeat DATETIME COMMENT '最后心跳时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_agent_id (agent_id),
    INDEX idx_status (status),
    INDEX idx_current_streaming_id (current_streaming_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent实例表';

-- =====================================================
-- Agent版本表
-- =====================================================
CREATE TABLE IF NOT EXISTS agent_version (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    version VARCHAR(20) NOT NULL COMMENT '版本号',
    file_path VARCHAR(500) COMMENT '文件路径',
    file_size BIGINT COMMENT '文件大小',
    checksum VARCHAR(64) COMMENT '文件校验和',
    release_notes TEXT COMMENT '更新日志',
    is_current TINYINT(1) DEFAULT 1 COMMENT '是否为当前版本',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_version (version),
    INDEX idx_is_current (is_current)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='Agent版本表';

-- =====================================================
-- 任务表
-- =====================================================
CREATE TABLE IF NOT EXISTS task (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    type VARCHAR(50) NOT NULL COMMENT '任务类型',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending/running/completed/failed/cancelled',
    config JSON COMMENT '任务配置',
    result JSON COMMENT '任务结果',
    error_message TEXT COMMENT '错误信息',
    started_at DATETIME COMMENT '开始时间',
    finished_at DATETIME COMMENT '结束时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_status (status),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务表';

-- =====================================================
-- 模板表（商户维度的自动化模板）
-- =====================================================
CREATE TABLE IF NOT EXISTS template (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    category VARCHAR(100) NOT NULL COMMENT '模板分类',
    name VARCHAR(100) NOT NULL COMMENT '模板名称',
    version VARCHAR(20) NOT NULL COMMENT '版本号',
    content_type VARCHAR(20) NOT NULL COMMENT '内容类型: image/json/script',
    file_path VARCHAR(500) COMMENT '文件路径',
    file_size BIGINT COMMENT '文件大小',
    checksum VARCHAR(64) COMMENT '文件校验和',
    is_current TINYINT(1) DEFAULT 1 COMMENT '是否为当前版本',
    changelog TEXT COMMENT '更新日志',
    created_by VARCHAR(64) COMMENT '创建人',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_category_name (category, name),
    INDEX idx_is_current (is_current),
    UNIQUE KEY uk_merchant_category_name_version (merchant_id, category, name, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='模板表';

-- =====================================================
-- 设备绑定表
-- =====================================================
CREATE TABLE IF NOT EXISTS device_binding (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    device_id VARCHAR(64) NOT NULL COMMENT '设备ID',
    device_name VARCHAR(100) COMMENT '设备名称',
    device_type VARCHAR(50) COMMENT '设备类型',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/inactive',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_device_id (device_id),
    UNIQUE KEY uk_merchant_device (merchant_id, device_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='设备绑定表';

-- =====================================================
-- 激活码批次表
-- =====================================================
CREATE TABLE IF NOT EXISTS activation_code_batch (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) COMMENT '所属商户',
    batch_name VARCHAR(100) COMMENT '批次名称',
    total_count INT NOT NULL COMMENT '生成总数',
    used_count INT DEFAULT 0 COMMENT '已使用数',
    remaining_count INT DEFAULT 0 COMMENT '剩余数',
    subscription_type VARCHAR(20) DEFAULT 'points' COMMENT '订阅类型: points/game_account/streaming_account/host',
    target_id VARCHAR(64) COMMENT '目标ID',
    target_name VARCHAR(100) COMMENT '目标名称',
    duration_days INT COMMENT '时长(天)',
    daily_price INT COMMENT '每日价格(点数)',
    points_amount INT COMMENT '点数数量',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/inactive/completed',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='激活码批次表';

-- =====================================================
-- 激活码表
-- =====================================================
CREATE TABLE IF NOT EXISTS activation_code (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) COMMENT '所属商户',
    batch_id VARCHAR(64) COMMENT '批次ID',
    code VARCHAR(50) NOT NULL UNIQUE COMMENT '激活码',
    subscription_type VARCHAR(20) DEFAULT 'points' COMMENT '订阅类型: points/game_account/streaming_account/host',
    target_id VARCHAR(64) COMMENT '目标ID',
    target_name VARCHAR(100) COMMENT '目标名称',
    duration_days INT COMMENT '时长(天)',
    daily_price INT COMMENT '每日价格(点数)',
    points_amount INT COMMENT '点数数量',
    status VARCHAR(20) DEFAULT 'unused' COMMENT '状态: unused/used/expired',
    used_by VARCHAR(64) COMMENT '使用者的用户ID',
    used_at DATETIME COMMENT '使用时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_batch_id (batch_id),
    INDEX idx_code (code),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='激活码表';

-- =====================================================
-- 充值卡批次表
-- =====================================================
CREATE TABLE IF NOT EXISTS recharge_card_batch (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    batch_name VARCHAR(100) NOT NULL COMMENT '批次名称',
    total_count INT NOT NULL COMMENT '生成总数',
    used_count INT DEFAULT 0 COMMENT '已使用数',
    remaining_count INT DEFAULT 0 COMMENT '剩余数',
    points_amount INT NOT NULL COMMENT '点数数量',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/inactive/completed',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值卡批次表';

-- =====================================================
-- 充值卡表
-- =====================================================
CREATE TABLE IF NOT EXISTS recharge_card (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    batch_id VARCHAR(64) COMMENT '批次ID',
    code VARCHAR(50) NOT NULL UNIQUE COMMENT '充值码',
    points_amount INT NOT NULL COMMENT '点数数量',
    status VARCHAR(20) DEFAULT 'unused' COMMENT '状态: unused/used/expired',
    used_by VARCHAR(64) COMMENT '使用者的用户ID',
    used_at DATETIME COMMENT '使用时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_batch_id (batch_id),
    INDEX idx_code (code),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值卡表';

-- =====================================================
-- 充值面额配置表
-- =====================================================
CREATE TABLE IF NOT EXISTS recharge_denomination_config (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    name VARCHAR(100) NOT NULL COMMENT '面额名称',
    points_amount INT NOT NULL COMMENT '点数数量',
    price DECIMAL(10,2) NOT NULL COMMENT '价格',
    is_default TINYINT(1) DEFAULT 0 COMMENT '是否默认',
    sort_order INT DEFAULT 0 COMMENT '排序',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/inactive',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值面额配置表';

-- =====================================================
-- 充值记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS recharge_record (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    type VARCHAR(20) NOT NULL COMMENT '类型: card/payment',
    amount INT NOT NULL COMMENT '点数数量',
    reference_id VARCHAR(64) COMMENT '关联ID（充值卡ID或支付订单ID）',
    created_by VARCHAR(64) COMMENT '创建人',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值记录表';

-- =====================================================
-- 点数交易记录表
-- =====================================================
CREATE TABLE IF NOT EXISTS point_transaction (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    type VARCHAR(20) NOT NULL COMMENT '类型: recharge/consume/refund',
    amount INT NOT NULL COMMENT '金额（正数充值，负数消费）',
    balance_before INT NOT NULL COMMENT '变动前余额',
    balance_after INT NOT NULL COMMENT '变动后余额',
    description TEXT COMMENT '描述',
    reference_id VARCHAR(64) COMMENT '关联ID',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_type (type),
    INDEX idx_created_time (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='点数交易记录表';

-- =====================================================
-- 订阅表
-- =====================================================
CREATE TABLE IF NOT EXISTS subscription (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) NOT NULL COMMENT '所属商户',
    type VARCHAR(20) NOT NULL COMMENT '类型: points/game_account/streaming_account/host',
    target_id VARCHAR(64) COMMENT '目标ID',
    target_name VARCHAR(100) COMMENT '目标名称',
    start_time DATETIME NOT NULL COMMENT '开始时间',
    end_time DATETIME NOT NULL COMMENT '结束时间',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/expired/cancelled',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_status (status),
    INDEX idx_type (type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订阅表';

-- =====================================================
-- 订阅价格表
-- =====================================================
CREATE TABLE IF NOT EXISTS subscription_price (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    type VARCHAR(20) NOT NULL COMMENT '类型: points/game_account/streaming_account/host',
    duration_days INT NOT NULL COMMENT '时长(天)',
    price INT NOT NULL COMMENT '价格(点数)',
    description VARCHAR(200) COMMENT '描述',
    status VARCHAR(20) DEFAULT 'active' COMMENT '状态: active/inactive',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_type (type),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='订阅价格表';

-- =====================================================
-- 系统指标表
-- =====================================================
CREATE TABLE IF NOT EXISTS system_metrics (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    metric_type VARCHAR(50) NOT NULL COMMENT '指标类型',
    metric_name VARCHAR(100) NOT NULL COMMENT '指标名称',
    metric_value DECIMAL(20,2) NOT NULL COMMENT '指标值',
    metric_unit VARCHAR(20) COMMENT '单位',
    recorded_at DATETIME NOT NULL COMMENT '记录时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_metric_type (metric_type),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统指标表';

-- =====================================================
-- 系统告警表
-- =====================================================
CREATE TABLE IF NOT EXISTS system_alert (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    alert_type VARCHAR(50) NOT NULL COMMENT '告警类型',
    alert_level VARCHAR(20) NOT NULL COMMENT '告警级别: info/warning/error/critical',
    title VARCHAR(200) NOT NULL COMMENT '告警标题',
    content TEXT COMMENT '告警内容',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending/resolved/ignored',
    resolved_by VARCHAR(64) COMMENT '处理人',
    resolved_at DATETIME COMMENT '处理时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_alert_type (alert_type),
    INDEX idx_alert_level (alert_level),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='系统告警表';

-- =====================================================
-- 自动化任务表
-- =====================================================
CREATE TABLE IF NOT EXISTS automation_task (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    merchant_id VARCHAR(64) COMMENT '所属商户',
    agent_id VARCHAR(64) COMMENT '执行的Agent',
    streaming_id VARCHAR(64) NOT NULL COMMENT '串流账号ID',
    game_id VARCHAR(64) COMMENT '游戏账号ID',
    task_type VARCHAR(50) NOT NULL COMMENT '任务类型: login/stream/game_switch/custom',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '状态: pending/running/paused/completed/failed/cancelled',
    started_at DATETIME COMMENT '开始时间',
    finished_at DATETIME COMMENT '结束时间',
    result JSON COMMENT '执行结果',
    error_message TEXT COMMENT '错误信息',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_agent_id (agent_id),
    INDEX idx_streaming_id (streaming_id),
    INDEX idx_status (status),
    INDEX idx_created_time (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='自动化任务表';

-- =====================================================
-- 任务统计表
-- =====================================================
CREATE TABLE IF NOT EXISTS task_statistics (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    streaming_id VARCHAR(64) NOT NULL COMMENT '串流账号ID',
    game_id VARCHAR(64) COMMENT '游戏账号ID',
    stat_date DATE NOT NULL COMMENT '统计日期',
    total_tasks INT DEFAULT 0 COMMENT '总任务数',
    completed_tasks INT DEFAULT 0 COMMENT '完成任务数',
    failed_tasks INT DEFAULT 0 COMMENT '失败任务数',
    total_duration_seconds BIGINT DEFAULT 0 COMMENT '总执行时长(秒)',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    UNIQUE KEY uk_stream_game_date (streaming_id, game_id, stat_date),
    INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='任务统计表';

-- =====================================================
-- 串流错误日志表
-- =====================================================
CREATE TABLE IF NOT EXISTS streaming_error_log (
    id VARCHAR(64) PRIMARY KEY COMMENT '主键（UUID）',
    streaming_account_id VARCHAR(64) NOT NULL COMMENT '串流账号ID',
    xbox_host_id VARCHAR(64) COMMENT 'Xbox主机ID',
    error_code VARCHAR(20) NOT NULL COMMENT '错误码',
    error_message TEXT COMMENT '错误信息',
    error_trace TEXT COMMENT '错误堆栈',
    severity VARCHAR(20) NOT NULL COMMENT '严重程度: HIGH/MEDIUM/LOW',
    retry_count INT DEFAULT 0 COMMENT '重试次数',
    resolved_at DATETIME COMMENT '解决时间',
    created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    INDEX idx_account_id (streaming_account_id),
    INDEX idx_error_code (error_code),
    INDEX idx_created_time (created_time)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='串流错误日志表';



-- =====================================================
-- 初始化管理员数据
-- =====================================================
-- 密码加密方式: AES-128-ECB ZeroPadding
-- 加密密钥: bend-platform-se (16字节)
-- 加密结果: HEX(AES_ENCRYPT(明文密码, 密钥))
-- Java解密: 使用相同密钥解密后去除零填充
-- 默认密码: 123456

INSERT INTO merchant (id, phone, name, status, expire_time, total_points)
VALUES ('system-admin', '13800138000', '系统管理员', 'active', '2099-12-31 23:59:59', 0)
ON DUPLICATE KEY UPDATE name=name;

INSERT INTO merchant_user (id, merchant_id, username, phone, password_hash, role, status)
VALUES ('admin-001', 'system-admin', 'admin', '13800138000', 'A66650E65FD4124AEAE0F50E73116881', 'platform_admin', 'active')
ON DUPLICATE KEY UPDATE password_hash=password_hash;
