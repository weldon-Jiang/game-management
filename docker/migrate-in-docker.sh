#!/bin/bash
# 在MySQL容器内执行的迁移脚本

# 使用环境变量中的密码
mysql -u root -p${MYSQL_ROOT_PASSWORD} -D bend_platform << 'EOF'
-- 添加操作系统类型字段
ALTER TABLE agent_instance 
ADD COLUMN IF NOT EXISTS os_type VARCHAR(50) DEFAULT NULL COMMENT '操作系统类型'
AFTER uninstall_reason;

-- 添加操作系统版本字段
ALTER TABLE agent_instance 
ADD COLUMN IF NOT EXISTS os_version VARCHAR(100) DEFAULT NULL COMMENT '操作系统版本'
AFTER os_type;

-- 添加CPU核心数字段
ALTER TABLE agent_instance 
ADD COLUMN IF NOT EXISTS cpu_count INT DEFAULT NULL COMMENT 'CPU核心数'
AFTER os_version;

-- 添加总内存字段
ALTER TABLE agent_instance 
ADD COLUMN IF NOT EXISTS total_memory_gb DECIMAL(5,1) DEFAULT NULL COMMENT '总内存(GB)'
AFTER cpu_count;

-- 添加可用内存字段
ALTER TABLE agent_instance 
ADD COLUMN IF NOT EXISTS available_memory_gb DECIMAL(5,1) DEFAULT NULL COMMENT '可用内存(GB)'
AFTER total_memory_gb;

-- 添加总磁盘空间字段
ALTER TABLE agent_instance 
ADD COLUMN IF NOT EXISTS total_disk_gb DECIMAL(8,1) DEFAULT NULL COMMENT '总磁盘空间(GB)'
AFTER available_memory_gb;

-- 添加可用磁盘空间字段
ALTER TABLE agent_instance 
ADD COLUMN IF NOT EXISTS available_disk_gb DECIMAL(8,1) DEFAULT NULL COMMENT '可用磁盘空间(GB)'
AFTER total_disk_gb;

-- 添加系统信息更新时间字段
ALTER TABLE agent_instance 
ADD COLUMN IF NOT EXISTS system_info_updated_time DATETIME DEFAULT NULL COMMENT '系统信息更新时间'
AFTER available_disk_gb;

-- 显示结果
SELECT 'Migration completed!' AS result, NOW() AS executed_at;

-- 验证
SELECT 
    COLUMN_NAME,
    COLUMN_TYPE,
    COLUMN_COMMENT
FROM INFORMATION_SCHEMA.COLUMNS
WHERE TABLE_SCHEMA = 'bend_platform'
AND TABLE_NAME = 'agent_instance'
AND COLUMN_NAME IN (
    'os_type', 'os_version', 'cpu_count', 
    'total_memory_gb', 'available_memory_gb',
    'total_disk_gb', 'available_disk_gb',
    'system_info_updated_time'
)
ORDER BY ORDINAL_POSITION;
EOF