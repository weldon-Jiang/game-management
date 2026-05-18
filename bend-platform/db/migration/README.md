# 数据库迁移指南

## 概述
本次迁移为 `agent_instance` 表添加系统资源信息字段，用于存储Agent注册时上报的系统信息。

## 需要添加的字段

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `os_type` | VARCHAR(50) | 操作系统类型 |
| `os_version` | VARCHAR(100) | 操作系统版本 |
| `cpu_count` | INT | CPU核心数 |
| `total_memory_gb` | DECIMAL(5,1) | 总内存(GB) |
| `available_memory_gb` | DECIMAL(5,1) | 可用内存(GB) |
| `total_disk_gb` | DECIMAL(8,1) | 总磁盘空间(GB) |
| `available_disk_gb` | DECIMAL(8,1) | 可用磁盘空间(GB) |
| `system_info_updated_time` | DATETIME | 系统信息更新时间 |

## 迁移步骤

### 方法1：使用Docker容器执行（推荐）

1. 进入MySQL容器：
```bash
docker exec -it bend-xbox-mysql bash
```

2. 连接到MySQL：
```bash
mysql -u root -p
# 输入密码：D@GAMECeKfidb
```

3. 选择数据库并执行迁移：
```sql
USE bend_platform;

-- 添加操作系统类型字段
ALTER TABLE agent_instance 
ADD COLUMN os_type VARCHAR(50) DEFAULT NULL COMMENT '操作系统类型'
AFTER uninstall_reason;

-- 添加操作系统版本字段
ALTER TABLE agent_instance 
ADD COLUMN os_version VARCHAR(100) DEFAULT NULL COMMENT '操作系统版本'
AFTER os_type;

-- 添加CPU核心数字段
ALTER TABLE agent_instance 
ADD COLUMN cpu_count INT DEFAULT NULL COMMENT 'CPU核心数'
AFTER os_version;

-- 添加总内存字段
ALTER TABLE agent_instance 
ADD COLUMN total_memory_gb DECIMAL(5,1) DEFAULT NULL COMMENT '总内存(GB)'
AFTER cpu_count;

-- 添加可用内存字段
ALTER TABLE agent_instance 
ADD COLUMN available_memory_gb DECIMAL(5,1) DEFAULT NULL COMMENT '可用内存(GB)'
AFTER total_memory_gb;

-- 添加总磁盘空间字段
ALTER TABLE agent_instance 
ADD COLUMN total_disk_gb DECIMAL(8,1) DEFAULT NULL COMMENT '总磁盘空间(GB)'
AFTER available_memory_gb;

-- 添加可用磁盘空间字段
ALTER TABLE agent_instance 
ADD COLUMN available_disk_gb DECIMAL(8,1) DEFAULT NULL COMMENT '可用磁盘空间(GB)'
AFTER total_disk_gb;

-- 添加系统信息更新时间字段
ALTER TABLE agent_instance 
ADD COLUMN system_info_updated_time DATETIME DEFAULT NULL COMMENT '系统信息更新时间'
AFTER available_disk_gb;

-- 验证迁移结果
DESCRIBE agent_instance;
```

### 方法2：使用迁移脚本（如果存在）

如果已创建迁移脚本，可以直接执行：

```bash
cd docker
# 使用提供的脚本（如有问题，请用方法1）
.\run-migration.ps1
```

## 验证迁移

执行以下SQL验证字段是否添加成功：

```sql
USE bend_platform;

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
```

## 回滚方案

如果需要回滚，可以删除新添加的字段：

```sql
USE bend_platform;

ALTER TABLE agent_instance 
DROP COLUMN IF EXISTS system_info_updated_time,
DROP COLUMN IF EXISTS available_disk_gb,
DROP COLUMN IF EXISTS total_disk_gb,
DROP COLUMN IF EXISTS available_memory_gb,
DROP COLUMN IF EXISTS total_memory_gb,
DROP COLUMN IF EXISTS cpu_count,
DROP COLUMN IF EXISTS os_version,
DROP COLUMN IF EXISTS os_type;
```

## 注意事项

1. 迁移操作在生产环境请先在测试环境验证
2. 建议在业务低峰期执行迁移
3. 迁移前建议先备份数据库
4. 如果字段已存在，ALTER TABLE 会报错，可以忽略或使用方法1逐个执行

## 后端服务部署

数据库迁移完成后，重新构建和部署后端服务：

```bash
cd docker
docker compose -f docker-compose.yml up -d --build backend
```

或者使用完整部署脚本：

```bash
cd docker
.\deploy.ps1
```