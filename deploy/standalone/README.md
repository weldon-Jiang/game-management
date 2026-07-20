# Bend Platform 总控/分控/Agent 改造总结与打包指南

本文档总结把原"单公网 SaaS 平台"改造为"总控 + 局域网分控 + Agent"三层架构的全部工作,以及三种安装包的打包流程和 Agent 与分控的对接。

> **本地开发验证**(不打包、跑源码同机三端)见 [local-dev-verify.md](local-dev-verify.md)。

---

## 一、目标架构

```
┌──────────────── 公网 ────────────────┐
│         总控平台(Master)               │
│  backend + gateway + web + MySQL + Redis │
│  职责: 商户入驻 / License签发 / 监控大盘  │
└──────────────────┬───────────────────┘
                   │ 分控主动出站
        ┌──────────┴──────────┐
        │ (1) license 校验     │ (2) 指标上报
        ▼                     ▼
┌──────── 局域网(每商户一套)─────────┐
│       分控平台(Tenant)                │  仅局域网可访问,公网入站被挡
│  backend(tenant) + gateway + web      │
│  + MySQL green(无 Redis)              │
│  + UDP广播发现服务(端口47820)          │
└──────────────────┬───────────────────┘
                   │ Agent 局域网内连分控(UDP 自动发现IP)
        ┌──────────┴──────────┐
        ▼                     ▼
   Agent 1   Agent 2 ...   Agent N   (同局域网,可装在分控同机)
```

关键网络方向:**分控 → 总控**(出站,做 license 校验+指标上报);**Agent → 分控**(局域网内)。总控无法主动连分控(分控在局域网),所有监控数据靠分控主动出站上报。

---

## 二、改造内容(P1-P9)

| 编号 | 内容 | 关键文件 |
|---|---|---|
| P1 | 总控 License 体系:表/实体/Mapper/Service/Controller,签发+吊销+续期+校验 | `db/migration/V20260716_001_create_merchant_license.sql`、`entity/MerchantLicense.java`、`service/LicenseService.java`、`controller/LicenseController.java`、`util/LicenseSignUtil.java` |
| P2 | 分控 License 校验:启动校验+每30min定时+离线宽限+失效拦截 | `service/LicenseClientService.java`、`config/LicenseClientCondition.java`、`config/LicenseGateFilter.java`、`scheduler/LicenseVerifyScheduler.java`、`controller/LicenseStatusController.java` |
| P3 | 总控/分控功能开关:`license.mode` + `MasterModeCondition` + tenant profile | `config/MasterModeCondition.java`、`application-tenant.yml`、三个总控专属 Controller 加 `@Conditional` |
| P4 | 去 Redis:分控排除 Redis 自动配置,全部走本地 fallback(Caffeine/ConcurrentHashMap) | `application-tenant.yml`(排除RedisAutoConfiguration)、`service/CredentialTokenService.java`(本地令牌)、`gateway/RateLimitFilter.java`(可选注入)、`config/RedisMessageSubscriber.java`(加条件) |
| P5 | Agent 激活改向本地分控:打包预填 backend_url + 预置 registration_code 自动激活 | `bend-agent/src/agent/core/config.py`(加 registration_code 字段)、`bend-agent/src/main.py`(自动激活) |
| P6 | Inno Setup 三种安装包 + 打包编排脚本 | `deploy/standalone/master/master.iss`、`deploy/standalone/tenant/tenant.iss`、`deploy/standalone/agent/agent.iss`、`deploy/standalone/build-*.ps1` |
| P7 | UDP 广播发现:分控广播 + Agent 自动发现IP + 安装时单分控检测 | `config/TenantBroadcastService.java`、`bend-agent/src/agent/core/tenant_discovery.py`、`deploy/standalone/tenant/detect-tenant.ps1` |
| P8 | 总控监控:分控定时上报汇总指标,总控存 tenant_metrics 做大盘 | `db/migration/V20260716_002_create_tenant_metrics.sql`、`entity/TenantMetrics.java`、`controller/TenantMetricsController.java`、`service/impl/TenantMetricsReporter.java`、`scheduler/TenantMetricsScheduler.java` |
| P9 | 日志:logback 写文件 + nssm 重定向 stdout/stderr + 查看日志快捷方式 | `bend-platform/.../logback-spring.xml`、`bend-gateway/.../logback-spring.xml`、`deploy/standalone/*/view-logs.bat`、.iss 中 nssm AppStdout 设置 |

