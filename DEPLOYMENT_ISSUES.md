# 项目知识库 — 架构 / 修复 / 踩坑

> 总控(公网) + 分控(局域网) + Agent 三层架构。同份 jar 靠 `spring.profiles.active=master|tenant` 切换。

---

## 一、架构概览

```
┌──────────── 公网 ────────────┐
│     总控平台 (Master)          │
│  backend + gateway + web      │
│  + MySQL + Redis              │
│  职责: 商户入驻 / License签发   │
│         / 监控大盘             │
└──────────────┬───────────────┘
               │ 分控主动出站
    ┌──────────┴──────────┐
    │ (1) license 校验     │ (2) 指标上报
    ▼                     ▼
┌─────── 局域网(每商户一套) ──────┐
│     分控平台 (Tenant)           │
│  backend(tenant) + gateway     │
│  + web + MySQL green(无Redis)  │
│  + UDP广播发现(端口47820)       │
└──────────────┬───────────────┘
               │ Agent 局域网连分控
    ┌──────────┴──────────┐
    ▼                     ▼
 Agent 1  ...  Agent N   (UDP自动发现IP)
```

### 核心决策

| 项 | 说明 |
|---|---|
| 网络方向 | 分控→总控(出站)；Agent→分控(局域网)。总控无法主动连分控 |
| License | `merchant_license` 表 HMAC-SHA256 签名；分控启动+每30min校验；离线宽限24h；机器指纹绑定(MAC+主机名+OS) |
| 模式开关 | `license.mode=master/tenant` + `MasterModeCondition`/`LicenseClientCondition` 两个 Condition 控制装配 |
| 去 Redis | 分控排除 RedisAutoConfiguration，本地 ConcurrentHashMap fallback 自动接管 |
| UDP 发现 | 端口 47820，协议 `BENDTENANT\|ip\|port\|licenseKey前缀\|商户名`；分控每5秒广播 |
| Agent 激活 | 免注册码 `POST /api/agents/auto-register`；Agent UDP 发现分控后自动注册 |
| 端口约定 | 分控前端 8090 / gateway 8060 / backend 8061 / MySQL 3306 / UDP 47820 |
| 同机共存 | 分控服务名 `BendTenant*`，Agent `BendAgent`；Agent 用 `127.0.0.1:8060` 连本机分控 |

---

## 二、P0 修复历史 (2026-07-16)

### P0#1 — 后端双控制面死代码清理
- 删除 `TaskService` 接口中 `cancel/pause/resume/stop` 四个零调用者方法
- 删除 `TaskServiceImpl` 中对应实现（~140 行）
- 删除前端 `task.js` 中 `stop` API
- `cancel` 和 `terminate` 在 `TaskControlServiceImpl` 中完全等价（cancel 委托到 terminate）

### P0#2 — 复用任务计费缺口
- `TaskControlServiceImpl.startStreaming()` 移除 `if (!reused)` 守卫
- 每次启动串流都计费，包括任务复用场景

### P0#3 — TaskEvent 写入异常日志升级
- `TaskEventServiceImpl.record()` 中 `log.warn` → `log.error`
- 日志明确标注"事件将丢失"，新增 phase 字段

### P0#4 — 密钥保护加固
- `.gitignore` 新增 `docker/.env.dev/.env.sit/.env.prod` 显式规则
- `docker/.env.dev` 中 7 处真实密钥替换为 `CHANGE_ME_dev_*` 占位符
- **真实密钥曾存在于 git 历史 `b456ec3`，生产环境需轮换**

### P2 — 死字段注入清理
- `ActivationCodeController`：删除 `activationCodeBatchMapper`
- `MerchantSubscriptionController`：删除 `activationCodeBatchMapper` + `ObjectMapper`

### P2 — Controller 直连 Mapper 重构（部分完成）
- `MerchantSubscriptionController` 完成 5 处 Mapper 直调 → Service 层
- 待处理：`ActivationCodeController`、`GameAccountController`、`BillingController`、`MerchantRegistrationCodeController`

---

## 三、部署踩坑 (2026-07-20)

### 3.1 ProGuard 混淆构建失败

**现象**：`mvn package` → `Obfuscation failed (result=1)`
```
java.io.IOException: You have to specify '-keep' options if you want to write out kept elements with '-printseeds'.
```

**根因**：[bend-platform/Dockerfile](bend-platform/Dockerfile) 只复制了 `pom.xml` 和 `src/`，没有复制项目根目录的 `proguard.conf`。

**修复**：Dockerfile 增加 `COPY proguard.conf .`

### 3.2 ProGuard 混淆自定义注解 → Spring AOP 启动失败

**现象**：容器反复重启：
```
error Type referred to is not an annotation type: com$bend$platform$annotation$AuditLog
```

