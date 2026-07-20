# BendPlatform 总控安装包

总控平台部署在**公网**，负责商户入驻、License 签发/吊销/到期管理、分控在线监控。一个总控管多个商户/分控。

安装包：`BendPlatformMasterSetup.exe`（由 `deploy/standalone/build-master-package.ps1` 产出）。

---

## 安装

1. 把 `BendPlatformMasterSetup.exe` 拷到公网 Windows 服务器（需固定公网 IP/域名）。
2. 双击运行 → 选择安装路径（默认 `C:\BendPlatformMaster`，避免中文/空格）→ 下一步。
3. 安装器自动完成：
   - 解压 JRE / backend / gateway / web / nginx / MySQL / Redis / nssm
   - 初始化 MySQL green（`--initialize-insecure`）+ 注册服务 `BendPlatformMySQL`
   - 建库 `bend_platform` + 导入 `schema.sql`
   - 注册 Redis 服务 `BendPlatformRedis`
   - 用 nssm 注册并启动 `BendPlatformNginx` / `BendPlatformGateway` / `BendPlatformBackend`（均 `--spring.profiles.active=master`）
4. 安装完成。

> 安装需管理员权限（注册 Windows 服务 + 防火墙）。

## 访问

- 前端：`http://公网IP或域名:8090`（nginx 承载）
- 网关 API/WS：`http://公网:8060`
- 健康检查：`http://公网:8060/actuator/health`（应返回 UP）
- 默认管理员：用户名 `admin` / 密码见 `schema.sql` 初始化数据（**首次登录后立即修改**）

## 服务列表（Windows 服务）

| 服务名 | 说明 | 端口 |
|---|---|---|
| BendPlatformMySQL | 数据库 | 3306 |
| BendPlatformRedis | 缓存/限流/幂等 | 6379 |
| BendPlatformNginx | 前端静态资源 + 反代 | 8090 |
| BendPlatformGateway | API 网关（master） | 8060 |
| BendPlatformBackend | 后端（master） | 8061 |

管理：`services.msc` 或 `net stop/start BendPlatformBackend`。

## 运行日志

全部在**安装目录下 `logs/`**：

| 文件 | 内容 |
|---|---|
| `bend-platform.log` | 后端主日志（按天+50MB 滚动，保留14天） |
| `bend-platform-error.log` | 后端 ERROR 级别（保留30天） |
| `backend-stdout.log` | nssm 重定向的后端 stdout/stderr |
| `bend-gateway.log` | 网关主日志 |
| `gateway-stdout.log` | 网关 stdout/stderr |
| nginx 日志 | `nginx/logs/`（access.log / error.log） |
| MySQL 日志 | `mysql/data/*.err` |

查看：进 `安装目录\logs\` 用记事本打开，或用 `Get-Content -Wait bend-platform.log` 实时跟踪。

## 安装后的运维操作

1. **登录总控后台** → 创建商户 → 为商户签发 License（`POST /api/licenses`，打包分控包时由 `build-tenant-package.ps1` 自动调）。
2. **监控大盘**：后台或 `GET /api/tenant-metrics/status` 查看各分控在线状态、在线 Agent 数、今日任务、License 状态。
3. **License 管理**：吊销 `PUT /api/licenses/{id}/revoke`、续期 `PUT /api/licenses/{id}/renew`。
4. **Agent 版本**：`agent_version` 表管理，分控会拉取版本清单下发给 Agent（分控代理升级）。

## 卸载

控制面板卸载，或运行安装目录下卸载程序。卸载会停止并移除所有 `BendPlatform*` 服务、Redis、MySQL 服务。**MySQL data 目录会被清空**，卸载前请备份。

## 常见问题

- **端口被占**：8090/8060/8061/3306/6379 任一被占则对应服务启动失败，改 `application.yml`/`my.ini`/`nginx.conf` 端口。
- **公网访问不到**：检查云服务器安全组放行 8090/8060；Windows 防火墙。
- **backend 启动失败**：看 `logs/backend-stdout.log`，常见是 DB 连不上（MySQL 服务没起）或 JWT_SECRET/AES_SECRET 未配。

## 前置打包资源（打包者看）

`deploy/standalone/staging/base/` 下需备好：`jre/`(JRE21) · `mysql/`(MySQL8 green+my.ini) · `redis/`(Redis Windows green) · `nginx/`(nginx green) · `nssm.exe`。schema.sql 由打包脚本自动放入。详见 [AGENTS.md 生产打包规则](../../AGENTS.md)。
