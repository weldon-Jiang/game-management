# Bend Platform Docker 部署手册

## 目录

1. [环境准备](#1-环境准备)
2. [Docker 部署架构](#2-docker-部署架构)
3. [部署场景](#3-部署场景)
4. [启动顺序](#4-启动顺序)
5. [停止服务](#5-停止服务)
6. [常见问题](#6-常见问题)

---

## 1. 环境准备

### 1.1 安装 Docker

#### Windows

1. 下载 [Docker Desktop](https://www.docker.com/products/docker-desktop/)
2. 安装并启动 Docker Desktop
3. 确认 WSL 2 已启用（如提示）

#### Ubuntu / Debian

```bash
# 安装 Docker
sudo apt update
sudo apt install docker.io docker-compose

# 启动 Docker
sudo systemctl start docker
sudo systemctl enable docker

# 添加当前用户到 docker 组（免 sudo）
sudo usermod -aG docker $USER
newgrp docker
```

### 1.2 验证安装

```bash
docker --version
docker-compose --version
```

---

## 2. Docker 部署架构

### 2.1 组件说明

| 组件 | 容器名 | 端口 | 说明 |
|------|--------|------|------|
| MySQL | bend-mysql | 3306 | 数据库（仅本地访问） |
| Redis | bend-redis | 6379 | 缓存（仅本地访问） |
| Backend | bend-backend | 8061 | 后端服务（对外暴露） |
| Frontend | bend-frontend | 3090 | 前端界面（对外暴露） |

### 2.2 网络架构

```
                           ┌─────────────────┐
                           │   商户用户      │
                           └────────┬────────┘
                                    │
                                    ▼
┌─────────────┐              ┌─────────────────┐
│   Agent     │─────────────▶│  bend-frontend  │
│             │   HTTP       │    (3090)       │
└─────────────┘              └────────┬────────┘
                                      │ Nginx 反向代理
                                      ▼
                           ┌─────────────────┐
                           │  bend-backend   │
                           │    (8061)       │
                           └────────┬────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
            ┌───────────┐   ┌───────────┐   ┌───────────┐
            │   MySQL   │   │   Redis   │   │  Agent    │
            │   3306    │   │   6379    │   │  WebSocket│
            └───────────┘   └───────────┘   └───────────┘
```

### 2.3 配置文件说明

| 文件 | 说明 |
|------|------|
| `docker-compose.yml` | 基础设施：MySQL + Redis |
| `docker-compose.backend.yml` | 后端服务 |
| `docker-compose.frontend.yml` | 前端服务 |
| `.env` | 环境变量配置 |

---

## 3. 部署场景

### 场景一：首次部署（完整安装）

#### 步骤 1：配置环境变量

编辑 `.env` 文件：

```bash
# 数据库配置
MYSQL_ROOT_PASSWORD=welldn852
MYSQL_DATABASE=bend_platform
MYSQL_USER=weldon
MYSQL_PASSWORD=welldn852

# Redis 配置
REDIS_PASSWORD=welldn852
```

#### 步骤 2：创建 Docker 网络

```bash
docker network create bend-network
```

#### 步骤 3：启动基础设施（MySQL + Redis）

```bash
docker-compose up -d
```

#### 步骤 4：验证 MySQL 和 Redis 启动成功

```bash
docker ps | grep bend-
```

输出应包含 `bend-mysql` 和 `bend-redis`。

#### 步骤 5：初始化数据库

等待 MySQL 完全启动后，执行初始化脚本：

```bash
# 进入后端目录
cd d:\auto-xbox\team-management\bend-platform

# 初始化数据库（Windows）
mysql -h 127.0.0.1 -u welldon -p welldn852 < db\schema.sql

# 初始化数据（Windows）
mysql -h 127.0.0.1 -u welldon -p welldn852 welldn852 < db\data.sql
```

#### 步骤 6：启动后端服务

```bash
docker-compose -f docker-compose.backend.yml up -d
```

#### 步骤 7：启动前端服务

```bash
docker-compose -f docker-compose.frontend.yml up -d
```

#### 步骤 8：验证部署

访问 http://localhost:3090 检查前端是否正常。

---

### 场景二：仅更新后端

当后端代码有修改时，只重新构建和部署后端：

```bash
# 重新构建后端镜像
docker-compose -f docker-compose.backend.yml build backend

# 停止并删除旧容器
docker-compose -f docker-compose.frontend.yml down

# 启动新容器
docker-compose -f docker-compose.frontend.yml up -d
```

或使用一条命令：

```bash
docker-compose -f docker-compose.backend.yml up -d --build backend
```

---

### 场景三：仅更新前端

当前端代码有修改时，只重新构建和部署前端：

```bash
# 重新构建前端镜像
docker-compose -f docker-compose.frontend.yml build frontend

# 停止并删除旧容器
docker-compose -f docker-compose.frontend.yml down

# 启动新容器
docker-compose -f docker-compose.frontend.yml up -d
```

或使用一条命令：

```bash
docker-compose -f docker-compose.frontend.yml up -d --build frontend
```

---

### 场景四：仅重启 MySQL/Redis

```bash
# 重启 MySQL
docker-compose restart mysql

# 重启 Redis
docker-compose restart redis

# 重启两者
docker-compose restart
```

---

### 场景五：查看日志

```bash
# 查看后端日志
docker logs -f bend-backend

# 查看前端日志
docker logs -f bend-frontend

# 查看 MySQL 日志
docker logs -f bend-mysql

# 查看 Redis 日志
docker logs -f bend-redis
```

---

### 场景六：数据备份

#### 备份 MySQL 数据

```bash
# 创建备份目录
mkdir -p backup

# 备份 MySQL
docker exec bend-mysql mysqldump -u welldon -pwelldn852 bend_platform > backup/bend_platform_$(date +%Y%m%d).sql

# 备份 Redis
docker exec bend-redis redis-cli -a welldn852 SAVE
docker cp bend-redis:/data/dump.rdb backup/redis_$(date +%Y%m%d).rdb
```

---

### 场景七：数据恢复

```bash
# 恢复 MySQL
docker exec -i bend-mysql mysql -u welldon -pwelldn852 bend_platform < backup/bend_platform_20240501.sql

# 恢复 Redis
docker cp backup/redis_20240501.rdb bend-redis:/data/dump.rdb
docker exec bend-redis redis-cli -a welldn852 SHUTDOWN NOSAVE
docker restart bend-redis
```

---

## 4. 启动顺序

### 标准启动顺序

```bash
# 1. 创建网络（仅首次需要）
docker network create bend-network

# 2. 启动基础设施（MySQL + Redis）
docker-compose up -d

# 3. 等待 MySQL 就绪（约 30 秒）
docker ps | grep bend-mysql  # 确保状态为 healthy

# 4. 初始化数据库（仅首次需要）
# ... 执行 db/schema.sql 和 db/data.sql ...

# 5. 启动后端
docker-compose -f docker-compose.backend.yml up -d

# 6. 启动前端
docker-compose -f docker-compose.frontend.yml up -d
```

### 验证启动成功

```bash
# 检查所有容器状态
docker ps | grep bend-

# 验证后端健康检查
curl http://localhost:8061/actuator/health

# 验证前端
curl http://localhost:3090
```

---

## 5. 停止服务

### 停止单个服务

```bash
# 停止前端
docker-compose -f docker-compose.frontend.yml stop

# 停止后端
docker-compose -f docker-compose.backend.yml stop

# 停止基础设施
docker-compose stop
```

### 停止并删除容器

```bash
# 删除前端容器
docker-compose -f docker-compose.frontend.yml down

# 删除后端容器
docker-compose -f docker-compose.backend.yml down

# 删除基础设施容器（同时删除数据卷 - 会丢失数据！）
docker-compose down -v
```

### 完全清理（慎用）

```bash
# 删除所有容器和网络
docker-compose -f docker-compose.frontend.yml down
docker-compose -f docker-compose.backend.yml down
docker-compose down

# 删除数据卷（MySQL 和 Redis 数据会丢失）
docker volume rm team-management_mysql_data
docker volume rm team-management_redis_data

# 删除网络
docker network rm bend-network
```

---

## 6. 常见问题

### Q1：MySQL 启动失败，提示 "Access denied"

**原因**：密码中的特殊字符（如 `$`、`#`、`@`）在 Docker 环境变量中未正确转义。

**解决**：
1. 检查 `.env` 文件中的密码是否使用单引号括起来
2. 或修改为不包含特殊字符的密码
3. 重启 MySQL：`docker-compose restart mysql`

### Q2：后端连接 MySQL 失败

**原因**：后端启动时 MySQL 还未就绪。

**解决**：
1. 检查 MySQL 是否就绪：`docker ps` 确保 bend-mysql 状态为 healthy
2. 检查后端日志：`docker logs bend-backend`
3. 等待 MySQL 完全启动后再启动后端

### Q3：前端无法访问后端

**原因**：Nginx 代理配置错误或后端未启动。

**解决**：
1. 检查后端是否运行：`docker ps | grep bend-backend`
2. 检查后端日志：`docker logs bend-backend`
3. 检查 Nginx 配置：确认 `nginx.conf` 中的代理地址正确

### Q4：端口被占用

**解决**：
```bash
# 查找占用端口的进程
netstat -ano | findstr 8061  # Windows
# 或
lsof -i :8061  # Linux

# 结束进程或修改 docker-compose.yml 中的端口映射
```

### Q5：如何更新单个服务而不影响其他服务？

**解决**：使用 `--no-deps` 标志，避免重启依赖服务

```bash
# 只重启后端，不影响 MySQL 和 Redis
docker-compose -f docker-compose.backend.yml up -d --no-deps backend
```

### Q6：如何查看实时日志？

**解决**：
```bash
# 查看所有服务日志
docker-compose logs -f

# 查看特定服务日志
docker-compose logs -f backend
docker-compose logs -f frontend

# 只查看错误日志
docker-compose logs --tail=100 | grep ERROR
```

### Q7：数据卷在哪？如何持久化？

**解决**：
```bash
# 查看数据卷
docker volume ls | grep team-management

# 查看数据卷详情
docker volume inspect team-management_mysql_data

# 数据卷位置
# Windows: C:\ProgramData\Docker\volumes\
# Linux: /var/lib/docker/volumes/
```

---

## 附录：常用命令速查表

| 操作 | 命令 |
|------|------|
| 创建网络 | `docker network create bend-network` |
| 启动基础设施 | `docker-compose up -d` |
| 启动后端 | `docker-compose -f docker-compose.backend.yml up -d` |
| 启动前端 | `docker-compose -f docker-compose.frontend.yml up -d` |
| 停止所有 | `docker-compose down` |
| 重启后端 | `docker-compose -f docker-compose.backend.yml restart backend` |
| 查看日志 | `docker logs -f bend-backend` |
| 进入容器 | `docker exec -it bend-backend bash` |
| 健康检查 | `curl http://localhost:8061/actuator/health` |