**根因**：[bend-platform/proguard.conf](bend-platform/proguard.conf) 遗漏 `com.bend.platform.annotation` 包。`@AuditLog` 和 `@Idempotent` 被混淆后，AspectJ `@Around("@annotation(...)")` 点切表达式找不到注解类。

**修复**：proguard.conf 增加 `-keep class com.bend.platform.annotation.** { *; }`

### 3.3 分控前端健康检查假死

**现象**：`bend-tenant-frontend` 一直 `unhealthy`，但 nginx 实际正常运行。

**根因**：健康检查用 `wget`，`nginx:alpine` 不含该命令。

**修复**：改用 `curl -f http://localhost/health`

### 3.4 主控前端 CORS 预检 403

**现象**：浏览器 POST `/api/auth/login` → `403 Forbidden`；curl 直接 POST 正常，但 OPTIONS 预检返回 403。

**根因**：`application-prod.yml` 覆盖 CORS 为 `${CORS_ALLOWED_ORIGINS:https://localhost}`，默认 HTTPS 与前端 HTTP 不匹配；Docker Compose 未将 `CORS_ALLOWED_ORIGINS` 传入 Gateway 容器。

**修复**：
1. `docker/.env` 新增 `CORS_ALLOWED_ORIGINS=http://localhost:3090,http://localhost:8090`
2. `docker/docker-compose.yml` Gateway 注入 `CORS_ALLOWED_ORIGINS` 环境变量

---

## 四、分控部署脚本规则

### 首次安装 vs 升级判断

判断依据：`{app}\mysql\data` 目录是否存在。

| 模式 | 条件 | MySQL 初始化 | schema.sql | 激活 (License+数据) | 增量 migration |
|------|------|-------------|-----------|---------------------|---------------|
| **首次安装** | data 目录不存在 | ✅ `--initialize-insecure` | ✅ 全量导入 | ✅ 调 activate-tenant.ps1 | ❌ 跳过 |
| **升级** | data 目录已存在 | ❌ 跳过 | ❌ 跳过 | ❌ 跳过 | ✅ 按字典序执行未应用的 V*.sql |

### 脚本清单

| 脚本 | 路径 | 调用方 | 用途 |
|------|------|--------|------|
| `detect-tenant.ps1` | `deploy/standalone/tenant/` | `tenant.iss` PrepareToInstall | 首次安装前检测同局域网是否已有分控(安装后跳过) |
| `activate-tenant.ps1` | `deploy/standalone/tenant/` | `tenant.iss` [Run] Check:IsFirstInstall | 向总控签发 License + 拉取商户数据 + 回写 tenant.env |
| **`upgrade-tenant.ps1`** | `deploy/standalone/tenant/` | `tenant.iss` [Run] Check:IsUpgrade | 创建 `_migrations` 追踪表 + 执行未应用的 V*.sql |
| `build-tenant-package.ps1` | `deploy/standalone/` | 运维手动 | 构建后端/网关/前端产物 → 组装 staging → 调 ISCC 编译 |

### 数据库迁移规范

1. **全量 schema**：`bend-platform/db/schema.sql` — 始终与最新表结构同步，用于首次安装
2. **增量 migration**：`bend-platform/db/migration/V{YYYYMMDD}_{NNN}_{name}.sql` — 按文件名字典序执行
3. **迁移追踪**：升级脚本在目标库创建 `_migrations` 表，记录已执行的 migration 文件名和执行耗时
4. **同步规则**：每次新增 migration 必须同步更新 `schema.sql` + `MIGRATION_INDEX.md`
5. **幂等要求**：migration 脚本应使用 `IF NOT EXISTS` / `IF EXISTS` 等幂等写法，允许重复执行不报错
6. **字符集**：每个 migration SQL 开头必须声明 `SET NAMES utf8mb4;`

### tenant.iss 关键逻辑

```
PrepareToInstall:
  ├── 升级模式 → 弹确认框 → 用户确认继续/取消
  └── 首次安装 → UDP 检测局域网分控 → 有则阻止

InitializeWizard:
  └── 仅首次安装显示"总控地址"+"激活码"输入页

[Run]:
  ├── Check:IsFirstInstall → MySQL init + schema + activate
  ├── Check:IsUpgrade     → upgrade-tenant.ps1 (增量迁移)
  └── 无条件              → 注册服务 + 防火墙 + 启动

CurStepChanged(ssPostInstall):
  └── 首次显示"已安装" / 升级显示"已升级"
```

### 打包时迁移文件组装

