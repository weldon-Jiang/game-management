# ============================================
# Bend Platform Docker 部署指南
# ============================================

## 目录

1. [环境要求](#环境要求)
2. [项目结构](#项目结构)
3. [快速部署](#快速部署)
4. [部署步骤详解](#部署步骤详解)
5. [停止服务](#停止服务)
6. [常用命令](#常用命令)
7. [数据管理](#数据管理)
8. [常见问题](#常见问题)

---

## 环境要求

| 组件 | 版本 | 说明 |
|------|------|------|
| Docker | 20.10+ | [安装指南](https://docs.docker.com/get-docker/) |
| Docker Compose | 2.0+ | 通常随 Docker 一起安装 |
| 内存 | 4GB+ | 推荐 8GB |
| 磁盘 | 20GB+ | 需要存储 MySQL 和 Redis 数据 |

**验证安装：**
```bash
docker --version
docker compose version
```

---

## 项目结构

```
team-management/
├── docker/
│   ├── docker-compose.yml    # Docker Compose 配置（统一管理所有服务）
│   ├── nginx.conf            # Nginx 配置
│   ├── .env.example           # 环境变量模板
│   └── DEPLOY.md              # 本部署文档
├── bend-platform/             # 后端服务
│   ├── Dockerfile             # 后端 Docker 镜像构建文件
│   ├── pom.xml
│   └── src/
├── bend-platform-web/         # 前端服务
│   ├── Dockerfile             # 前端 Docker 镜像构建文件
│   ├── package.json
│   └── src/
└── bend-gateway/              # 网关服务
    └── Dockerfile             # 网关 Docker 镜像构建文件
```

### Dockerfile 位置

| 服务 | Dockerfile 位置 | 说明 |
|------|----------------|------|
| backend | `bend-platform/Dockerfile` | Spring Boot 应用 |
| frontend | `bend-platform-web/Dockerfile` | Vue.js + Nginx |
| gateway | `bend-gateway/Dockerfile` | Spring Cloud Gateway |

---

## 快速部署

### 一键部署（开发/测试环境）

```bash
# 1. 进入项目目录
cd /path/to/team-management

# 2. 复制环境配置文件
cp docker/.env.example .env

# 3. 编辑 .env 文件，修改密码等配置
nano .env

# 4. 一键启动所有服务
docker compose -f docker/docker-compose.yml up -d --build

# 5. 查看服务状态
docker compose -f docker/docker-compose.yml ps
```

### 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3090 | Web 界面 |
| API 网关 | http://localhost:8060 | API 接口 |
| 后端服务 | http://localhost:8061 | 内部后端（不对外暴露） |
| 数据库 | localhost:3306 | MySQL |
| Redis | localhost:6379 | Redis |

**默认账号：**
- 系统管理员：admin / admin123

---

## 部署步骤详解

### 1. 环境配置

```bash
# 创建并编辑环境配置文件
cp docker/.env.example .env
nano .env  # 修改密码等配置
```

**重要配置项：**
```env
# 数据库密码（请修改为强密码）
MYSQL_ROOT_PASSWORD=your_strong_password
MYSQL_PASSWORD=your_strong_password

# Redis 密码
REDIS_PASSWORD=your_redis_password

# JWT 密钥（请修改为随机字符串）
JWT_SECRET=your-very-long-secret-key-at-least-32-characters

# 时区
TZ=Asia/Shanghai
```

### 2. 构建并启动

```bash
# 完整构建（首次构建或代码更新后）
docker compose -f docker/docker-compose.yml up -d --build

# 仅启动（不重新构建）
docker compose -f docker/docker-compose.yml up -d

# 后台运行并查看日志
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml logs -f
```

### 3. 验证部署

```bash
# 检查服务状态
docker compose -f docker/docker-compose.yml ps

# 检查服务健康
curl http://localhost:3090/health        # 前端
curl http://localhost:8060/actuator/health  # 网关
curl http://localhost:8061/actuator/health  # 后端（内部）

# 查看日志
docker compose -f docker/docker-compose.yml logs -f gateway
docker compose -f docker/docker-compose.yml logs -f backend
```

---

## 服务 profile

Docker Compose 使用 profile 来管理不同环境的服务启动：

| profile | 包含服务 | 使用场景 |
|---------|---------|---------|
| `full` | mysql + redis + backend + gateway + frontend | 完整部署 |
| `core` | redis + backend + gateway | 无前端，数据层独立 |
| `data` | mysql + redis | 仅数据层 |

```bash
# 启动完整环境
docker compose -f docker/docker-compose.yml --profile full up -d

# 仅启动核心后端服务
docker compose -f docker/docker-compose.yml --profile core up -d

# 仅启动数据层
docker compose -f docker/docker-compose.yml --profile data up -d
```

---

## 停止服务

### 方式一：优雅停止（推荐）

```bash
# 停止所有服务（保留数据卷）
docker compose -f docker/docker-compose.yml stop

# 停止并移除容器（保留数据卷）
docker compose -f docker/docker-compose.yml down
```

### 方式二：完全停止并清理

```bash
# 停止并移除所有容器、网络（保留数据卷）
docker compose -f docker/docker-compose.yml down

# 停止并移除所有容器、网络、数据卷（危险！会删除数据库）
docker compose -f docker/docker-compose.yml down -v
```

### 方式三：停止单个服务

```bash
# 停止后端
docker compose -f docker/docker-compose.yml stop backend

# 停止前端
docker compose -f docker/docker-compose.yml stop frontend

# 停止数据库
docker compose -f docker/docker-compose.yml stop mysql
```

---

## 常用命令

### 服务管理

```bash
# 启动所有服务
docker compose -f docker/docker-compose.yml start

# 停止所有服务
docker compose -f docker/docker-compose.yml stop

# 重启所有服务
docker compose -f docker/docker-compose.yml restart

# 重启单个服务
docker compose -f docker/docker-compose.yml restart backend

# 查看服务状态
docker compose -f docker/docker-compose.yml ps

# 查看实时日志
docker compose -f docker/docker-compose.yml logs -f
docker compose -f docker/docker-compose.yml logs -f backend  # 仅后端
docker compose -f docker/docker-compose.yml logs -f --tail=100 frontend  # 前端最近100行
```

### 容器操作

```bash
# 进入容器
docker exec -it bend-backend /bin/sh
docker exec -it bend-mysql mysql -u root -p
docker exec -it bend-redis redis-cli

# 查看容器信息
docker inspect bend-backend

# 查看资源使用
docker stats

# 查看网络
docker network ls
```

### 数据库操作

```bash
# 备份数据库
docker exec bend-mysql mysqldump -u root -p${MYSQL_ROOT_PASSWORD} bend_platform > backup.sql

# 恢复数据库
docker exec -i bend-mysql mysql -u root -p${MYSQL_ROOT_PASSWORD} bend_platform < backup.sql

# 导入初始数据
docker exec -i bend-mysql mysql -u root -p${MYSQL_ROOT_PASSWORD} bend_platform < db/schema.sql
```

### 清理

```bash
# 清理未使用的镜像
docker image prune -f

# 清理未使用的卷
docker volume prune -f

# 清理构建缓存
docker builder prune -f

# 完全重置（删除所有容器、镜像、卷）
docker compose -f docker/docker-compose.yml down -v --rmi all
```

---

## 数据管理

### 数据卷位置

```bash
# 查看数据卷
docker volume ls

# 数据卷位置
# MySQL: mysql_data
# Redis: redis_data
```

### 备份数据

```bash
# 创建备份目录
mkdir -p backups

# 备份 MySQL
docker exec bend-mysql mysqldump -u root -p${MYSQL_ROOT_PASSWORD} bend_platform > backups/$(date +%Y%m%d_%H%M%S)_backup.sql

# 备份 Redis
docker exec bend-redis redis-cli -a ${REDIS_PASSWORD} SAVE
docker cp bend-redis:/data/dump.rdb backups/$(date +%Y%m%d_%H%M%S)_dump.rdb
```

### 恢复数据

```bash
# 恢复 MySQL
docker exec -i bend-mysql mysql -u root -p${MYSQL_ROOT_PASSWORD} bend_platform < backups/backup.sql

# 恢复 Redis
docker cp backups/dump.rdb bend-redis:/data/dump.rdb
docker exec bend-redis redis-cli -a ${REDIS_PASSWORD} LOAD
```

---

## 常见问题

### 1. 端口冲突

如果 3090、8060、8061、3306、6379 端口被占用：

```bash
# 修改 .env 中的端口映射
# 然后重启
docker compose -f docker/docker-compose.yml down
docker compose -f docker/docker-compose.yml up -d
```

### 2. 数据库连接失败

```bash
# 检查数据库是否就绪
docker compose -f docker/docker-compose.yml logs mysql | grep "ready for connections"

# 等待 MySQL 完全启动后重试
sleep 30
docker compose -f docker/docker-compose.yml restart backend
```

### 3. 前端无法访问后端 API

```bash
# 检查网络连通性
docker exec bend-frontend ping gateway
docker exec bend-frontend curl http://gateway:8060/actuator/health
docker exec bend-gateway curl http://backend:8061/actuator/health

# 检查 Nginx 配置
docker exec bend-frontend cat /etc/nginx/conf.d/default.conf
```

### 4. 内存不足

```bash
# 增加 Docker 内存限制（Docker Desktop）
# Docker Desktop -> Settings -> Resources -> Memory -> 8GB+

# 或优化 JVM 内存
# 编辑 bend-platform/Dockerfile
# 将 -Xmx1024m 改为 -Xmx512m
```

### 5. 更新代码后重新部署

```bash
# 重新构建并启动
docker compose -f docker/docker-compose.yml up -d --build

# 强制重新构建（不使用缓存）
docker compose -f docker/docker-compose.yml build --no-cache
docker compose -f docker/docker-compose.yml up -d
```

---

## 生产环境注意事项

1. **修改所有密码**：使用强密码替换默认密码
2. **配置 HTTPS**：使用 Nginx 反向代理配置 SSL
3. **数据备份**：设置定时备份任务
4. **日志管理**：配置日志轮转
5. **监控告警**：接入 Prometheus/Grafana
6. **防火墙**：仅开放必要端口

---

## 卸载

```bash
# 停止所有服务并删除
docker compose -f docker/docker-compose.yml down -v

# 删除所有镜像
docker images -q | xargs docker rmi -f

# 删除数据卷（会丢失所有数据！）
docker volume ls | grep bend
docker volume rm <volume_name>

# 清理残留
docker system prune -f
```
