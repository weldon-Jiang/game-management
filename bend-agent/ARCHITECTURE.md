# Bend Agent 架构文档

**版本**: 1.0
**最后更新**: 2026-05-30
**适用范围**: Bend Agent 开发人员

---

## 一、系统架构概述

### 1.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          Bend Platform 系统架构                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│   ┌─────────────────────┐                                        │
│   │  Bend Platform Web  │  ← Vue3 Web管理界面                   │
│   │   (前端 Vue3)       │                                        │
│   └─────────┬───────────┘                                        │
│             │                                                    │
│   ┌─────────▼───────────┐     ┌─────────────────────┐           │
│   │    Bend Gateway     │────▶│   Bend Platform      │           │
│   │    (Java网关)       │     │   (Java后端)         │           │
│   └─────────┬───────────┘     └──────────┬──────────┘           │
│             │                            │                       │
│             │ WebSocket                   │ REST API              │
│             │                            │                       │
│   ┌─────────▼────────────────────────────▼──────────┐           │
│   │              Bend Agent (Python)                 │            │
│   │  CentralManager ──▶ AutomationScheduler ──▶    │            │
│   │              AgentAutomationTask (四步骤)        │            │
│   └─────────────────────────────────────────────────┘            │
│                          │                                        │
│                          ▼                                        │
│               ┌──────────────────────┐                           │
│               │    Xbox 主机         │                           │
│               │  (游戏执行环境)      │                           │
│               └──────────────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、模块架构

### 2.1 核心模块

| 模块 | 路径 | 核心职责 |
|------|------|----------|
| **api** | `agent/api/` | 与Bend Platform通信 |
| **auth** | `agent/auth/` | 微软账号认证(Token自动刷新) |
| **automation** | `agent/automation/` | 四步骤自动化流程 |
| **xbox** | `agent/xbox/` | GSSV 云端串流（xsrp_cloud_connect）+ 主机匹配/租约 |
| **vision** | `agent/vision/` | 画面捕获与模板匹配 |
| **scene** | `agent/scene/` | 场景识别(降频+缓存优化) |
| **input** | `agent/input/` | 手柄/键盘（ControllerProtocol + DataChannel） |
| **game** | `agent/game/` | 游戏账号管理 |
| **windows** | `agent/windows/` | 窗口管理(SDL自绘) |
| **task** | `agent/task/` | 任务调度 |
| **core** | `agent/core/` | 核心功能 |

---

## 三、四步骤数据流

### 3.1 步骤一：串流账号登录

```
输入: streaming_account_email, streaming_account_password
    │
    ▼
TokenStorage.load() ──▶ Refresh Token
    │
    ▼
MicrosoftOAuthClient.refresh_token() ──▶ 优先自动刷新
    │ (失败)
    ▼
设备码认证(用户交互) ──▶ MicrosoftTokens
    │
    ▼
XboxLiveClient.get_xbox_tokens() ──▶ XboxLiveTokens
    │
    ▼
TokenStorage.save() ──▶ 持久化Refresh Token
    │
    ▼
输出: microsoft_tokens, xbox_tokens
```

### 3.2 步骤二：Xbox 串流连接（xsrp / GSSV 云端）

```
输入: GSSV/Xbox tokens（Step1 xblive）
    │
    ▼
attach_streaming_credentials() ──▶ Token 校验
    │
    ▼
XboxHostMatcher + GSSV 云端发现 ──▶ 主机匹配 + serverId 租约
    │
    ▼
connect_xsrp_cloud() ──▶ play 会话 + WebRTC SDP（aiortc）
    │
    ▼
step3_execute_xsrp_init()（内联）──▶ 首帧 + input ready
    │
    ▼
输出: WebRTC 会话, frame_capture 就绪, current_xbox
```

> SmartGlass UDP 发现/唤醒（`xbox_discovery`）为 LAN 兜底，非 Step2 主传输路径。

### 3.3 步骤三：串流环境初始化（xsrp 栈）

```
输入: Step2 WebRTC 会话 / 帧源
    │
    ▼
XsrpFrameCapture ──▶ WebRTC 视频帧
    │
    ▼
SDL 串流窗口（step3_display_helpers）
    │
    ▼
ControllerProtocol / DataChannel ──▶ 输入通道
    │
    ▼
stream readiness 校验 + idle keepalive
    │
    ▼
输出: frame_capture, _controller_protocol, sdl_window, streaming_stack=xsrp
```

### 3.4 步骤四：游戏比赛自动化

```
输入: frame_capture, game_accounts, task_type
    │
    ▼
OptimizedSceneDetector ──▶ 降频检测+缓存
    │
    ▼
GameAutomationEngine ──▶ 状态决策
    │
    ▼
ControllerProtocol ──▶ 手柄信号发送
    │
    ▼
AccountSwitcher ──▶ 账号切换
    │
    ▼
循环: 账号 ──▶ 比赛 ──▶ 上报 ──▶ 完成
    │
    ▼
输出: matches_completed, accounts_processed
```

---

## 四、通信架构

### 4.1 与平台通信

| 通信方式 | 协议 | 认证 |
|----------|------|------|
| WebSocket | ws:// | URL参数agentSecret |
| HTTP | http:// | X-Agent-Secret(Base64) |

### 4.2 与 Xbox 通信（生产热路径：xsrp / GSSV 云端）

| 通信方式 | 协议 | 用途 |
|----------|------|------|
| GSSV REST | HTTPS | 云端主机列表、play 会话 |
| WebRTC | SDP/DataChannel | 视频帧 + 输入通道（Step2–3） |
| SmartGlass UDP | LAN 5050 | **仅**发现/唤醒兜底（非 Step2 主链路） |

### 4.3 遗留/调试模块

LAN SmartGlass TCP、PlaySession 等类仍存在于 `xbox/`、`xhome_stream/`，供调试或历史路径；**自动化 Step2–3 不经过 SmartGlass TCP 串流**。

---

## 五、类图

### 5.1 核心类

| 类名 | 模块 | 职责 |
|------|------|------|
| `CentralManager` | core | Agent生命周期管理 |
| `AutomationScheduler` | task | 任务调度与并发控制 |
| `AutomationTask` | automation | 四步骤协调执行 |
| `TaskContext` | task | 步骤间数据传递 |
| `MicrosoftMsalAuthenticator` | auth | 微软账号认证（调试/legacy） |
| `connect_xsrp_cloud` | xbox | GSSV 云端 + WebRTC 串流（Step2） |
| `XsrpFrameCapture` | xbox | WebRTC 帧捕获（Step3） |
| `SDLStreamWindow` | windows | SDL 窗口渲染 |
| `StreamingSceneDetector` | scene | 场景检测（Step4 主路径） |
| `ControllerProtocol` | input | DataChannel 手柄信号 |

---

## 六、优化功能

| 优化 | 对应步骤 | 功能 |
|------|----------|------|
| GSSV 云端 + WebRTC | 步骤二 | xsrp 串流握手（对齐 streaming） |
| SDL 窗口 + WebRTC 帧 | 步骤三 | 显示与 frame_capture |
| 场景检测优化 | 步骤四 | 降频检测+缓存 |
| InputGate | 步骤四 | 自动化/人工输入隔离 |

---

*文档结束*