`build-tenant-package.ps1` 负责：
```powershell
# 复制增量 migration SQL 到 staging
New-Item -ItemType Directory -Force -Path "$TenantStagingDir\migration" | Out-Null
Copy-Item bend-platform\db\migration\V*.sql $TenantStagingDir\migration\ -Force
# 复制升级脚本
Copy-Item packaging\tenant\upgrade-tenant.ps1 $TenantStagingDir\upgrade-tenant.ps1 -Force
```

`tenant.iss` [Files] 负责复制到安装目录：
```
Source: "staging\tenant\migration\*.sql"; DestDir: "{app}\mysql\migration"
Source: "upgrade-tenant.ps1"; DestDir: "{app}"
```

---

## 五、重新部署检查清单

- [ ] `bend-platform/Dockerfile` — `COPY proguard.conf .` 是否存在
- [ ] `bend-platform/proguard.conf` — `com.bend.platform.annotation.**` 是否保留
- [ ] `docker/.env` — `CORS_ALLOWED_ORIGINS` 是否指向前端实际地址
- [ ] `docker/docker-compose.yml` — Gateway 是否注入 `CORS_ALLOWED_ORIGINS`
- [ ] 分控前端健康检查 — 是否用 `curl` 而非 `wget`
- [ ] 数据库卷 — down 时不加 `-v`，避免数据重置
- [ ] `license.sign-secret` — 总控分控必须一致
- [ ] 密钥轮换 — 真实密钥曾在 git 历史 `b456ec3`，生产需轮换
- [ ] 分控首次安装 — `tenant.iss` 是否正确检测 `mysql\data` 目录判定首次/升级
- [ ] 分控升级 — `upgrade-tenant.ps1` 是否随包分发，`_migrations` 追踪表是否正常创建
- [ ] 新增 migration — 是否同步更新 `schema.sql` + `MIGRATION_INDEX.md`
- [ ] 本地调试 hack — 提交前确认 `agent.yaml`（8060 非 8071）、`vite.config.js`（3090 非 3091）未夹带

---

## 六、Agent 自动化架构

### 串流栈（当前生产，2026-06-13 勘误）

| 步骤 | 入口文件 | 职责 |
|------|----------|------|
| Step1 | `bend-agent/src/agent/automation/step1_xblive_login.py` | xblive 认证 + GSSV/Xbox Token |
| Step2 | `bend-agent/src/agent/automation/step2_xsrp.py` → `xbox/step2_xsrp_connect.py` | GSSV 云端发现 + play/WebRTC 握手 |
| Step3 | `bend-agent/src/agent/automation/step3_xsrp.py` | WebRTC 帧捕获 + SDL 窗口 + DataChannel 输入 |
| Step4 | `bend-agent/src/agent/automation/step4_game_automation.py` | 游戏自动化（模板匹配+手柄） |

**已废弃/非热路径**：
- `step2_xbox_streaming.py` — **已删除**，由 `step2_xsrp.py` 替代
- `step3_streaming_init.py`（SmartGlass+pygame）— 非生产主路径
- SmartGlass TCP:5050 — 历史方案
- SmartGlass UDP 5050 — **保留**，仅作 LAN 发现/唤醒兜底

**输入通道**：生产用 WebRTC DataChannel → `input/controller_protocol.py`（`ControllerProtocol`）

### 核心并发模型

```
一个串流账号 = 一个任务 = 一个窗口
├── 多账号并发，每个账号独立窗口
├── 每个窗口独立四步骤：登录 → 串流 → 解码 → 自动化
├── 任务互不干扰，一个异常不影响其他
└── 任务状态和异常实时上报平台
```

### CentralManager 架构

```python
CentralManager
├── windows: Dict[str, StreamWindow]  # instance_id → StreamWindow
├── register_to_backend()             # 向分控注册
├── start_streaming_account() -> str  # 返回 instance_id
└── stop_instance()

StreamWindow
├── state: WindowState  # INITIALIZING → READY → CONNECTING → CONNECTED → AUTOMATING
├── frame_capture: VideoFrameCapture  # 视频帧捕获（BGR格式，归一化坐标0-1）
├── template_matcher: TemplateMatcher
└── input_controller: InputController
```

### 场景智能匹配系统

| 场景 | ID 范围 | 匹配策略 |
|------|---------|----------|
| 游戏主菜单 | 100-110 | 纯模板 (<20ms) |
| FUT (Ultimate Team) | 200-234 | 纯模板 |
| 比赛内 | — | 纯模板 |
| 登录 | — | 模板优先 + OCR fallback |
| 菜单/设置/账号 | — | 模板优先 + OCR fallback |
| 通用 | — | 模板优先 + OCR |

**核心匹配器**：`SceneBasedMatcher`（场景匹配器）→ `HybridMatcher`（综合匹配器）→ `OCRTextMatcher`（文字识别）

