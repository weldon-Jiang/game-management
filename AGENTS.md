# Bend Platform - Agent 全局技能文档

**版本** 3.4 · **更新** 2026-06-07 · **范围** 后端 (Spring Boot 3.2.5/Java 17) · 网关 (Spring Cloud Gateway 4.1.x) · 前端 (Vue 3.5/Vite 8) · Agent (Python 3.9/asyncio)

---

## ⚠️ 核心原则（P0）


| 原则       | 说明                             |
| -------- | ------------------------------ |
| 前瞻设计     | 编写代码时考虑未来需求与关联模块影响             |
| 双向适配     | 改后端检查前端，反之亦然                   |
| 部署验证     | 代码改动后必须经 Docker Compose 重新部署验证 |
| 架构红线     | 新增控制接口/自动化入口必须遵循下方「架构红线」       |
| 注释清晰     | 前端、后端、Agent 的接口、方法、字段、步骤与核心逻辑必须写清楚注释 |
| 聚焦验证（P1） | 仅验证改动模块，不做全流程验证                |


---

## 🛑 架构红线（P0，必须遵守）


| #   | 红线               | 必须                                                                              | 禁止                                                                  |
| --- | ---------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| 1   | **任务控制面**        | 新接口加在 `TaskControlController`，发 WS `task_control{action}`                       | 在旧 `TaskController` 新增 pause/resume/stop                            |
| 2   | **自动化入口**        | 走 `/api/streaming-accounts/{id}/tasks/start-streaming` → `start-automation` 两阶段 | 新增 `/api/automation/start` 一步式入口                                    |
| 3   | **TaskEvent 写入** | 经 `TaskEventService.record(...)`（待补）                                            | `AgentCallbackServiceImpl` 直连 Mapper + 静默吞异常                        |
| 4   | **Agent 并发**     | 引擎/切换器挂 `context._xxx`；用 `get_active_scheduler()`                               | 模块级全局；单任务 `finally` 调 `scheduler.close()`；`task_executor.scheduler` |
| 5   | **Git 红线**       | 见 `.gitignore`                                                                  | 提交 `target/` `__pycache__/` `logs/` `tokens/` `docker/.env`*        |


---

## 🚀 快速开始

### Docker Compose（必须带 `--env-file`）

```bash
# 首选：环境脚本（自动注入 --env-file + profile + Prod 占位符校验）
.\docker\start-dev.ps1 / start-sit.ps1 / start-prod.ps1

# 手动命令（务必带 --env-file，否则容器内变量为空）
docker compose --env-file docker/.env.dev -f docker/docker-compose.yml --profile full up -d --build
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f backend
```

**Profile**：


| Profile | mysql | redis | backend | gateway | frontend | 用途           |
| ------- | ----- | ----- | ------- | ------- | -------- | ------------ |
| `data`  | ✅     | ✅     | -       | -       | -        | 仅数据层         |
| `core`  | -     | ✅     | ✅       | ✅       | -        | 后端（外部 mysql） |
| `app`   | -     | -     | ✅       | ✅       | ✅        | 应用层（外部数据）    |
| `full`  | ✅     | ✅     | ✅       | ✅       | ✅        | 完整栈（默认）      |


**端口**：


| 服务       | 容器内  | 主机映射                                        |
| -------- | ---- | ------------------------------------------- |
| Gateway  | 8060 | `0.0.0.0:8060`（唯一对外 API）                    |
| Frontend | 80   | `0.0.0.0:3090`                              |
| Backend  | 8061 | **不暴露**（容器网络内）                              |
| MySQL    | 3306 | `127.0.0.1:3307` (dev/sit) / `:3306` (prod) |
| Redis    | 6379 | `127.0.0.1:6380` (dev/sit) / `:6379` (prod) |


### 部署后检查清单

