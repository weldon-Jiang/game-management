# Bend Agent 架构文档

**版本**: 3.1 · **更新**: 2026-07-20 · **Python**: 3.9+ asyncio · **子包**: 18 (从 24 合并) · **总行**: ~38,000

---

## 一、包结构总览

```
agent/                                  201 py files  ~38K lines
│
├── main.py                    (260L)   ← 入口: 参数解析 → CentralManager 启动
│
├── core/                      (20f)    ← 基础层: 配置/日志/路径/身份/许可/更新
├── api/                       (6f)     ← 平台通信: HTTP Client / WS Client / 注册
├── auth/                      (16f)    ← 认证: xblive SISU 全链路 / MSAL(legacy)
│
├── automation/                (21f)    ← 自动化四步骤 (核心编排)
│   ├── step1/ xblive_login  (128L)
│   ├── step2/ router + xsrp + ps (167L)
│   ├── step3/ xsrp_init + display (719L)
│   ├── step4/ orchestrator + 10 modules (3652L)
│   └── platform_util.py              ← 共享: 平台判断
│
├── task/                      (6f)     ← 任务调度与编排: Scheduler/Executor/Context/Session
├── runtime/                   (10f)    ← 运行时: 并发原语/FSM/InputGate/StreamRuntime/Session
│
├── xbox/                      (21f)    ← Xbox 串流: GSSV/WebRTC/恢复/发现/租约/xHome
├── gssv/                      (10f)    ← GSSV 协议: 云端发现/play/WebRTC/输入
│
├── vision/                    (11f)    ← 计算机视觉: 帧捕获/模板匹配/OCR/GPU解码
├── scene/                     (6f)     ← 场景检测: Streaming/FC/优化检测器
│
├── input/                     (10f)    ← 输入控制: 手柄/键盘/协议/泵调度
├── game/                      (10f)    ← 游戏逻辑: 账号切换/FC启动/键盘
│
├── window/                    (6f)     ← 窗口管理: SDL/Stream/DisplayPump/TaskManager
│
├── discovery/                 (10f)    ← 设备发现: Xbox/PS/Console/Tenant UDP/LAN工具
├── playstation/               (11f)    ← PlayStation: Chiaki/发现/串流
│
├── runtime/                   (10f)    ← 运行时: 并发原语/FSM/InputGate/Session
├── system/                    (2f)     ← 系统集成: 托盘图标
└── debug/                     (4f)     ← 调试: 追踪/手动捕获/调试控制
```

---

## 二、自动化四步骤 (核心数据流)

### Step1 — 串流账号认证
> `automation/step1/xblive_login.py` + `auth/xblive/`

```
streaming_account (email + password)
  → SISU Device Token 认证
  → Xbox Live Token 交换 (gsToken/serverId/playPath/gamerTag)
  → attach_streaming_credentials → context.xbox_tokens
```

### Step2 — 串流握手
> `automation/step2/router.py` → `xsrp_streaming.py` / `playstation_streaming.py`

```
Xbox 路径:
  context.xbox_tokens → GSSV 云端发现 (gssv/)
  → serverId 租约 (xbox/console_lease)
  → play 会话 + WebRTC SDP 握手 (xbox/step2_xsrp_connect)
  → 首帧解码 + DataChannel 就绪
  → 内联链式执行 Step3 初始化

PlayStation 路径:
  → Chiaki 发现 + 连接 (playstation/)
```

### Step3 — 串流环境初始化
> `automation/step3/xsrp_init.py` + `display_helpers.py`

```
Step2 产物 (WebRTC session + frame source)
  → XsrpFrameCapture (WebRTC 视频帧)
  → SDL 串流窗口 (windows/sdl_window)
  → ControllerProtocol / DataChannel 输入通道
  → stream readiness 校验 (帧稳定 + input channel 通畅)
  → idle keepalive + liveness monitor
  → 输出: frame_capture, controller_protocol, sdl_window
```

### Step4 — 游戏自动化
> `automation/step4/` (11 modules)

```
Step3 产物 (frame_capture + input channel)
  → FC 启动 (_retry_fc_launch_if_on_home)
  → 账号切换 (game/account_switcher)
  → task_type 路由 (转会 / SQB / DR / WL)
  → 模式导航 (navigator)
  → 比赛循环 (match_lifecycle: enter → wait → play → finish)
  → 赛后结算 (post_match)
  → 计费上报 + 进度同步
```

---

## 三、架构评审

### 3.1 ✅ 设计良好的部分

