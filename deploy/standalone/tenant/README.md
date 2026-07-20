# BendPlatform 分控安装包

分控平台部署在**商户局域网**内的一台机器，承载该商户的全部业务（Agent/账号/主机/任务），仅同局域网可访问。每个商户一套，同局域网只能装一个。

安装包：`BendPlatformTenantSetup.exe`（由 `deploy/standalone/build-tenant-package.ps1` 产出，已内嵌该商户的 License + 商户数据）。

---

## 安装（先于 Agent 安装）

1. 把 `BendPlatformTenantSetup.exe` 拷到商户局域网内一台 Windows 机器（建议配静态 IP 或 DHCP 保留）。
2. 双击运行 → 选择安装路径（默认 `C:\BendPlatformTenant`）→ 下一步。
3. **安装前自动检测**：若同局域网已有分控运行 → 中止安装，提示"一个局域网只能装一个分控"。
4. 安装器自动完成：
   - 解压 JRE / backend / gateway / web / nginx / MySQL green / nssm
   - 初始化本地 MySQL green + 建库 + 导入 `schema.sql` + 导入**该商户数据**（`merchant_data.sql`）
   - 写入 `tenant.env`（含内嵌 License、总控地址、DB 配置）
   - 防火墙放行 8090/8060（`netsh advfirewall`）
   - 用 nssm 注册并启动 `BendTenantNginx` / `BendTenantGateway` / `BendTenantBackend`（`--spring.profiles.active=tenant`，读 `tenant.env`）
5. 分控启动：向总控校验 License（online）→ 每 30min 复核 → 每 5min 上报指标 → 开始 UDP 广播（供 Agent 发现）。
6. 安装完成**弹使用说明**，并默认勾选"立即打开分控平台"。

> 安装需管理员权限。**分控不连 Redis**（tenant profile 排除 RedisAutoConfiguration，全部走本地 fallback）。

## 访问

- **本机**：双击桌面 **BendPlatform分控** 快捷方式，或浏览器 `http://localhost:8090`
- **同局域网其他电脑**：`http://分控机器的局域网IP:8090`（如 `http://192.168.1.10:8090`）
  - 桌面快捷方式用**本机局域网 IP** 打开浏览器，地址栏直接显示局域网地址，复制给其他电脑即可
  - 可在浏览器存为书签
- **首次登录**：用总控分配的商户用户名/密码

> 三前提（已自动处理）：nginx 监听 0.0.0.0:8090、防火墙放行 8090、同局域网。

## 服务列表（Windows 服务）

| 服务名 | 说明 | 端口 |
|---|---|---|
| BendTenantMySQL | 本地数据库 | 3306 |
| BendTenantNginx | 前端 + 反代 | 8090 |
| BendTenantGateway | 网关（tenant） | 8060 |
| BendTenantBackend | 后端（tenant，读 tenant.env） | 8061 |

管理：`services.msc` 或 `net stop/start BendTenantBackend`。开机自启。

## 运行日志

全部在**安装目录下 `logs/`**：

| 文件 | 内容 |
|---|---|
| `bend-platform.log` | 后端主日志（含 License 校验 `valid=true`、指标上报记录） |
| `bend-platform-error.log` | 后端 ERROR |
| `backend-stdout.log` | nssm 重定向的后端 stdout/stderr |
| `bend-gateway.log` | 网关日志 |
| `gateway-stdout.log` | 网关 stdout/stderr |
| nginx 日志 | `nginx/logs/` |
| MySQL 日志 | `mysql/data/*.err` |

查看：开始菜单 → BendPlatform分控 → **查看运行日志**（打开 logs 目录），或 `Get-Content -Wait bend-platform.log` 实时跟踪。

## 安装后的使用

1. 登录分控后台（浏览器访问上述地址）。
2. 管理流媒体账号 / 游戏账号 / Xbox 主机 / 任务（数据已从总控导入，本地操作）。
3. **装 Agent**：在同局域网（或本机）的 Agent 机器双击 `BendAgentSetup.exe`，Agent 自动发现本分控并注册。详见 [Agent 安装说明](../agent/README.md)。
4. 分控每 30min 向总控复核 License：失效则 `LicenseGateFilter` 拒绝启动新串流/任务；总控不可达进入离线宽限（默认 24h）。
5. 总控后台可看本分控的在线状态/今日任务/余额（分控每 5min 上报）。

## License 失效/到期怎么办

- 到期/吊销：分控后台会提示，无法启动新任务（已在跑的任务按策略处理）。联系总控运维续期（`PUT /api/licenses/{id}/renew`）或重新签发。
- 总控网络抖动：24h 内不影响使用（离线宽限，基于上次签名时间）。

## 卸载

控制面板卸载或运行安装目录卸载程序。卸载停止并移除所有 `BendTenant*` 服务 + MySQL 服务，**删除 MySQL data 目录**，卸载前请备份商户数据。

## 常见问题

- **其他电脑访问不到**：确认①分控机器防火墙已放行（安装时自动加 `BendTenant-Web` 规则）②同局域网③用分控机器 IP 而非 localhost。
- **Agent 发现不了分控**：确认分控服务正常运行（`BendTenantBackend` Running）、同局域网、UDP 47820 未被防火墙挡。
- **License 校验失败**：看 `logs/bend-platform.log` 的 `LicenseClientServiceImpl` 日志；确认 `tenant.env` 的 `LICENSE_KEY/SECRET/MASTER_URL` 正确、总控可达。
- **分控机器 IP 变了**：Agent 会自动重新发现（WS 失败重连触发 UDP rediscover）；其他电脑浏览器书签失效，重新输新 IP。

## 前置打包资源（打包者看）

`deploy/standalone/staging/base/` 下需备好：`jre/` · `mysql/` · `nginx/` · `nssm.exe`（分控不需要 redis）。打包脚本自动签 License + 导商户数据 + 生成 tenant.env + 放 nginx.conf。详见 [AGENTS.md 生产打包规则](../../AGENTS.md)。