- [ ] 各服务无 ERROR / Exception（容器名 `bend-xbox-{mysql,redis,backend,gateway,frontend}`）
- [ ] `curl http://localhost:8060/actuator/health` 返回 UP
- [ ] 出错时主动读容器日志分析

### 数据库迁移（**非 Flyway，手动**）

- **全量初始化**：`bend-platform/db/schema.sql` 经 docker volume 挂入 MySQL `/docker-entrypoint-initdb.d/`，**仅首次空卷**自动执行
- **增量**：`bend-platform/db/migration/V{YYYYMMDD}_{NNN}_{snake_case}.sql`，按文件名字典序，**手动**应用

**新增迁移流程**：

1. 在 `bend-platform/db/migration/` 新增 `V20260607_005_xxx.sql`
2. SQL 脚本开头必须与 `schema.sql` 一致声明 `SET NAMES utf8mb4;`、`SET CHARACTER SET utf8mb4;`、`SET collation_connection = 'utf8mb4_unicode_ci';`，避免中文 COMMENT 乱码
3. **同步**更新 `bend-platform/db/schema.sql` + `bend-platform/db/migration/MIGRATION_INDEX.md`
4. 已运行环境：`.\docker\run-migration.ps1`（Windows） 或 `./docker/run-migration.sh <file>`

---

## 📁 项目结构

### 后端 `bend-platform`（234 文件 / 15 子包，端口 8061 容器内）

`controller/` 25 个 REST · `service/` + `service/impl/` 27 接口/实现 + 8 独立 `@Service` · `repository/` 29 `*Mapper`（`@MapperScan`） · `entity/` `dto/` `enums/` `config/` `util/`（`UserContext`/`JwtUtil`/`DataSecurityUtil`/`AesUtil`） · `task/` 4 个 `@Scheduled` · `websocket/` `aspect/`（`AuditLogAspect`/`IdempotentInterceptor`） · `exception/`（`GlobalExceptionHandler` + `BusinessException` + `ResultCode`） · `db/` 全量 + 增量脚本

### 网关 `bend-gateway`（端口 8060 / WebFlux）

- 路由：`/api/`** `/ws/**` `/actuator/**` → `backend:8061`
- 全局过滤器：`IpFilter(-100)` + `RateLimitFilter(-90, Redis)` + `CorsWebFilter`
- 限流：login 5/3、register 3/2、`/api/agents/**` 50/30、默认 100/50
- Actuator：dev/sit `health,info,gateway`；prod 仅 `health,info`

### Agent `bend-agent`（20 子包，Python 3.9 / asyncio）

`automation/` 四步骤（核心） · `api/` HTTP+WS · `auth/` MSAL · `core/` 中央管理/日志/路径 · `discovery/` Xbox 发现 · `game/` 账号切换 · `gssv/` GSSV API · `input/` 手柄/键盘 · `orchestration/` 两阶段编排 · `**runtime/` 并发原语**（task_registry/phase_fsm/input_gate/input_focus/task_control_handler） · `scene/` 场景检测 · `session/` `system/` `task/` 调度执行 · `utils/`（crypto） · `vision/` 模板/解码/捕获 · `window/` `windows/` SDL · `xbox/` SmartGlass/LAN · `xhome_stream/`

配置：`configs/agent.yaml` · `configs/scene_schemas.py` (SCENE_SCHEMAS 100 行 + SCENE_NAMES ID 1-204) · `configs/scene_transitions.py` · `templates/{场景}.{模板}.png`

### 前端 `bend-platform-web`（Vue 3.5 + Vite 8 + Element Plus 2.13 + Pinia 3）