| 模式 | 说明 |
|------|------|
| **automation/step{1-4}/** | 四步独立包, 职责清晰, 每步 ≤12 模块 |
| **gssv/** (10f) | GSSV 协议隔离, 不依赖 xbox/ 业务 |
| **input/** (10f) | 输入抽象清晰: Protocol → Gamepad/Keyboard → Pump |
| **vision/** (11f) | CV 关注点集中: Capture → Decode → Template → OCR |
| **playstation/** (11f) | 平台隔离, 仅通过动态导入接入 step2/router |
| **runtime/** (8f) | 并发原语独立: FSM/InputGate/TaskRegistry/PauseControl |

### 3.2 ✅ 已优化 (2026-07-20)

| # | 变更 | 结果 |
|---|------|------|
| 1 | `window/` + `windows/` → `window/` | 6 文件合并, 消除一字之差混淆 |
| 2 | `auth/step{1,2,3}_router.py` → 删除 | 零引用死代码 |
| 3 | `orchestration/` → `task/` | 2 文件并入, 消除微包 |
| 4 | `session/` → `runtime/` | 2 文件并入 |
| 5 | `lan/` → `discovery/` | LAN 工具并入选 device 发现 |
| 6 | `utils/` → `core/` | 单文件包消除 |
| 7 | `xhome_stream/` → `xbox/` | Legacy 兜底并入 |

**24 子包 → 18 子包** (-25%)

### 3.3 ⚠ 待后续优化

| # | 问题 | 严重度 | 建议 |
|---|------|--------|------|
| 8 | **`core/`** 过大 (21f) — 配置/日志/身份/许可/发现混在一起 | P2 | 拆分子包: config / logging / identity / licensing |
| 9 | **`xbox/`** 过大 (21f) — GSSV/WebRTC/恢复/发现/租约/xHome 全在一个包 | P2 | 拆分: 协议层(gssv) / 串流层(xsrp) / 发现层 |
| 10 | **`auth/` legacy 代码** — `microsoft_auth_msal.py`(1090L) + `browser_*.py` | P3 | MSAL 已废弃，确认 xblive 不再依赖后移除 |

### 3.3 外部引用热图

```
被引用最多的包 (跨包 import 次数):
  core/        ← 所有模块的配置/日志依赖
  task/        ← Scheduler/Context 被 orchestration/session/xbox 引用
  xbox/        ← GSSV/WebRTC 被 step2/step3/runtime 引用
  automation/  ← step{1-4} 被 auth/orchestration/task 引用
  input/       ← controller_protocol 被 step3/step4/xbox 引用

仅自引用的包 (无外部 import):
  debug/       ← 仅内部, 通过动态 import 接入
  system/      ← 托盘图标, 仅 main.py 启动
  playstation/ ← 仅 step2/router 动态导入
```

---

## 四、建议目标架构

```
agent/
├── core/                        ← 基础 (拆分子包)
│   ├── config.py
│   ├── logging/                 ← account/game/heartbeat logger
│   ├── crypto.py                ← 从 utils/ 迁入
│   ├── paths.py
│   └── identity.py              ← machine_identity + license_checker
│
├── platform/                    ← 从 api/ 重命名
│   ├── http.py, ws.py, registration.py, auth.py
│
├── auth/                        ← 精简
│   ├── step1_xblive.py
│   ├── xblive/                  ← SISU/Token/签名
│   └── credentials.py
│
├── streaming/                   ← NEW: 合并 xbox + gssv + xhome + step2 + step3
│   ├── step2/
│   ├── step3/
│   ├── xsrp/                    ← GSSV/WebRTC 协议
│   ├── recovery.py
│   └── keepalive.py
│
├── automation/                  ← 游戏自动化 (保持)
│   ├── step1/ step2/ step3/ step4/
│
├── vision/                      ← CV (保持)
├── input/                       ← 输入 (保持)
│
├── window/                       ← 合并 window/ + windows/
│   ├── manager.py, sdl.py, stream.py
│
├── task/                         ← 合并 orchestration/ + runtime/
│   ├── scheduler.py, executor.py, context.py
│   ├── fsm.py, input_gate.py, registry.py
│   └── session.py               ← 从 session/ 迁入
│
├── game/                         ← 游戏逻辑 (保持)
├── discovery/                    ← 合并 lan/ 网络工具
├── system/                       ← 合并 debug/ 调试工具
└── playstation/                  ← PS 平台 (保持隔离)
```

### 迁移优先级

| 优先级 | 变更 | 影响文件 |
|--------|------|----------|
| **P0** | `window/` + `windows/` → `window/` | ~12 引用点 |
| **P1** | `orchestration/` → `task/` | 3 引用点 |
| **P1** | `session/` → `runtime/` 或 `streaming/` | 2 引用点 |
| **P1** | step routers 迁入各 automation/step 包 | 6 引用点 |
| **P2** | `lan/` → `discovery/` | ~4 引用点 |
| **P2** | `utils/` → `core/` | 1 引用点 |
| **P2** | `xhome_stream/` → `xbox/` (或删除) | ~4 引用点 |
| **P3** | `core/` 拆分子包 | ~全量 |

---

## 五、关键设计决策

| 决策 | 说明 |
|------|------|
| **Step1–3 串行, 任一失败→任务失败** | 串流准备必须有确定性结果 |
| **Step4 失败保留串流** | 用户可重试, 不关窗口/串流 |
| **task_type 仅 Step4 生效** | Step1–3 不读取 task_type |
| **InputGate 统一收敛** | 暂停/非自动化期拦截所有按键, Step4 是唯一自动化按键来源 |
| **GSSV 云端为热路径, SmartGlass 仅兜底** | UDP 5050 仅用于 LAN 发现/唤醒, 不传输视频 |
| **分控不连 Redis** | tenant profile 自动排除, ConcurrentHashMap fallback |
| **Agent UDP 47820 自动发现分控** | 免注册码, 局域网零配置 |

---

## 六、并发模型

```
CentralManager (单例)
  └─ CentralManager.start()
       ├─ PlatformApiClient (HTTP 心跳, 60s)
       ├─ WebSocketClient (WS 心跳, 30s)
       └─ AutomationScheduler (单例)
            ├─ TaskRegistry (并发原语)
            ├─ PhaseFSM (状态机)
            ├─ InputGate (输入门控)
            └─ TaskExecutor[] (每任务一个)
                 ├─ step1 → step2 → step3 → step4
                 └─ StreamRuntime (帧泵 + 场景检测)
```

**并发约束:**
- 最大并发任务: `task.max_concurrent: 10`
- GPU 解码并发: `task.max_concurrent_gpu: 3`
- 同邮箱重登冷却: 300s
- 任意两次登录间隔: 15s

---

*文档结束 — 版本 3.0*
