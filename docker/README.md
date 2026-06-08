# Docker 启动 / 打包部署使用指南

本目录提供按环境（dev / sit / prod）一键启动、单服务打包部署、停服清理的脚本，统一基于 `docker-compose.yml` 与各自的 `.env.<env>` 文件。

> 在 PowerShell（Windows）中执行，工作目录无要求，脚本会自动切换到 `docker/` 目录。

---

## 1. 文件总览

| 文件 | 作用 |
|------|------|
| `docker-compose.yml` | 服务编排定义 |
| `.env.dev` / `.env.sit` / `.env.prod` | 各环境变量（含密钥、端口、Spring Profile）。**已被 `.gitignore` 忽略，请勿提交** |
| `start-dev.ps1` / `start-sit.ps1` / `start-prod.ps1` | 启动 / 打包部署 |
| `compose-up.ps1` | 启动脚本内部共用（正确组装 `docker compose up` 参数） |
| `hot-deploy-dev.ps1` | Dev 热部署：本地编译 + `docker cp` + 重启（无需 `docker build`） |
| `stop-dev.ps1` / `stop-sit.ps1` / `stop-prod.ps1` | 停服 / 清理 |

---

## 2. Profile 说明（控制启动哪些服务，与环境无关）

| Profile | 启动的服务 | 适用场景 |
|---------|-----------|---------|
| `data` | MySQL + Redis | 仅起数据层 |
| `core` | Redis + 后端 + 网关 | 无 MySQL/前端的核心联调 |
| `app`  | 前端 + 后端 + 网关 | 应用层（数据层另起或外部托管） |
| `full` | MySQL + Redis + 后端 + 网关 + 前端 | **默认**，完整环境 |

> 指定 `-Services` 单独打包某服务时，脚本会自动用 `full` profile 以保证依赖服务名（mysql/redis）可解析，但只会重建你点名的服务。

---

## 3. 启动 / 打包部署

### 3.1 首次全量部署（构建全部服务）

```powershell
cd docker
./start-sit.ps1            # SIT 环境全量
./start-dev.ps1            # 开发环境全量
./start-prod.ps1          # 生产环境全量（含密钥确认，见 §5）
```

### 3.2 后续只重新打包部署一个 / 多个服务

```powershell
./start-sit.ps1 -Services backend                 # 只重打 backend
./start-sit.ps1 -Services backend,gateway         # 重打 backend + gateway
./start-sit.ps1 -Services frontend                # 只重打前端
```

### 3.3 只重启、不重新构建（改了配置/环境变量时）

```powershell
./start-sit.ps1 -Services backend -NoBuild
```

### 3.4 Dev 热部署（镜像源不可用 / 快速验证代码）

容器已启动时，本地编译后替换容器内产物，**不触发 `docker build`**：

```powershell
./hot-deploy-dev.ps1                         # backend + gateway + frontend
./hot-deploy-dev.ps1 -Services backend       # 仅后端
./hot-deploy-dev.ps1 -Services backend,gateway
./hot-deploy-dev.ps1 -SkipBuild              # 已有 target/dist，仅复制并重启
```

前提：先 `./start-dev.ps1 -NoBuild` 确保 `bend-xbox-{backend,gateway,frontend}` 在运行。

> Agent（Python）改动不在此脚本范围，需本地重启 Agent 进程。

### 3.5 按 profile 控制启动范围

```powershell
./start-sit.ps1 -Profile app      # 前端+后端+网关
./start-sit.ps1 -Profile core     # Redis+后端+网关
./start-sit.ps1 -Profile data     # 仅 MySQL+Redis
```

> `app` 只起应用层，运行期仍需 MySQL/Redis 可达：要么先 `./start-sit.ps1 -Profile data` 起数据层（同网络按 `mysql`/`redis` 主机名连通），要么连外部库。

### 启动脚本参数

| 参数 | 说明 | 默认 |
|------|------|------|
| `-Profile <name>` | 启动范围：`data` / `core` / `app` / `full` | `full` |
| `-Services a,b` | 仅打包部署指定服务（逗号分隔） | 空=全部 |
| `-NoBuild` | 不重新构建，仅重启 | 关闭（默认构建） |

> 兼容旧的位置写法：`./start-sit.ps1 full backend`、`./start-sit.ps1 core`。

---

## 4. 停服 / 清理

```powershell
./stop-sit.ps1                  # 停止并移除容器（保留数据卷）
./stop-sit.ps1 -RemoveVolumes   # 连数据卷一起删（清空 MySQL/Redis 数据）
./stop-sit.ps1 -RemoveImages    # 顺带删除本项目构建的镜像
```

### 停服脚本参数

| 参数 | 说明 |
|------|------|
| `-RemoveVolumes` | 同时删除数据卷（**会清空数据库数据**） |
| `-RemoveImages` | 同时删除本项目构建的镜像（`--rmi local`） |

---

## 5. 生产环境（prod）安全保护

`start-prod.ps1` 在部署前会自动：

1. 检查 `.env.prod` 是否存在；
2. 扫描残留占位符 `CHANGE_ME`，发现则列出行号并**拒绝部署**；
3. 通过后需手动输入 `yes` 才继续。

`stop-prod.ps1` 停服前需输入 `yes`；带 `-RemoveVolumes` 删除生产数据卷时，需再输入 `DELETE` 二次确认。

---

## 6. 常用辅助命令

```powershell
# 查看容器状态
docker compose --env-file .env.sit -f docker-compose.yml ps

# 跟踪某服务日志
docker compose --env-file .env.sit -f docker-compose.yml logs -f backend

# 等价的原生命令（脚本即对其封装）
docker compose --env-file .env.sit -f docker-compose.yml --profile full up -d --build
```

---

## 7. 默认端口（可在 `.env.<env>` 调整）

| 服务 | 变量 | 默认 |
|------|------|------|
| 网关 | `GATEWAY_PORT` | `0.0.0.0:8060` |
| 前端 | `FRONTEND_PORT` | `0.0.0.0:3090` |
| MySQL | `MYSQL_PORT` | `127.0.0.1:3307`（仅本机） |
| Redis | `REDIS_PORT` | `127.0.0.1:6380`（仅本机） |

> 更详细的部署背景见 `DEPLOY.md` / `DEPLOY_GUIDE.md`。