- **纯 JS + 纯 CSS**（无 TS/SCSS），全部 `<script setup>`，**深色单一主题**
- 入口 `main.js`（Pinia + Router + ElementPlus zhCn + 全局错误处理）
- 路由 17 个活跃 + 1 个注释（充值卡）；侧栏 `views/layout/MainLayout.vue`
- Store：仅 `useAuthStore`（含 `isPlatformAdmin/isMerchantOwner/isOperator/hasManagementPermission`）
- HTTP：`utils/request.js`（axios 封装 + 401 刷新 + 防重）；17 个 `api/*.js` 模块
- 样式入口 `styles/index.css`：`variables.css`（设计令牌） + `reset.css`（工具类） + `element-plus.css`（EP 深色覆盖）
- Dev 端口 3090，`/api` 代理 → `:8060`
- 测试：Vitest 单元 + MSW 集成

---

## 🔐 认证与多商户隔离


| 客户端        | 认证方式                                                                                    |
| ---------- | --------------------------------------------------------------------------------------- |
| 前端 Web     | JWT `Authorization: Bearer <token>` → `JwtAuthInterceptor` → `UserContext`（ThreadLocal） |
| Agent HTTP | `X-Agent-Id`（原始） + `X-Agent-Secret`（**Base64**） → `AgentAuthFilter`                     |
| Agent WS   | 握手头 `X-Agent-Secret`（Base64，首选）；URL `?agentSecret=`（原始，legacy 兜底）                       |


```python
# Agent 侧 Base64 编码（违反则 401）
headers['X-Agent-Secret'] = base64.b64encode(agent_secret.encode()).decode()
```

**多商户三层防护**：① Controller 显式传 `UserContext.getMerchantId()` ② `DataSecurityUtil.validateMerchantAccess`（`platform_admin` 绕行） ③ Service 查询按 `merchantId` 过滤 + `requireTask(taskId, merchantId)` 校验  
**角色**：`platform_admin` / `merchant_owner` / `operator`

---

## 🛠️ 开发规范

### 后端（Java / Spring Boot）


| 规则   | 说明                                                                                                                                               |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| 注释   | Controller / Service / Entity / DTO / Mapper 等新增或改动类必须补充类级 Javadoc；后端接口、公共方法、关键私有方法、重要字段、状态字段、复杂业务分支必须写清楚用途、入参约束、状态迁移与异常语义 |
| 命名   | 类 PascalCase；方法/变量 camelCase；避免魔法值（用 `enums/`）                                                                                                   |
| API  | 统一 `ApiResponse<T>` 包装；异常经 `GlobalExceptionHandler` 转 `BusinessException(ResultCode)`                                                            |
| DAO  | MyBatis-Plus `BaseMapper`，避免手写 SQL；`@Transactional(rollbackFor = Exception.class)`                                                               |
| 商户隔离 | 所有商户写操作经 `UserContext.getMerchantId()` 或 `validateMerchantAccess`                                                                                |
| 注入   | `@RequiredArgsConstructor` 的依赖必须 `final`                                                                                                         |


**编译检查清单**：方法重复 / import 完整 / `final` 注入 / 枚举值存在 / `BusinessException(ResultCode)` 构造合法

⚠️ 逻辑删除场景慎用 `@TableLogic`：唯一键资源（如 xbox_host）建议物理删除避免再插冲突

### 前端（Vue3 / JavaScript）


| 规则     | 说明                                                                                                                                             |
| ------ | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| 组件     | PascalCase；`<script setup>` Composition API                                                                                                    |
| 注释     | 复杂函数、核心业务逻辑、关键状态计算、权限/计费/任务控制分支必须补充注释；禁止给简单赋值、显而易见表达式堆砌低价值注释                                                                 |
| API 调用 | 用封装的 `request`（`utils/request.js`），禁直接 axios                                                                                                   |
| 状态     | Pinia                                                                                                                                          |
| 样式     | scoped；**禁硬编码颜色/间距**，统一 `var(--*)` 令牌；表格/弹窗/页头用 `reset.css` 工具类（`.page-container`/`.content-card`/`.toolbar`/`.pagination-wrap`），不在 scoped 内重复 |
| 单文件大小  | **不超过 800 行**；超过必须拆子组件 + composable                                                                                                            |
| 空状态    | 列表/详情必须含 `el-empty`（详情页 `v-else` 兜底）                                                                                                           |
| 菜单     | 侧栏分组标题禁重名                                                                                                                                      |