### 关键设计决策

1. **License 校验**:分控启动 + 每30min 向总控 `/api/licenses/verify` 出站校验,结果带 HMAC-SHA256 签名缓存本地;总控不可达时按上次签名时间起算离线宽限(默认24h)。失效后 `LicenseGateFilter` 拦截"启动串流/任务"等写操作返回403。
2. **机器绑定**:license 首次校验时绑定机器指纹(MAC+主机名+OS的SHA256),换机器则校验失败,防止分控包被拷给多家用。
3. **去 Redis**:分控单实例,所有原 Redis 用点(限流/幂等/缓存/租约/断线宽限/负载计数)已有本地 ConcurrentHashMap fallback;只需排除 Redis 自动配置让其走 fallback。`CredentialTokenService` 改为本地令牌(原代码 Redis 不可用会503拦截启动任务,已修)。
4. **UDP 发现**:分控每5秒广播 `BENDTENANT|ip|8060|...`;Agent 启动若 base_url 为占位则监听8秒自动获取;新分控安装前监听6秒,若已有分控广播则阻止安装(同局域网单分控)。
5. **同机安装**:分控服务名 `BendTenant*`(端口8060/8061/3306),Agent 服务名 `BendAgent`(不监听入站),目录/端口隔离,可同机共存,Agent 用 `127.0.0.1:8060` 连本机分控。
6. **安装选路径**:Inno Setup 默认保留目录选择页,用户可改,服务/配置/日志路径都跟随 `{app}`。

---

## 三、三种打包流程

### 前置准备(一次性,放入 `deploy/standalone/staging/base/`)

```
base/
├── jre/        JRE 21 green
├── mysql/      MySQL 8.x green(zip解压版,含 my.ini,端口3306)
├── redis/      Redis Windows green(仅总控需要)
├── nginx/      nginx green(承载前端静态资源,含 nginx.conf)
└── nssm.exe    Windows 服务托管
```

Agent 额外准备 `deploy/standalone/agent/staging/agent/`:
```
chromium/         Playwright Chromium 目录(从 %LOCALAPPDATA%\ms-playwright\ 复制,离线)
vc_redist.x64.exe VC++ 2015-2022 x64 运行库
nssm.exe
```

### 1. 打总控包(公网部署,一次)

```powershell
powershell -ExecutionPolicy Bypass -File packaging\build-master-package.ps1
# 产物: packaging\master\Output\BendPlatformMasterSetup.exe
```

在公网服务器双击安装:自动装 MySQL+Redis+nginx+gateway+backend(master profile),启动服务。安装后登录总控后台,创建商户、签发 License。

### 2. 打分控包（通用包，打一次）

```powershell
powershell -ExecutionPolicy Bypass -File deploy\standalone\tenant\build-tenant-package.ps1
# 产物: deploy\standalone\tenant\Output\BendPlatformTenantSetup.exe
```

分控包是**通用安装包**，不含 License 和商户数据。打包脚本自动：构建 backend/gateway/web → 组装 green 资源 + 激活脚本 → 调 ISCC 编译。

商户安装时输入**激活码**，安装器向总控实时签发 License 并拉取该商户数据。

商户在局域网机器双击安装:
- **安装前**:detect-tenant.ps1 监听6秒,若已有分控广播则阻止(同局域网单分控)
- 安装:初始化本地 MySQL green → 导入 schema + 商户数据 → 注册 BendTenant* 服务(tenant profile)→ 启动
- 启动后:向总控校验 license(online)→ 每30min 复核 → 每5min 上报指标 → 开始 UDP 广播供 Agent 发现

### 3. 打 Agent 包（通用包，打一次）

```powershell
powershell -ExecutionPolicy Bypass -File deploy\standalone\agent\build-agent-package.ps1
# 产物: deploy\standalone\agent\Output\BendAgentSetup.exe
```

