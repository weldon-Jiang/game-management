# Bend Platform Docker 部署指南

## 📋 概述

本文档涵盖 Bend Platform 项目的完整 Docker 部署流程，包括从首次部署到完全销毁的所有操作。

---

## 🏠 首次部署

### 前置条件
- Docker Desktop 已安装并运行
- 端口未被占用（8060, 8061, 3090, 3306, 6379）

### 1. 启动完整环境

```bash
# 进入项目目录
cd d:\auto-xbox\team-management

# 启动所有服务（首次部署会初始化数据库）
docker-compose up -d

# 查看服务状态
docker-compose ps
```

### 2. 验证服务

```bash
# 检查所有服务健康状态
curl http://localhost:8060/actuator/health   # Gateway
curl http://localhost:8061/actuator/health   # Backend

# 检查 MySQL
docker exec bend-mysql mysqladmin ping -h localhost -u root -p

# 检查 Redis
docker exec bend-redis redis-cli -a D$U@GAMECeKfi ping
```

### 3. 访问服务

| 服务 | 地址 | 说明 |
|------|------|------|
| 前端 | http://localhost:3090 | Web 界面 |
| API 网关 | http://localhost:8060 | API 接口 |
| 后端 | http://localhost:8061 | 内部服务 |
| 数据库 | localhost:3306 | MySQL (仅本地) |
| Redis | localhost:6379 | Redis (仅本地) |

---

## 🚀 日常运维

### 启动服务

```bash
# 启动所有服务
docker-compose up -d

# 启动所有服务（强制重新创建）
docker-compose up -d --force-recreate

# 启动并构建镜像
docker-compose up -d --build
```

### 停止服务

```bash
# 停止所有服务（保留数据）
docker-compose stop

# 停止指定服务
docker-compose stop backend
docker-compose stop gateway
```

### 重启服务

```bash
# 重启所有服务
docker-compose restart

# 重启指定服务
docker-compose restart backend
docker-compose restart gateway
docker-compose restart mysql
docker-compose restart redis
```

### 查看日志

```bash
# 查看所有服务日志
docker-compose logs

# 实时查看所有日志
docker-compose logs -f

# 查看指定服务日志
docker-compose logs -f gateway
docker-compose logs -f backend
docker-compose logs -f mysql
docker-compose logs -f redis
docker-compose logs -f frontend

# 查看最近 N 行日志
docker-compose logs --tail=100 gateway

# 查看指定时间范围的日志
docker-compose logs --since="2024-01-01" backend
```

---

## 🎯 服务组合选择

### 使用 Profile

```bash
# 完整环境（前端 + 后端 + 数据库）
docker-compose --profile full up -d

# 核心后端（无前端）
docker-compose --profile core up -d

# 仅数据层
docker-compose --profile data up -d
```

### 启动单个服务

```bash
# 仅启动 MySQL
docker-compose --profile data up -d mysql

# 仅启动 Redis
docker-compose --profile data up -d redis

# 仅启动后端（需要 MySQL 和 Redis 先运行）
docker-compose --profile core up -d backend

# 仅启动网关（需要后端先运行）
docker-compose --profile core up -d gateway

# 仅启动前端（需要网关先运行）
docker-compose --profile full up -d frontend
```

### 服务启动顺序

```
数据层 (data)
    ↓
后端 (backend) - 依赖 MySQL, Redis
    ↓
网关 (gateway) - 依赖后端
    ↓
前端 (frontend) - 依赖网关
```

---

## 🔧 服务重建

### 重建单个服务

```bash
# 重建后端服务
docker-compose build backend
docker-compose up -d --no-deps backend

# 重建网关服务
docker-compose build gateway
docker-compose up -d --no-deps gateway

# 重建前端服务
docker-compose build frontend
docker-compose up -d --no-deps frontend
```

### 重建所有服务

```bash
# 停止、删除、重新构建、启动
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## 📊 服务管理

### 查看服务状态

```bash
# 查看所有服务状态
docker-compose ps