### Agent（Python）


| 规则     | 说明                                                                                                                |
| ------ | ----------------------------------------------------------------------------------------------------------------- |
| 代码风格   | PEP 8 + type hints                                                                                                |
| 注释     | 自动化 Step1-4 每个步骤、任务状态流转、资源清理、异常保留/失败分支、输入控制、场景识别等核心环节必须写清楚注释；复杂 async 流程需说明等待条件与退出条件 |
| API 调用 | 用 `PlatformApiClient`（`/api/v1/agent-callback/`*）/ `ApiClient`（`/api/*`），禁直接 aiohttp/requests                     |
| 异步     | `async/await` + `asyncio.sleep`（非 `time.sleep`）                                                                   |
| 日志     | 主日志 `logs/agent.log` **JSON**；账号 `logs/stream_log/stream_{name}.log` + `logs/game_log/game_{name}_{date}.log` 纯文本 |
| 认证     | `X-Agent-Secret` 必须 Base64                                                                                        |
| 资源清理顺序 | API 客户端 → WS → **仅停当前任务**（不要 close 全局调度器）→ 释放窗口 + GPU 解码槽                                                         |


#### 自动化四步骤（必须在 `automation/` 目录）


| 步骤  | 文件                              | 主入口                       | 职责                           |
| --- | ------------------------------- | ------------------------- | ---------------------------- |
| 1   | `step1_stream_account_login.py` | `step1_execute_login`     | MSAL 设备码 + Token 自动刷新        |
| 2   | `step2_xbox_streaming.py`       | `step2_execute_streaming` | GSSV∩LAN 发现 + SmartGlass 握手 |
| 3   | `step3_streaming_init.py`       | `step3_streaming_init`    | SDL 窗口 + GPU 解码              |
| 4   | `step4_game_automation.py`      | `step4_execute_gaming`    | 游戏自动化（`task_type` **仅此处生效**） |


**串行规则**：Step1–3 任一失败 → 整个任务失败；Step4 失败 → **保留串流/窗口**，会话进入 `automation_failed`，用户可再次选择模式重试（不关串流、不关窗口）。

**Step1–3（串流准备）vs Step4（自动化执行）职责边界**：

| 维度 | Step1–3 | Step4 |
|---|---|---|
| 触发时机 | 启动串流任务时自动执行 | 串流就绪后由前端「开始自动化」触发 |
| 退出语义 | 全成功 → 进入 `READY` 等待自动化；失败 → 任务失败、关闭串流 | 全部账号完成 → 关串流；任一失败 → **保持串流 + 窗口**，回到 `automation_failed` 等重试 |
| 手柄按键 | **禁止**自动化按键；仅建立 `ControllerProtocol` 通道（物理手柄/键盘人工接管走此通道） | **唯一**发送自动化按键来源；通过 `InputGate` 在暂停/非自动化期拦截 |
| 任务类型 | 不读取 `task_type` | **唯一**生效位置（`_apply_task_type` 调用点） |
| `streaming_session` | Step3 完成后写入 `ready` 阶段 | Step4 开始时锁定 `gameActionType` |
| 失败回调 | `STEP1/2/3 FAILED` → 任务 failed | `scope=session, phase=automation_failed`（保留任务 running） |

**复用任务约束**：同一 `(streaming_account_id, target_agent_id)` 终态任务会被复用为新一轮 `streaming_session`，Agent 侧通过 `ensure_task_slot(task_id, relaunch=True)` 清理旧 runtime 后重新跑 Step1–3。

`**task_type` 生效流程**（仅 step4 + 确认登录后）：

