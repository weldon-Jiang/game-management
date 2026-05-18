#!/bin/bash
# =============================================
# 在Docker MySQL容器中执行数据库迁移脚本
# =============================================

set -e

echo "============================================"
echo "Bend Platform 数据库迁移工具"
echo "============================================"
echo ""

# 检查参数
if [ -z "$1" ]; then
    echo "使用方法: $0 <迁移脚本路径>"
    echo "示例: $0 ../bend-platform/db/migration/migrate_simple.sql"
    exit 1
fi

MIGRATION_FILE="$1"

# 检查脚本文件是否存在
if [ ! -f "$MIGRATION_FILE" ]; then
    echo "错误: 迁移脚本文件不存在: $MIGRATION_FILE"
    exit 1
fi

# 检查MySQL容器是否运行
CONTAINER_NAME="bend-xbox-mysql"
echo "检查MySQL容器状态..."
if ! docker ps --filter "name=$CONTAINER_NAME" --format "{{.Names}}" | grep -q "$CONTAINER_NAME"; then
    echo "错误: MySQL容器 $CONTAINER_NAME 未运行"
    exit 1
fi

echo "✓ MySQL容器正在运行"
echo ""

# 复制迁移脚本到容器
echo "复制迁移脚本到容器..."
docker cp "$MIGRATION_FILE" "$CONTAINER_NAME:/tmp/migration.sql"
if [ $? -eq 0 ]; then
    echo "✓ 迁移脚本已复制到容器"
else
    echo "错误: 复制迁移脚本失败"
    exit 1
fi

echo ""

# 执行迁移
echo "开始执行数据库迁移..."
echo "============================================"

docker exec "$CONTAINER_NAME" /bin/bash -c '
    mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -D bend_platform < /tmp/migration.sql
'

if [ $? -eq 0 ]; then
    echo "============================================"
    echo ""
    echo "✓ 数据库迁移执行成功！"
    echo ""
    echo "验证迁移结果:"
    docker exec "$CONTAINER_NAME" mysql -u root -p"${MYSQL_ROOT_PASSWORD}" -D bend_platform -e "
        SELECT 
            COLUMN_NAME,
            COLUMN_TYPE,
            COLUMN_COMMENT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = 'bend_platform'
        AND TABLE_NAME = 'agent_instance'
        AND COLUMN_NAME IN ('os_type', 'os_version', 'cpu_count')
        ORDER BY ORDINAL_POSITION;
    "
else
    echo "============================================"
    echo ""
    echo "✗ 数据库迁移失败"
    exit 1
fi