Agent 包是**通用安装包**，不含分控地址。Agent 启动后通过 UDP 47820 自动发现局域网分控。

Agent 机器双击安装:
- 静默装 VC++ redist → 配置 `PLAYWRIGHT_BROWSERS_PATH` 指向内嵌 Chromium → 注册 BendAgent 自启动服务 → 启动
- 启动时若 base_url 为占位(未预填),监听 UDP 47820 自动发现局域网分控 IP 并回写 agent.yaml
- 首次用预置注册码自动向**本地分控**激活,拿 agentId/secret → 连分控 WS 开始工作(全程不连总控)

> 注:若 Agent 装在与分控同一台机器,`TenantBaseUrl` 传 `http://127.0.0.1:8060` 即可。

---

## 四、Agent 安装与分控对接(端到端)

1. **总控** 签发 License + 创建商户用户(分控后台登录用) + 在分控后台预生成 Agent 注册码
2. **打分控包** → 商户在局域网机器 A 双击安装 → 分控启动,向总控校验 License(online),开始 UDP 广播
3. 分控后台登录,生成本地 Agent 注册码(分控本地,不经总控)
4. **打 Agent 包** 时填入机器 A 的局域网 IP + 该注册码(或留空占位让 Agent 自动发现)
5. Agent 机器 B(与 A 同局域网,或就是 A)双击安装 → 首启动自动发现分控(若未预填)→ 用预置注册码向**机器 A 的分控**激活 → 连分控 WS 工作
6. 分控每30min 向总控校验 License;失效则 LicenseGateFilter 拒绝新任务;总控不可达进入离线宽限(24h)
7. 分控每5min 向总控上报汇总指标,总控后台监控大盘可见各分控在线Agent数/今日任务/余额/License状态

---

## 五、运行日志位置与查看

| 服务 | 日志位置 | 内容 |
|---|---|---|
| 分控 backend | `{安装目录}\logs\bend-platform.log` | 主日志(logback,按天+50MB滚动) |
| 分控 backend | `{安装目录}\logs\bend-platform-error.log` | 仅 ERROR 级别 |
| 分控 backend | `{安装目录}\logs\backend-stdout.log` | nssm 重定向的 stdout/stderr |
| 分控 gateway | `{安装目录}\logs\bend-gateway.log` | gateway 主日志 |
| 分控 gateway | `{安装目录}\logs\gateway-stdout.log` | nssm 重定向的 stdout/stderr |
| Agent | `{安装目录}\logs\` | Agent 自身日志 + service_stdout/stderr.log |

查看方式:开始菜单 → 程序组 → "查看运行日志"(打开 logs 目录),或直接进 `{安装目录}\logs\`。

---

## 六、实现说明(已落地,无占位)

- **商户数据导出**:总控 `GET /api/merchants/{id}/export-data`(纯 JDBC 生成 INSERT IGNORE SQL,不依赖 mysqldump),打包脚本调此接口下载为 `merchant_data.sql`。导出范围为该商户私有数据(merchant/merchant_user/merchant_balance/subscription/activation_code/streaming_account/game_account/xbox_host/agent_instance/task 等共 22 张表);全局配置(merchant_group/agent_version)不导出,分控用 schema.sql 自带初始值。
- **指标采集**:分控 `TenantMetricsReporter` 用 JdbcTemplate 查本地库真实数据上报(今日任务数、执行中任务、今日消费点数、余额、在线/总Agent数),总控大盘 `GET /api/tenant-metrics` 可见真实数据。
- **安装器命令**:总控/分控建库+导schema 用 `{cmd} /c mysql.exe ... < schema.sql`;Agent 设 PLAYWRIGHT_BROWSERS_PATH 用系统自带 `{sys}\setx.exe /M`,均无自定义小工具依赖。
- **绿色资源**(JRE/MySQL/Redis/nginx/Chromium)体积大不入 git,由打包者放入 `deploy/standalone/staging/base/`(Agent 包另需 chromium/、vc_redist.x64.exe)。

## 七、最简操作流程(两条命令打两包,发给商户的就是分控包 + Agent 包)

```powershell
# 前置(一次性): 把 green 基础资源放入 deploy/standalone/staging/base/(jre/mysql/redis/nginx/nssm.exe)
#                 Agent 额外把 chromium/、vc_redist.x64.exe 放 deploy/standalone/staging/agent/