```
switch_to(account) → launch_fc_to_ut_menu / _retry_fc_launch_if_on_home
  → _match_expected_screen("MAIN_MENU") [仅匹配 UT 场景 127/149/147/101]
  → _apply_task_type(context, account, logger)  ← 此处生效
  → 按 task_type 执行比赛循环
```

合法值：`auction_transfer / squad_battle / transfer_sqb_combo / divisions_rivals / weekend_league`（非法归一为 `squad_battle`）

---

## 🛑 Agent 并发反模式禁忌（P0）

```python
# ❌ 单任务 finally 调 scheduler.close() — 会 stop_all_tasks() 误杀全部并发任务
finally:
    await scheduler.close()

# ✅ 仅停当前任务；scheduler 是进程级单例
except asyncio.CancelledError:
    await scheduler.stop_task(task_id)
    raise
```


| 反模式                                                  | 正确做法                                                                  |
| ---------------------------------------------------- | --------------------------------------------------------------------- |
| step4 模块级全局 `automation_engine` / `account_switcher` | 按 taskId 挂 `context._automation_engine` / `context._account_switcher` |
| `task_executor.scheduler`（属性不存在，被 try/except 静默吞）    | `from ..task.automation_scheduler import get_active_scheduler`        |
| FC 启动失败盲等 MAIN_MENU 25s 后跳过账号                        | `_retry_fc_launch_if_on_home(switcher, ...)` 检测主页 203 后重启 FC          |


**运行时约束**：


| 约束           | 值                                     | 来源                        |
| ------------ | ------------------------------------- | ------------------------- |
| 任务总并发        | `task.max_concurrent: 10`             | `configs/agent.yaml`      |
| GPU 解码并发     | `task.max_concurrent_gpu: 3`（超出降 CPU） | 同上                        |
| 同邮箱重登冷却      | `MIN_LOGIN_INTERVAL = 300s`           | `automation_scheduler.py` |
| 任意两次登录间隔     | `MIN_ACCOUNT_INTERVAL = 15s`          | 同上                        |
| HTTP 心跳 | 60s | `agent.yaml` `heartbeat_interval` |
| WS 心跳 | 30s（服务端 idle 默认 180s） | `agent.yaml` `ws_heartbeat_interval` |
| 进度回调节流 | 2s/步（终态立即上报） | `agent.yaml` `platform.progress_report_interval_sec` |


---

## 🎯 Streaming 场景模板匹配

详见 [bend-agent/docs/STEP4_SCENE_DESIGN.md](bend-agent/docs/STEP4_SCENE_DESIGN.md)


| 组件   | 路径                                                                              |
| ---- | ------------------------------------------------------------------------------- |
| 场景配置 | `bend-agent/configs/scene_schemas.py`（SCENE_SCHEMAS 100 行；SCENE_NAMES ID 1-204） |
| 场景流转 | `bend-agent/configs/scene_transitions.py`                                       |
| 场景检测 | `bend-agent/src/agent/scene/streaming_scene_detector.py`                        |
| 模板管理 | `bend-agent/src/agent/vision/template_manager.py`                               |


- **模板命名**：`{场景ID}.{模板ID}.png`（如 `templates/127.1.png`）
- **基准尺寸**：固定 `960×540`
- **推荐算法**：3（`TM_CCORR_NORMED`）
- **多模板分组**：按 `search_id` — 组内全命中算匹配，组间取最高
- **运行时降阈值**：仅对 `scene_id <= 64` 生效
- **Step4 必备场景**：`STEP4_REQUIRED_SCENE_IDS = [1,2,3,4,5,6,7,10,24,101,126,127,147,149,203]`，启动 `_validate_step4_templates` 预检；缺失则拒绝运行

---

## 🔄 通信协议

```
Agent ──HTTP/WS──► Gateway:8060 ──► Backend:8061
WebSocket URL: ws://{gateway}:8060/ws/agent/{agentId}
```

### WebSocket 消息矩阵

**入站（Platform → Agent）**：