# 查看所有服务（包括已停止的）
docker-compose ps -a

# 查看服务详情
docker-compose ps mysql
docker inspect bend-mysql
```

### 进入容器

```bash
# 进入 MySQL 容器
docker exec -it bend-mysql mysql -u root -p

# 进入 Redis 容器
docker exec -it bend-redis redis-cli -a D$U@GAMECeKfi

# 进入后端容器
docker exec -it bend-backend sh

# 进入网关容器
docker exec -it bend-gateway sh

# 进入前端容器
docker exec -it bend-frontend sh
```

### 服务健康检查

```bash
# 检查容器健康状态
docker-compose ps

# 手动健康检查
curl http://localhost:8060/actuator/health
curl http://localhost:8061/actuator/health

# 检查端口监听
netstat -ano | findstr ":8060 :8061 :3090"
```

---

## 💾 数据管理

### 查看数据卷

```bash
# 列出所有数据卷
docker volume ls | grep bend

# 查看数据卷详情
docker volume inspect bend_platform_mysql_data
docker volume inspect bend_platform_redis_data
```

### 备份数据库

```bash
# 创建 SQL 备份
docker exec bend-mysql mysqldump -u root -pD$U@GAMECeKfidb bend_platform > backup_$(date +%Y%m%d_%H%M%S).sql

# 备份到指定文件
docker exec bend-mysql mysqldump -u root -pD$U@GAMECeKfidb bend_platform > backup.sql
```

### 恢复数据库

```bash
# 从备份文件恢复
docker exec -i bend-mysql mysql -u root -pD$U@GAMECeKfidb bend_platform < backup.sql
```

### 清理数据卷（谨慎！）

```bash
# 删除 MySQL 数据卷（会丢失所有数据！）
docker volume rm bend_platform_mysql_data

# 删除 Redis 数据卷
docker volume rm bend_platform_redis_data

# 删除所有未使用的数据卷
docker volume prune
```

---

## 🧹 清理与销毁

### 停止并删除容器

```bash
# 停止所有服务并删除容器（保留数据卷）
docker-compose down
```

### 完全清理

```bash
# 删除容器和网络（保留数据卷）
docker-compose down --remove-orphans

# 删除容器、网络和数据卷（会丢失所有数据！）
docker-compose down -v

# 删除容器、网络、数据卷和镜像
docker-compose down -v --rmi all
```

### 删除镜像

```bash
# 删除项目相关镜像
docker rmi bend-platform_backend
docker rmi bend-platform_gateway
docker rmi bend-platform_frontend

# 删除所有未使用的镜像
docker image prune -a
```

### 完全重置（从头开始）

```bash
# 1. 停止所有服务并删除所有资源
docker-compose down -v --remove-orphans --rmi all

# 2. 删除 Docker 残留网络
docker network prune

# 3. 验证清理完成
docker-compose ps -a
docker volume ls | grep bend

# 4. 重新部署
docker-compose up -d
```

---

## 🔄 更新与升级

### 更新代码后重新部署

```bash
# 1. 拉取最新代码
git pull

# 2. 重新构建并启动
docker-compose up -d --build

# 3. 查看日志确认启动成功
docker-compose logs -f backend
```

### 更新单个服务

```bash
# 更新后端
docker-compose build backend
docker-compose up -d --no-deps backend

# 更新网关
docker-compose build gateway
docker-compose up -d --no-deps gateway

# 更新前端
docker-compose build frontend
docker-compose up -d --no-deps frontend
```

---

## ⚙️ 环境配置

### 修改环境变量

```bash
# 1. 编辑 .env 文件
notepad .env

# 2. 使配置生效（重启服务）
docker-compose down
docker-compose up -d
```

### 常见配置修改

```bash
# 修改端口
MYSQL_PORT=127.0.0.1:3307
GATEWAY_PORT=0.0.0.0:8061

# 修改密码
MYSQL_ROOT_PASSWORD=NewPassword123
REDIS_PASSWORD=NewPassword123

