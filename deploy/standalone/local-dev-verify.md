# 本地开发验证（docker 方案 + 踩坑记录）

本地一台机器验证总控/分控/Agent 三层架构。**总控 + 分控都用 docker（启停方便），Agent 本地 python**。

> 最后更新：2026-07-17，验证通过。后续若再踩坑，更新本文件。

## 方案

| 端 | 方式 | 端口 |
|---|---|---|
| 总控 | docker compose（现有 `docker/docker-compose.yml` profile full） | gateway 8060 / backend 8061 / web 3090 / mysql 3307 / redis 6380 |
| 分控 | docker compose（`deploy/standalone/local-tenant-compose.yml`，复用总控镜像，tenant profile） | 8071 |
| Agent | 本地 venv（`bend-agent/venv`，最小依赖 aiohttp+websockets） | 直连 localhost:8071 |

## 日常启停（最常用）

```bash
# 总控
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile full up -d
docker compose -f docker/docker-compose.yml down

# 分控
docker compose --env-file docker/.env -f deploy/standalone/local-tenant-compose.yml up -d
docker compose -f deploy/standalone/local-tenant-compose.yml down

# Agent 验证（mini 脚本,只验证 auto-register+WS）
PYTHONUTF8=1 bend-agent/venv/Scripts/python.exe bend-agent/mini_verify.py

# 看日志
docker logs -f bend-xbox-backend       # 总控
docker logs -f bend-tenant-backend     # 分控
```

## 当前就绪状态（本次已准备，无需重复）

- ✅ 总控镜像 `bend-xbox-backend:latest` 已重建（含最新 License 代码）
- ✅ 分控库 `bend_platform_tenant` 已建（schema + merchant_group + admin）
- ✅ 总控库已导 migration（merchant_license / tenant_metrics / license_verify_cache）
- ✅ License 已造：`LIC-localtest-01` / `localsecrettest01xyz`（active，2027-07-16 到期）
- ✅ Agent venv 已建，aiohttp+websockets 已装
- ✅ agent.yaml `base_url=http://localhost:8071`（直连分控，本地跳过 UDP 发现）

## 一次性准备（重置/换机器时才做）

### 1. 重建总控镜像（改了 Java 代码后）
```bash
docker compose --env-file docker/.env -f docker/docker-compose.yml --profile full up -d --build --no-deps backend
```

### 2. 建分控库 + 导 schema（关键：sed 替换库名前缀 + 过滤 USE）
```bash
docker exec bend-xbox-mysql sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" -e "DROP DATABASE IF EXISTS bend_platform_tenant; CREATE DATABASE bend_platform_tenant DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"'
sed 's/bend_platform\./bend_platform_tenant./g' bend-platform/db/schema.sql | grep -vE "^(CREATE DATABASE|USE) " | docker exec -i bend-xbox-mysql sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" bend_platform_tenant'
```

### 3. 导总控 migration（merchant_license / tenant_metrics）
```bash
docker exec -i bend-xbox-mysql sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" bend_platform' < bend-platform/db/migration/V20260716_001_create_merchant_license.sql
docker exec -i bend-xbox-mysql sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" bend_platform' < bend-platform/db/migration/V20260716_002_create_tenant_metrics.sql
```

### 4. 造 License（绕过 admin 登录，直接 INSERT + sha256 哈希）
```bash
LICENSE_KEY=LIC-localtest-01
LICENSE_SECRET=localsecrettest01xyz
HASH=$(echo -n "$LICENSE_SECRET" | sha256sum | awk '{print $1}')
cat > insert_license.sql <<EOF
INSERT INTO merchant_license (id, merchant_id, license_key, license_secret, status, expire_at, max_agents, max_tasks, offline_grace_hours, created_time, updated_time, deleted)
VALUES (UUID(), 'f5d927c40f87f57ef0f4a484d8a823e9', '$LICENSE_KEY', '$HASH', 'active', '2027-07-16 00:00:00', 5, 50, 24, NOW(), NOW(), 0);
EOF
docker exec -i bend-xbox-mysql sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" bend_platform' < insert_license.sql
```

