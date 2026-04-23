-- ================================================
-- 时间字段重命名修复脚本 v2
-- ================================================
-- 将所有 _at 后缀的时间字段改为 _time 后缀
-- ================================================

USE bend_platform;

-- ================================================
-- merchant 表
-- ================================================
ALTER TABLE merchant CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE merchant CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- vip_config 表
-- ================================================
ALTER TABLE vip_config CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE vip_config CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- merchant_user 表
-- ================================================
ALTER TABLE merchant_user CHANGE COLUMN last_login_at last_login_time DATETIME DEFAULT NULL COMMENT '最后登录时间';
ALTER TABLE merchant_user CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';

-- ================================================
-- merchant_registration_code 表
-- ================================================
ALTER TABLE merchant_registration_code CHANGE COLUMN created_at created_time DATETIME NOT NULL COMMENT '创建时间';
ALTER TABLE merchant_registration_code CHANGE COLUMN used_at used_time DATETIME NULL COMMENT '使用时间';

-- ================================================
-- streaming_account 表
-- ================================================
ALTER TABLE streaming_account CHANGE COLUMN last_error_at last_error_time DATETIME DEFAULT NULL COMMENT '最近错误发生时间';
ALTER TABLE streaming_account CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE streaming_account CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- game_account 表
-- ================================================
ALTER TABLE game_account CHANGE COLUMN last_used_at last_used_time DATETIME DEFAULT NULL COMMENT '最后使用时间';
ALTER TABLE game_account CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE game_account CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- agent_version 表
-- ================================================
ALTER TABLE agent_version CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE agent_version CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- agent_instance 表
-- ================================================
ALTER TABLE agent_instance CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE agent_instance CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- task 表
-- ================================================
ALTER TABLE task CHANGE COLUMN assigned_at assigned_time DATETIME DEFAULT NULL COMMENT '分配时间';
ALTER TABLE task CHANGE COLUMN started_at started_time DATETIME DEFAULT NULL COMMENT '开始执行时间';
ALTER TABLE task CHANGE COLUMN completed_at completed_time DATETIME DEFAULT NULL COMMENT '完成时间';
ALTER TABLE task CHANGE COLUMN expire_at expire_time DATETIME DEFAULT NULL COMMENT '过期时间';
ALTER TABLE task CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE task CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';
ALTER TABLE task DROP INDEX idx_created_at;
ALTER TABLE task ADD INDEX idx_created_time (created_time);

-- ================================================
-- template 表
-- ================================================
ALTER TABLE template CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE template CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- activation_code_batch 表
-- ================================================
ALTER TABLE activation_code_batch CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE activation_code_batch CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- activation_code 表
-- ================================================
ALTER TABLE activation_code CHANGE COLUMN used_at used_time DATETIME DEFAULT NULL COMMENT '使用时间';
ALTER TABLE activation_code CHANGE COLUMN generated_at generated_time DATETIME DEFAULT NULL COMMENT '生成时间';
ALTER TABLE activation_code CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE activation_code CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- streaming_account_login_record 表
-- ================================================
ALTER TABLE streaming_account_login_record CHANGE COLUMN logged_at logged_time DATETIME DEFAULT NULL COMMENT '登录时间';
ALTER TABLE streaming_account_login_record CHANGE COLUMN last_used_at last_used_time DATETIME DEFAULT NULL COMMENT '最后使用时间';
ALTER TABLE streaming_account_login_record CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';

-- ================================================
-- xbox_host 表
-- ================================================
ALTER TABLE xbox_host CHANGE COLUMN locked_at locked_time DATETIME DEFAULT NULL COMMENT '锁定时间';
ALTER TABLE xbox_host CHANGE COLUMN lock_expires_at lock_expires_time DATETIME DEFAULT NULL COMMENT '锁定过期时间';
ALTER TABLE xbox_host CHANGE COLUMN last_seen_at last_seen_time DATETIME DEFAULT NULL COMMENT '最后发现时间';
ALTER TABLE xbox_host CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE xbox_host CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';

-- ================================================
-- system_metrics 表
-- ================================================
ALTER TABLE system_metrics CHANGE COLUMN recorded_at recorded_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '记录时间';
ALTER TABLE system_metrics DROP INDEX idx_recorded_at;
ALTER TABLE system_metrics ADD INDEX idx_recorded_time (recorded_time);

-- ================================================
-- system_alert 表
-- ================================================
ALTER TABLE system_alert CHANGE COLUMN triggered_at triggered_time DATETIME COMMENT '触发时间';
ALTER TABLE system_alert CHANGE COLUMN acknowledged_at acknowledged_time DATETIME COMMENT '确认时间';
ALTER TABLE system_alert CHANGE COLUMN resolved_at resolved_time DATETIME COMMENT '解决时间';
ALTER TABLE system_alert CHANGE COLUMN created_at created_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间';
ALTER TABLE system_alert CHANGE COLUMN updated_at updated_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间';
ALTER TABLE system_alert DROP INDEX idx_triggered_at;
ALTER TABLE system_alert ADD INDEX idx_triggered_time (triggered_time);

-- ================================================
-- 验证结果
-- ================================================
SELECT '重命名完成! 所有 _at 字段已改为 _time' AS result;