**模板存储**：`template/{scene_id}.{template_id}.png`，序列化到 `data/templates.dat`（gzip+pickle）

### 手柄操作自动化

```python
class GamepadButton(Enum):  # 16 个按钮
    A=0, B=1, X=2, Y=3, LB=4, RB=5, LT=6, RT=7,
    BACK=8, START=9, L3=10, R3=11,
    DPAD_UP=12, DPAD_DOWN=13, DPAD_LEFT=14, DPAD_RIGHT=15
```

核心操作：`_press_button()`、`_move_stick()`、`_play_game()`（界面检测循环）

---

## 七、业务系统设计

### 点数制系统

| 项 | 说明 |
|---|---|
| 激活码 | 充值点数用，充多少得多少 |
| `merchant_balance.balance` | 商户当前可用点数 |
| `subscription` | 某个服务的订阅（按主机/窗口/号），消耗点数 |
| `merchant.expireTime` | **保留但不再使用**（历史兼容） |

**核心逻辑**：商户状态只根据 `merchant.status` 判断（active=正常），与点数/expireTime 无关。

### 激活码订阅类型（方案B）

| 类型 | 说明 |
|------|------|
| `points` | 充值点数 |
| `account` | 定向游戏账号订阅（目标ID + 时长 + 每日价格） |
| `window` | 定向窗口订阅 |
| `host` | 定向主机订阅 |

### Xbox 主机 MAC 地址增强

- `xbox_host` 表新增 `mac_address VARCHAR(17)`（格式 `AA:BB:CC:DD:EE:FF`）
- MAC 是物理地址，IP 变动后仍能精确匹配
- 创建索引 `idx_xbox_host_mac`

### 前端技术栈

Vue 3 + Composition API + Element Plus + Pinia + Vue Router 4

核心组件：`VideoMonitor.vue`（视频监控）、`LogViewer.vue`（日志查看器）、`RealtimeChart.vue`（ECharts 实时图表）

---

## 八、关键认知

- 架构评审中"TaskEvent 绕过 Service"的结论有误——代码实际走了 Service 层
- P0#1 没有真正的路由冲突——Spring 能区分不同子路径
- `cancel` 和 `terminate` 在 TaskControlServiceImpl 中完全等价
- `docker/.env.example` 虽被全局 `.env.example` 规则匹配，但因已被 git 跟踪而不受影响
- ProGuard 的 `-keepattributes *Annotation*` 只保留注解使用元数据，不保留注解类本身——注解类需单独 `-keep`
- `nginx:alpine` 不含 `wget`，健康检查统一用 `curl`
- Spring Boot `${VAR:default}` 语法中默认值不会自动匹配不同协议/端口——需显式配置
- 生产串流栈为 GSSV 云端 + WebRTC（aiortc），**不是** SmartGlass LAN
- SmartGlass UDP 5050 仅保留用于 LAN 发现/唤醒兜底
- 模板匹配用归一化坐标 (0-1)，处理不同分辨率下的黑边问题

---

## 九、项目清理记录 (2026-07-20)

### P0 安全与卫生
- **密钥脱敏**：`docker/.env` 和 `docker/.env.tenant` 中真实密码替换为 `CHANGE_ME_*` 占位符
- **gitignore 加固**：`docker/.env*` 通配符替换逐个枚举，新增 `.pytest_cache/` 规则
- **缓存清理**：删除 12,320 个 `.pyc` 文件 + 1,870 个 `__pycache__/` 目录 + 2 个 `.pytest_cache/`
- **日志清理**：`bend-agent/logs/` 从 41MB 清理至 0（删除调试截图、历史日志、手动捕获）

### P1 代码卫生
- **文档碎片整理**：删除 `.trae/`（39 个 AI 生成文档）和 `.cursor/`（IDE 规划文件，均已在 gitignore）
- **根目录清理**：删除 7 个一次性 Python 脚本 + 3 个 debug-*.log + `.cursor/debug-*.log`
- **step4 拆分**：提取常量至 `step4/constants.py`，主文件添加 11 个分段标记（1️⃣-1️⃣1️⃣）为后续完整拆分指南
- **分层修复**：`AgentAutoRegisterController` 移除 `LicenseVerifyCacheMapper` 直连，改为走 `LicenseClientService.getCache()`

### P2 持续改进
- **调试脚本归档**：`scripts/debug/`（36 个）→ `scripts/archive/debug/`
- **重复文档清理**：删除 `TEST_OPTIMIZATION_README.md`；`AGENT_AUTOMATION_SUMMARY.md` 添加历史存档标记
- **Compose 文件**：`docker-compose.yml` ↔ `docker-compose-tenant.yml` 添加互引用注释