| `type`                      | 用途                                   |
| --------------------------- | ------------------------------------ |
| `task`                      | 主任务下发（`task_executor.execute_task`）  |
| `task_control`              | **新协议** — 含 `action` 字段（见下）          |
| `command`                   | `capture_frame` / `get_scene` / 更新指令 |
| `version_update`            | 推送版本元数据                              |
| `automation_control`        | `action=stop` 全停（旧式）                 |
| `discover_xbox`             | LAN 发现                               |
| `stop_task` / `cancel_task` | 旧式停止                                 |


`**task_control.action` 值**：`pause` / `resume` / `cancel` / `terminate` / `show_window`(`window_show`) / `hide_window`(`window_hide`) / `focus_window` / `skip_game_account` / `reconnect_stream` / `start_game_automation` / `open_streaming_session`

**出站（Agent → Platform）**：`heartbeat` / `task_control_ack` / `task_result` / `status_report` / `xbox_discovered` / `progress`

> ⚠️ Agent README 列过 `task_ack` / `task_progress`，但**未在代码中实际发送**。任务流规范出口是 **HTTP**：`report_progress` / `complete_task` / `fail_task`。

### HTTP 回调端点（Agent → Backend）


| 客户端                 | 前缀                        | 关键端点                                                                                                                                           |
| ------------------- | ------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| `PlatformApiClient` | `/api/v1/agent-callback/` | `progress` · `task/{id}` · `xbox/{id}/lock|unlock` · `credentials/exchange` · `game-account/{id}/profile-binding`                              |
| `ApiClient`         | `/api/`                   | `agents/register` · `agents/heartbeat` · `agents/status` · `tasks/{id}/complete|fail` · `agents/version/check` · `registration-codes/activate` |


### API 响应格式

```json
{"code": 200, "message": "success", "data": { ... }}
```

错误码：200/400/401/403/404/429/500（429 = 网关限流）

---

## ⚙️ Agent 配置（`configs/agent.yaml` 真实键）

```yaml
backend:
  base_url: 'http://localhost:8060'        # 经 gateway
  ws_url: 'ws://localhost:8060/ws/agent'

agent:
  heartbeat_interval: 60                   # HTTP 心跳
  ws_heartbeat_interval: 30                # WS 心跳（建议 ≤ 服务端 idle 超时的一半）
  reconnect_delay: 5
  max_reconnect_attempts: 10

template:
  template_dir: './templates'              # ⚠ 键名为 template_dir
  threshold: 0.8

task:
  max_concurrent: 10
  max_concurrent_gpu: 3                    # 超出降 CPU
```

---

## 🔒 安全 / 测试 / 部署


| 类别   | 要点                                                            |
| ---- | ------------------------------------------------------------- |
| 密码   | AES 存储（`AesUtil`），HTTPS/WSS 传输                                |
| 日志   | 禁打印密码 / Token / refresh_token                                 |
| SQL  | MyBatis-Plus 参数化，禁拼接                                          |
| 限流   | 网关 Redis 滑动窗口（登录/注册严格、Agent 接口宽松）                             |
| 后端测试 | 核心模块 ≥ 80% 覆盖；`test{MethodName}_{Scenario}_{Expected}`        |
| 前端测试 | Vitest 单元 + MSW 集成；Playwright 已配置（待补 E2E）                     |
| 环境   | `.env.dev` / `.env.sit` / `.env.prod`（位于 `docker/`）           |
| Prod | `start-prod.ps1` 强制校验 `CHANGE_ME_*` 占位符                       |
| 健康检查 | 各服务 `healthcheck`；`depends_on: condition: service_healthy` 串联 |


### Git / 分支

`main` 生产 · `develop` 开发主干 · `feature/*` · `bugfix/*` · `hotfix/*`  
提交：`[类型] 描述`，类型：feat/fix/docs/style/refactor/test/chore

---

## 📚 相关文档

