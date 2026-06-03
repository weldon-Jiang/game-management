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
| **xbox** | `agent/xbox/` | Xbox主机控制(SmartGlass+PlaySession) |
| **vision** | `agent/vision/` | 画面捕获与GPU解码 |
| **scene** | `agent/scene/` | 场景识别(降频+缓存优化) |
| **input** | `agent/input/` | 手柄控制(pygame+SmartGlass) |
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

### 3.2 步骤二：Xbox串流连接

```
输入: xbox_tokens
    │
    ▼
XboxDiscovery.discover() ──▶ Xbox主机发现(SSDP)
    │
    ▼
XboxStreamController.connect() ──▶ SmartGlass连接(TCP:5050)
    │
    ▼
XboxPlaySessionManager.create_session() ──▶ PlaySession创建
    │
    ▼
XboxWebRTCHandler.exchange_sdp() ──▶ SDP握手
    │
    ▼
GPUDecoder检测 ──▶ GPU硬件解码准备
    │
    ▼
输出: xbox_session, current_xbox
```

### 3.3 步骤三：串流环境初始化

```
输入: xbox_session, current_xbox
    │
    ▼
SDLStreamWindow.initialize() ──▶ pygame窗口创建
    │
    ▼
GPUFrameCapture.initialize() ──▶ GPU加速捕获器
    │
    ▼
XboxGamepadController.initialize() ──▶ pygame手柄
    │
    ▼
KeyboardMapper.initialize() ──▶ YAML键位映射
    │
    ▼
检测游戏主界面 ──▶ 模板匹配验证
    │
    ▼
输出: frame_capture, sdl_window, gamepad_controller, keyboard_mapper
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

### 4.2 与Xbox通信

| 通信方式 | 端口 | 协议 | 用途 |
|----------|------|------|------|
| SSDP | UDP | 发现协议 | Xbox发现 |
| SmartGlass | TCP:5050 | JSON | 控制指令 |
| PlaySession | HTTPS | REST API | 会话管理 |

---

## 五、类图

### 5.1 核心类

| 类名 | 模块 | 职责 |
|------|------|------|
| `CentralManager` | core | Agent生命周期管理 |
| `AutomationScheduler` | task | 任务调度与并发控制 |
| `AutomationTask` | automation | 四步骤协调执行 |
| `TaskContext` | task | 步骤间数据传递 |
| `MicrosoftMsalAuthenticator` | auth | 微软账号认证 |
| `XboxStreamController` | xbox | SmartGlass通信 |
| `XboxPlaySessionManager` | xbox | PlaySession管理 |
| `GPUDecoder` | vision | GPU硬件解码 |
| `SDLStreamWindow` | windows | SDL窗口渲染 |
| `OptimizedSceneDetector` | scene | 场景检测(优化) |
| `ControllerProtocol` | input | 手柄信号协议 |

---

## 六、优化功能

| 优化 | 对应步骤 | 功能 |
|------|----------|------|
| GPU硬件解码 | 步骤二 | NVDEC/AMF/QSV自动检测 |
| SDL自绘窗口 | 步骤三 | pygame高效渲染 |
| 场景检测优化 | 步骤四 | 降频检测+缓存 |
| 手柄信号发送 | 步骤四 | SmartGlass协议 |

---

*文档结束*