# 启用后端 CORS
CORS_ENABLED=true
```

### 查看当前配置

```bash
# 查看所有环境变量
docker-compose config

# 查看特定服务配置
docker-compose config | grep -A 20 "backend:"
```

---

## 🐛 故障排查

### 服务无法启动

```bash
# 1. 查看日志
docker-compose logs gateway
docker-compose logs backend

# 2. 检查端口占用
netstat -ano | findstr ":8060 :8061 :3306 :6379"

# 3. 检查 Docker 状态
docker info
docker ps -a

# 4. 重启 Docker Desktop
```

### MySQL 连接失败

```bash
# 检查 MySQL 容器状态
docker-compose ps mysql

# 查看 MySQL 日志
docker-compose logs mysql

# 检查是否初始化完成
docker-compose logs mysql | grep "ready for connections"

# 等待初始化完成后再试
docker-compose up -d
```

### 数据库初始化未执行

```bash
# 检查数据卷是否存在
docker volume ls | grep mysql_data

# 如果需要重新初始化，必须删除数据卷
docker-compose down -v
docker-compose up -d

# 验证初始化
docker exec bend-mysql mysql -u root -p -e "USE bend_platform; SHOW TABLES;"
```

### 前端无法访问后端

```bash
# 1. 检查网络连通性
docker exec bend-frontend ping backend
docker exec bend-frontend curl http://backend:8061/actuator/health

# 2. 检查网关日志
docker-compose logs gateway

# 3. 检查 Nginx 配置
docker exec bend-frontend cat /etc/nginx/conf.d/default.conf
```

### Redis 连接失败

```bash
# 检查 Redis 容器状态
docker-compose ps redis

# 测试 Redis 连接
docker exec bend-redis redis-cli -a D$U@GAMECeKfi ping

# 查看 Redis 日志
docker-compose logs redis
```

---

## 📝 部署检查清单

部署前确认：

- [ ] Docker Desktop 已启动
- [ ] 端口未被占用
- [ ] `.env` 配置正确
- [ ] 防火墙允许端口访问

部署后确认：

- [ ] 所有服务状态为 `Up`
- [ ] 健康检查通过
- [ ] 可以访问前端页面
- [ ] 登录功能正常

---

## 🔐 安全建议

### 生产环境必须修改

```bash
# 修改所有密码
MYSQL_ROOT_PASSWORD=YourStrongPassword123!
MYSQL_PASSWORD=YourStrongPassword123!
REDIS_PASSWORD=YourStrongPassword123!

# 生成新的 JWT 密钥
# 使用 OpenSSL: openssl rand -base64 32
JWT_SECRET=your_new_jwt_secret_here

# 生成新的 AES 密钥
# 使用 OpenSSL: openssl rand -hex 16
AES_SECRET=your_new_aes_key_here
```

### 端口访问控制

```bash
# 开发环境：仅本地访问
MYSQL_PORT=127.0.0.1:3306

# 生产环境：谨慎开放
MYSQL_PORT=0.0.0.0:3306  # 需要防火墙保护
```

---

## 📞 常用命令速查

| 操作 | 命令 |
|------|------|
| 启动所有服务 | `docker-compose up -d` |
| 停止所有服务 | `docker-compose down` |
| 查看状态 | `docker-compose ps` |
| 查看日志 | `docker-compose logs -f` |
| 重启服务 | `docker-compose restart` |
| 重建服务 | `docker-compose up -d --build` |
| 进入容器 | `docker exec -it <container> sh` |
| 完全清理 | `docker-compose down -v --rmi all` |
| 备份数据库 | `docker exec bend-mysql mysqldump > backup.sql` |
| 恢复数据库 | `docker exec -i bend-mysql mysql < backup.sql` |

---

## 📂 相关文件

- `docker-compose.yml` - Docker Compose 配置
- `.env` - 环境变量配置
- `deploy.bat` - Windows 部署脚本
- `bend-platform/db/schema.sql` - 数据库初始化脚本
- `docker/nginx.conf` - Nginx 配置