# 三条命令，打三个通用包（各打一次即可）
powershell -File deploy\standalone\master\build-master-package.ps1   # 总控
powershell -File deploy\standalone\tenant\build-tenant-package.ps1   # 分控（通用包）
powershell -File deploy\standalone\agent\build-agent-package.ps1     # Agent（通用包）
```

> 发给商户的就是两个包：**BendPlatformTenantSetup.exe**（分控）+ **BendAgentSetup.exe**（Agent）。

### 商户安装体验(和装普通 app 一样)

**装分控**(局域网机器 A,先装):
1. 双击 BendPlatformTenantSetup.exe → 选路径 → 安装
2. 安装器自动装本地 MySQL + nginx + gateway + backend(tenant profile),导入商户数据,启动服务
3. 分控启动:向总控校验 license(online)+ 开始 UDP 广播 + 定时上报指标
4. 安装完成勾选"立即打开分控平台" → 浏览器自动打开 `http://localhost:8090`
5. 桌面有 **BendPlatform分控** 快捷方式,双击即用浏览器打开
6. 首次登录用总控创建的商户用户名/密码

**装 Agent**(Agent 机器 B,与 A 同局域网,后装):
1. 双击 BendAgentSetup.exe → 选路径 → 安装
2. **安装前自动检测**:若局域网没发现分控运行 → 安装中止,提示"请先安装分控平台服务"
3. 静默装 VC++ redist + 配置内嵌 Chromium + 注册 BendAgent 自启动服务 + 启动
4. Agent 首次启动:UDP 发现分控 IP(自动,无需手填)→ 免注册码自动向分控注册拿到 agentId/secret → 连分控 WS 开始干活
5. 全程无需注册码、无需手填分控地址

### 端口约定
- 分控前端(nginx):**8090**(浏览器访问地址)。nginx.conf 需 `listen 8090` 并 root 指向前端静态资源、`/api` `/ws` 反代到 gateway:8060。
- 分控 gateway:8060(内部),backend:8061(内部),MySQL:3306(本地)。
- Agent 不监听入站端口,只出站连分控 8060。
- UDP 发现端口:47820(分控广播,Agent/安装器监听)。

### 同局域网其他电脑访问分控
分控装在一台机器上,同局域网其他电脑也能访问分控后台,三前提缺一不可(均已自动处理):
1. **nginx 监听 0.0.0.0:8090**(分控专用 nginx.conf 已配置,非 127.0.0.1,其他电脑可连)
2. **Windows 防火墙放行 8090**(分控安装时自动加 `BendTenant-Web` 入站规则,卸载自动删)
3. **同局域网**

访问地址:
- **本机**:`http://localhost:8090`
- **同局域网其他电脑**:`http://分控机器的局域网IP:8090`(如 `http://192.168.1.10:8090`)
- 桌面快捷方式用**本机局域网IP**打开浏览器,地址栏直接显示局域网地址,商户复制给其他电脑即可;也可浏览器存为书签。
- 建议分控机器配静态 IP 或 DHCP 保留(MAC 绑 IP),避免 IP 变动导致书签失效;即使变动,Agent 也能自动跟上(见下)。

### 总控监控(问题1/2 落地)
- **分控在线**:总控 `GET /api/tenant-metrics/status` 返回各分控在线状态——基于分控最近出站活动(license校验每30min + 指标上报每5min)判断,超过15min无活动判离线(阈值可配 `LICENSE_ONLINE_THRESHOLD_MINUTES`)。总控无法主动连分控,故靠分控出站活动时间戳。
- **Agent 自动注册**:`POST /api/agents/auto-register`(仅分控,Agent 发现分控后调),分控从本地 license 缓存取 merchantId 创建实例,免注册码。开关 `AGENT_AUTO_REGISTER_ENABLED`(默认开)。