- [Step4 场景设计与新增手册](bend-agent/docs/STEP4_SCENE_DESIGN.md)
- [架构合理性评审](docs/review/01_architecture_review.md)
- [Agent 并发设计分析](docs/review/02_agent_concurrency.md)
- [前端结构与审美评审](docs/review/03_frontend_review.md)
- [数据库脚本](bend-platform/db/schema.sql) · [迁移索引](bend-platform/db/migration/MIGRATION_INDEX.md)
- [Agent 文档](bend-agent/README.md) · [部署文档](docker/DEPLOY.md)

---

## 🤖 自动化规则（机器可读）


| 标记  | 优先级 | 说明             |
| --- | --- | -------------- |
| ✅   | P0  | 必须遵守，违反将导致任务失败 |
| ⚠️  | P1  | 建议遵守，违反将发出警告   |
| 💡  | P2  | 最佳实践           |


```json
{
  "rules": [
    {"id": "R001", "name": "API请求规范", "priority": "P0", "check": "Agent 必须使用 PlatformApiClient / ApiClient，禁直接使用 aiohttp/requests", "location": ["bend-agent/src/agent/api/"]},
    {"id": "R002", "name": "日志规范", "priority": "P1", "check": "主日志 JSON；账号日志按 stream_log/ 与 game_log/ 分别落盘", "location": ["bend-agent/src/agent/core/logger.py", "bend-agent/src/agent/core/account_logger.py"]},
    {"id": "R003", "name": "自动化步骤位置", "priority": "P0", "check": "四步骤文件必须放在 automation/ 目录下", "location": ["bend-agent/src/agent/automation/"]},
    {"id": "R004", "name": "HTTP认证编码", "priority": "P0", "check": "X-Agent-Secret 必须 Base64 编码；WS 握手优先 header，URL 查询参数仅 legacy 兜底", "location": ["bend-agent/src/agent/api/platform_api_client.py", "bend-agent/src/agent/api/websocket.py"]},
    {"id": "R005", "name": "代码复用", "priority": "P1", "check": "避免代码重复，提取公共逻辑到工具类", "location": ["bend-agent/src/agent/"]},
    {"id": "R006", "name": "任务类型生效位置", "priority": "P0", "check": "task_type 仅在 step4_game_automation.py 中处理", "location": ["bend-agent/src/agent/automation/step4_game_automation.py"]},
    {"id": "R007", "name": "任务类型生效时机", "priority": "P0", "check": "task_type 必须在确认游戏账号登录成功后才能应用（_apply_task_type 调用点）", "location": ["bend-agent/src/agent/automation/step4_game_automation.py"]},
    {"id": "R008", "name": "Streaming场景模板匹配", "priority": "P0", "check": "模板文件命名 {场景ID}.{模板ID}.png；新增场景按 STEP4_SCENE_DESIGN.md 流程", "location": ["bend-agent/configs/scene_schemas.py", "bend-agent/src/agent/scene/streaming_scene_detector.py"]},
    {"id": "R009", "name": "任务控制面收敛", "priority": "P0", "check": "新接口加在 TaskControlController；旧 TaskController 不得新增 pause/resume/stop", "location": ["bend-platform/src/main/java/com/bend/platform/controller/TaskControlController.java"]},
    {"id": "R010", "name": "Agent 并发隔离", "priority": "P0", "check": "step4 严禁模块级全局；引擎/切换器挂 context._xxx；单任务 finally 严禁 scheduler.close()", "location": ["bend-agent/src/agent/automation/step4_game_automation.py", "bend-agent/src/agent/task/task_executor.py"]},
    {"id": "R011", "name": "调度器获取方式", "priority": "P0", "check": "用 get_active_scheduler()；不得通过 task_executor.scheduler 取（属性不存在）", "location": ["bend-agent/src/agent/task/automation_scheduler.py"]},
    {"id": "R012", "name": "数据库迁移规范", "priority": "P0", "check": "新增 V{YYYYMMDD}_{NNN}_*.sql 必须声明 utf8mb4 字符集，避免中文 COMMENT 乱码；并同步更新 schema.sql 与 MIGRATION_INDEX.md；通过 run-migration 脚本手动应用", "location": ["bend-platform/db/migration/", "bend-platform/db/schema.sql"]},
    {"id": "R013", "name": "Docker 启动规范", "priority": "P0", "check": "docker compose 必须带 --env-file docker/.env.{env}；优先用 docker/start-{env}.ps1", "location": ["docker/docker-compose.yml", "docker/start-dev.ps1"]},
    {"id": "R014", "name": "商户隔离强校验", "priority": "P0", "check": "商户写操作必须经 UserContext.getMerchantId() 显式传参 + DataSecurityUtil.validateMerchantAccess 校验", "location": ["bend-platform/src/main/java/com/bend/platform/util/UserContext.java", "bend-platform/src/main/java/com/bend/platform/util/DataSecurityUtil.java"]},
    {"id": "R015", "name": "前端单文件大小约束", "priority": "P1", "check": "单 .vue 不超过 800 行；超过应拆子组件 + composable；scoped 样式禁硬编码颜色（用 var(--*)）", "location": ["bend-platform-web/src/views/"]},
    {"id": "R016", "name": "后端注释规范", "priority": "P0", "check": "Controller / Service / Entity / DTO / Mapper 等新增或改动类必须补充类级 Javadoc；接口、公共方法、关键私有方法、重要字段、状态字段、复杂业务分支必须写清楚用途、约束、状态迁移与异常语义", "location": ["bend-platform/src/main/java/com/bend/platform/"]},
    {"id": "R017", "name": "前端注释规范", "priority": "P0", "check": "复杂函数、核心业务逻辑、关键状态计算、权限/计费/任务控制分支必须补充注释；禁止给简单赋值、显而易见表达式堆砌低价值注释", "location": ["bend-platform-web/src/"]},
    {"id": "R018", "name": "Agent 注释规范", "priority": "P0", "check": "自动化 Step1-4 每个步骤、任务状态流转、资源清理、异常保留/失败分支、输入控制、场景识别等核心环节必须写清楚注释；复杂 async 流程需说明等待条件与退出条件", "location": ["bend-agent/src/agent/automation/", "bend-agent/src/agent/runtime/", "bend-agent/src/agent/task/"]},
    {"id": "R019", "name": "Git 红线", "priority": "P0", "check": "禁止提交 target/、__pycache__/、logs/、tokens/、docker/.env.*；调试埋点不得入库", "location": [".gitignore"]}
  ]
}
```

---

## 📅 版本历史


| 版本  | 日期                      | 变更                                                                        |
| --- | ----------------------- | ------------------------------------------------------------------------- |
| 1.0 | 2026-05-13              | 初始版本                                                                      |
| 2.x | 2026-05-16 ~ 2026-05-21 | 认证 / 资源清理 / 结构优化                                                          |
| 3.0 | 2026-05-30              | GPU 解码、SDL 窗口、场景检测优化                                                      |
| 3.1 | 2026-06-02              | Streaming 场景模板匹配规范                                                        |
| 3.2 | 2026-06-07              | 全系统盘点修订；架构红线 + 并发反模式禁忌；WS 协议矩阵；Docker 4 profile + `--env-file`；精简至约 350 行 |
| 3.3 | 2026-06-07              | 串流任务长寿命化（任务复用 + `streaming_session` 多轮）；Step4 失败保留串流（`automation_failed`）；`InputGate` 统一收敛自动化按键；新增 Step1–3 vs Step4 边界表 |
| 3.4 | 2026-06-07              | 强化前端、后端、Agent 注释规范；要求接口、方法、字段、逻辑分支、自动化步骤与核心环节写清楚注释 |


