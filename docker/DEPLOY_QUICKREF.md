# Bend Platform Docker 部署速查

## 两个模式，两个 compose 文件

| 模式 | Compose 文件 | 环境变量 | 包含服务 |
|------|-------------|----------|----------|
| **总控 (Master)** | `docker-compose.master.yml` | `.env` | MySQL + Redis + Backend + Gateway + Frontend |
| **分控 (Tenant)** | `docker-compose.tenant.yml` | `.env.tenant` | Backend + Gateway + Frontend（无 MySQL/Redis 容器） |

## 总控部署

```bash
# 1. 从 .env.example 复制并修改配置
cp .env.example .env

# 2. 启动（首次需 --build）
docker compose -f docker-compose.master.yml up -d --build

# 3. 查看状态
docker compose -f docker-compose.master.yml ps

# 4. 查看日志
docker compose -f docker-compose.master.yml logs -f

# 5. 停止
docker compose -f docker-compose.master.yml down
```

## 分控部署

```bash
# 1. 从 .env.tenant 修改配置（填真实值）
# 必填: DB_HOST, DB_USERNAME, DB_PASSWORD, LICENSE_KEY, LICENSE_SECRET, LICENSE_MASTER_URL

# 2. 启动（首次需 --build）
docker compose --env-file .env.tenant -f docker-compose.tenant.yml up -d --build

# 3. 查看状态
docker compose --env-file .env.tenant -f docker-compose.tenant.yml ps

# 4. 查看日志
docker compose --env-file .env.tenant -f docker-compose.tenant.yml logs -f

# 5. 停止
docker compose --env-file .env.tenant -f docker-compose.tenant.yml down
```

## 端口约定

| 服务 | 总控端口 | 分控端口 |
|------|---------|---------|
| 前端 Web | 3090 | 8090 |
| 网关 (Agent 通信) | 8060 | 8060 |
| 后端 (内部) | 8061 | 8061 |
| MySQL | 3307（宿主机映射） | 3306（直连宿主机） |
| Redis | 6380（宿主机映射） | 不需要 |

## 注意事项

- **分控不需要 Redis**：`application-tenant.yml` 已排除 `RedisAutoConfiguration`，gateway 的 `RateLimitFilter` 检测到无 Redis 会自动放行
- **分控 MySQL 直连宿主机**：不在 Docker 内启动 MySQL 容器，通过 `host.docker.internal` 访问宿主机 3306
- **总控和分控不要同时启动**：端口会冲突（都尝试占用 8060）