### 5. 起分控 + 清机器绑定（容器指纹与宿主不同，首次需清绑定重绑）
```bash
docker compose --env-file docker/.env -f deploy/standalone/local-tenant-compose.yml up -d
# 清总控绑定，让分控容器重新绑自己的指纹
docker exec bend-xbox-mysql sh -c 'mysql -u root -p"$MYSQL_ROOT_PASSWORD" bend_platform -e "UPDATE merchant_license SET bound_machine_fingerprint=NULL, activated_at=NULL WHERE license_key=\"LIC-localtest-01\";"'
docker restart bend-tenant-backend
```

### 6. Agent 最小依赖（绕过 greenlet 编译问题）
```bash
cd bend-agent
python -m venv venv
venv/Scripts/python.exe -m pip install aiohttp websockets   # 只装链路验证必需，不装 paddleocr/opencv/greenlet
# agent.yaml base_url 改 http://localhost:8071（直连分控）
```

## 踩坑记录（必看，避免重复踩）

| # | 坑 | 现象 | 解决 |
|---|---|---|---|
| 1 | 总控旧镜像无新代码 | `/api/licenses` 返回 404 或行为异常 | `docker compose up -d --build backend` 重建镜像 |
| 2 | schema.sql `USE bend_platform;` 切回总控库 | 导分控库报 `Duplicate entry group_vip0`，分控库表数 0 | 导前 `sed 's/bend_platform\./bend_platform_tenant./g'` + `grep -v USE/CREATE DATABASE` |
| 3 | INSERT 带 `bend_platform.` 库名前缀 | 数据插进总控库，分控库空 | 同上 sed 替换前缀 |
| 4 | bat 文件 UTF-8 + 中文 | cmd 按 GBK 读 bat，`set` 变量名被截断（`SE_MODE`），mvn 报 `No plugin found` | bat 改纯英文；或直接用 docker compose 不用 bat |
| 5 | requirements.txt UTF-8 | pip 22 按 GBK 读报 `UnicodeDecodeError`，依赖没装 | `set PYTHONUTF8=1`（或跑时 `PYTHONUTF8=1 python ...`） |
| 6 | greenlet 编译失败 | `Microsoft Visual C++ 14.0 required`，整个 pip install 失败 | 验证链路只装 `aiohttp websockets`；全量 Agent 需装 MSVC Build Tools |
| 7 | 分控本地 mvn → docker 指纹变 | license 校验 `MACHINE_FINGERPRINT_MISMATCH` | 清总控 `bound_machine_fingerprint` 重绑（本地验证特有，生产每分控独立机器无此问题） |
| 8 | 分控连总控 | 容器内 localhost 指容器自身 | 用 `host.docker.internal:8060`（compose 已配 extra_hosts） |
| 9 | Agent UDP 发现跨 docker | 分控容器广播不到宿主 | 本地 Agent 直连 `localhost:8071`（跳过 UDP 发现，生产才用） |
| 10 | admin 密码 AES 加密不知明文 | 登录不了总控签 License | 绕过：直接 INSERT merchant_license + 用 verify 公开接口测 |

## 验证结果（本次）

- 总控 verify 接口 `valid=true` + 签名 ✅
- 分控 license 校验 `valid=1` 缓存 + 容器指纹绑定 ✅
- 分控 UDP 广播在跑 ✅
- 分控每 5min 上报总控 tenant_metrics（`license_status=ONLINE`）✅
- Agent auto-register `code=200` + WS `{"type":"connected"}` ✅
- 分控库 agent_instance 有 Agent 记录 ✅

## 遗留（不影响链路验证）

- **全量 Agent 依赖**（paddleocr/opencv/greenlet）需 MSVC Build Tools 才能编译。验证 auto-register+WS 不需要它们。真跑完整自动化任务再装 MSVC 或用预编译 wheel。
- `agent_instance.status=reconnecting` 是 mini_verify 脚本非长驻（WS 连上后退出），正常；真实 Agent 长驻会保持 online。
