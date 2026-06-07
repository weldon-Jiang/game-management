# Bend Agent

Bend Platform 的客户端 Agent 服务，负责在 Windows 主机上执行 Xbox 游戏自动化任务。

## 功能特性

- **Xbox 主机发现**：自动发现局域网内的 Xbox 主机
- **流媒体控制**：通过 Xbox Streaming 控制游戏主机
- **GPU硬件加速**：支持 NVIDIA/AMD/Intel 硬件解码
- **SDL2窗口渲染**：自绘制游戏画面窗口
- **手柄控制**：自动模拟Xbox手柄输入
- **场景识别**：基于模板匹配的游戏界面检测
- **游戏自动化**：自动执行游戏任务（比赛、活动等）
- **多账号管理**：支持游戏账号自动切换
- **平台通信**：与 Bend Platform 后端实时通信
- **任务调度**：支持多任务并发执行

## 系统要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Windows 10/11 (64-bit) |
| 内存 | 8GB+ |
| 显卡 | 支持硬件解码 (NVIDIA/AMD/Intel) |
| 网络 | 局域网连接 Xbox 主机 |
| Python | 3.9+ |

## 目录结构

```
bend-agent/
├── configs/
│   └── agent.yaml           # Agent 配置文件
│   └── scene_schemas.py     # ✅ Streaming场景模板配置（新增）
├── distribution/
│   ├── agent.exe             # 打包后的可执行文件
│   └── agent.yaml.example    # 配置模板
├── scripts/
│   ├── build.bat             # 构建脚本
│   └── debug/                # 调试/实验脚本（非生产代码）
├── src/
│   ├── main.py               # 程序入口
│   └── agent/
│       ├── api/              # API 通信模块
│       │   ├── platform_api_client.py   # 平台 API 客户端（含认证）
│       │   ├── registration.py          # 注册激活
│       │   └── websocket.py             # WebSocket 客户端
│       ├── auth/             # 认证模块
│       │   ├── microsoft_auth_msal.py  # Microsoft MSAL 认证（支持Token自动刷新）
│       │   ├── browser_automation.py   # 浏览器自动化
│       │   └── browser_login_controller.py  # 浏览器登录控制器
│       ├── automation/       # 四步骤实现
│       │   ├── step1_stream_account_login.py
│       │   ├── step2_xbox_streaming.py
│       │   ├── step3_streaming_init.py
│       │   └── step4_game_automation.py
│       ├── task/              # 任务调度与编排
│       │   ├── automation_scheduler.py
│       │   ├── automation_task.py
│       │   ├── task_executor.py
│       │   └── task_context.py
│       ├── core/             # 核心模块
│       │   ├── central_manager.py  # 中央管理器（生命周期管理）
│       │   ├── config.py           # 配置管理
│       │   ├── logger.py           # 日志管理（JSON格式）
│       │   ├── account_logger.py    # 账号日志管理
│       │   ├── machine_identity.py  # 机器标识
│       │   └── system_resource_detector.py  # 系统资源检测
│       ├── game/              # 游戏模块
│       │   ├── account_manager.py   # 游戏账号管理
│       │   └── account_switcher.py  # 游戏账号切换器
│       ├── input/             # 输入控制模块
│       │   ├── xbox_gamepad.py      # Xbox手柄控制器（pygame）
│       │   ├── keyboard_mapper.py    # 键盘映射器
│       │   ├── controller_protocol.py # 手柄信号协议
│       │   └── input_controller.py   # 输入控制器
│       ├── scene/             # 场景检测模块
│       │   ├── scene_detector.py           # 场景检测器
│       │   ├── optimized_scene_detector.py  # 优化后的场景检测器（降频+缓存）
│       │   ├── streaming_scene_detector.py  # ✅ Streaming风格场景检测器（新增）
│       │   └── game_automation_engine.py    # 游戏自动化引擎
│       ├── vision/            # 视觉识别模块
│       │   ├── template_matcher.py  # 模板匹配
│       │   ├── template_manager.py   # ✅ Streaming模板管理器（新增）
│       │   ├── frame_capture.py     # 画面捕获
│       │   ├── gpu_decoder.py       # GPU解码器（优化）
│       │   └── gpu_frame_capture.py  # GPU加速帧捕获（优化）
│       ├── windows/           # Windows 窗口模块
│       │   ├── stream_window.py     # 串流窗口管理
│       │   ├── sdl_window.py        # SDL自绘窗口（优化）
│       │   └── task_window_manager.py # 任务窗口管理器
│       ├── xbox/              # Xbox 控制模块
│       │   ├── stream_controller.py # 流媒体控制器
│       │   ├── xbox_discovery.py    # Xbox SSDP 发现
│       │   ├── play_session.py      # PlaySession管理器（优化）
│       │   └── webrtc_handler.py    # WebRTC处理器（优化）
│       └── utils/             # 工具模块
│           └── crypto_util.py       # 加密工具
├── tokens/                   # Token 存储目录（运行时生成，不提交）
│   └── refresh_tokens.json   # Refresh Token 持久化存储
├── logs/                     # 日志目录
│   ├── stream_log/           # 流媒体账号日志
│   └── game_log/             # 游戏账号日志
└── requirements.txt          # Python 依赖
```

## 快速开始

### 1. 安装依赖

```bash
# 推荐：使用安装脚本（PyPI 失败时自动切换阿里云镜像）
scripts\install-deps.bat

# 或手动安装
pip install -r requirements.txt
```

云端串流相关依赖（已包含在 `requirements.txt`）：
- `aiortc` — WebRTC 媒体连接
- `av` — 视频帧解码
- `compress-pickle` — 模板 `templates.dat` 加载

### 2. 配置 Agent

复制配置文件并修改：

```bash
copy configs\agent.yaml.example configs\agent.yaml
```

编辑 `configs/agent.yaml`：

```yaml
backend:
  base_url: 'http://localhost:8060'       # 后端地址
  ws_url: 'ws://localhost:8060/ws/agent'  # WebSocket 地址

agent:
  heartbeat_interval: 30                   # 心跳间隔（秒）
  reconnect_delay: 5                       # 重连延迟（秒）
  max_reconnect_attempts: 10              # 最大重连次数
```

### 3. 运行 Agent

```bash
# 开发模式运行
python src/main.py

# 或指定配置文件
python src/main.py --config configs/agent.yaml

# 指定注册码激活并运行
python src/main.py --code AGENT-XXXX-XXXX-XXXX
```

### 4. 激活 Agent

首次运行需要输入商户注册码进行激活：

```
请输入商户注册码进行激活：
(注册码格式: AGENT-XXXX-XXXX-XXXX)

注册码: AGENT-XXXX-XXXX-XXXX
```

## 配置说明

### 配置文件：agent.yaml

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `backend.base_url` | 后端 HTTP 地址 | `http://localhost:8060` |
| `backend.ws_url` | WebSocket 地址 | `ws://localhost:8060/ws/agent` |
| `agent.heartbeat_interval` | 心跳间隔（秒） | 30 |
| `agent.reconnect_delay` | 重连延迟（秒） | 5 |
| `agent.max_reconnect_attempts` | 最大重连次数 | 10 |
| `video.fps` | 视频捕获帧率 | 10 |
| `template.threshold` | 模板匹配阈值 | 0.8 |
| `template.dir` | 模板图片目录 | templates |
| `gpu.enabled` | 启用GPU硬件加速 | true |
| `gpu.preferred_type` | 首选GPU类型 | auto |

详细配置说明请参考 [config.py](src/agent/core/config.py)。

## 自动化任务四步骤流程

Agent 自动化任务采用**串行四步骤**设计，必须**完成当前步骤后才能进入下一步骤**，任一步骤失败则整个任务失败。

### 四步骤概述

```
任务初始化 → 【步骤一】串流账号登录 → 【步骤二】Xbox串流连接
    → 【步骤三】串流环境初始化 → 【步骤四】游戏比赛自动化 → 任务完成

⚠️ 步骤串行执行：必须完成步骤一才能进入步骤二，依此类推
⚠️ 失败即终止：任一步骤失败，任务立即失败并上报错误
⚠️ 步骤依赖：步骤四依赖步骤三初始化的画面捕获能力
```

### 步骤一：串流账号登录

**文件**：`step1_stream_account_login.py`

**功能**：使用MSAL设备码认证流程登录微软账号

**流程**：
1. 验证账号信息完整性（邮箱、密码）
2. 优先使用Refresh Token自动刷新获取新Token
3. Refresh Token失效时使用设备码认证
4. 使用Access Token获取Xbox Live Token
5. 保存Tokens到任务上下文供后续步骤使用

**技术特点**：
- Token自动刷新：无需用户交互
- 多账号管理：支持多账号Token存储
- 持久化存储：Refresh Token保存到本地文件

### 步骤二：Xbox串流连接

**文件**：`step2_xbox_streaming.py`

**功能**：匹配并连接到Xbox主机

**流程**：
1. 判断是否指定Xbox主机
   - 已指定：直接使用指定主机，测试连接
   - 未指定：通过SSDP协议自动发现在线Xbox（`XboxDiscovery.discover()`）
2. 测试Xbox连接（端口5050）
3. 使用Xbox令牌建立SmartGlass连接
4. 创建PlaySession（Xbox Live会话管理）
5. 执行SDP握手（WebRTC协商）
6. 初始化GPU硬件解码（优化）

**优化模块**：
- `xbox/play_session.py`：PlaySession生命周期管理
- `xbox/webrtc_handler.py`：WebRTC SDP握手处理
- `vision/gpu_decoder.py`：GPU类型检测和参数配置

**注意**：`XboxDiscovery.discover()` 方法不接受 `timeout` 参数，调用时请勿传入该参数

### 步骤三：串流环境初始化

**文件**：`step3_streaming_init.py`

**功能**：为步骤四准备串流环境和画面捕获能力

**核心定位**：
- 这是步骤四的"准备工作"
- 为步骤四提供画面捕获器、手柄控制器、SDL窗口等能力
- 步骤四直接使用这些能力进行游戏自动化

**流程**：
1. 初始化串流窗口（SDL自绘窗口）
2. 初始化画面捕获器（GPU加速）
3. 初始化手柄控制器（pygame）
4. 初始化键盘映射器
5. 检测游戏主界面
6. 将所有组件保存到上下文供步骤四使用

**优化模块**：
- `windows/sdl_window.py`：SDL2自绘窗口，支持高效帧捕获
- `vision/gpu_frame_capture.py`：GPU加速帧捕获器
- `input/xbox_gamepad.py`：pygame手柄控制器
- `input/keyboard_mapper.py`：键盘到Xbox手柄映射

**输出**：
- `context.frame_capture`：GPU加速画面捕获器
- `context.sdl_window`：SDL自绘窗口
- `context.gamepad_controller`：手柄控制器
- `context.keyboard_mapper`：键盘映射器

### 步骤四：游戏比赛自动化

**文件**：`step4_game_automation.py`

**功能**：使用步骤三的画面捕获能力自动执行游戏比赛

**核心依赖**：
- 使用 `context.frame_capture`（步骤三初始化）进行画面检测
- 使用 `context.gamepad_controller` 发送手柄指令
- 通过画面状态判断比赛进度

**流程**：
1. 验证画面捕获器是否可用
2. 初始化游戏自动化引擎和优化后的场景检测器
3. 初始化手柄协议（ControllerProtocol）
4. 遍历所有游戏账号
5. 每个账号执行指定场比赛（默认3场/账号）
6. 使用画面检测判断比赛状态（开始、进行中、结束）
7. 实时上报比赛状态到平台
8. 记录比赛次数

**优化模块**：
- `scene/optimized_scene_detector.py`：
  - 降频检测：每5帧检测一次，节省CPU
  - 画面变化检测：过滤无效检测
  - 结果缓存：场景稳定时复用结果
- `game/account_switcher.py`：游戏账号自动切换
- `input/controller_protocol.py`：手柄信号协议封装

**画面检测**：
- 使用步骤三初始化的 `context.frame_capture` 进行画面捕获
- 使用优化后的场景检测器进行降频+缓存检测
- 检测比赛准备、比赛开始、比赛进行中、比赛结束等状态
- 根据画面状态执行相应的自动化操作

### 步骤依赖关系

```
步骤一 ──► 步骤二 ──► 步骤三 ──► 步骤四
  │          │          │          │
  │          │          │          │
  │          │          ├──────────┴──► frame_capture, gamepad, keyboard_mapper
  │          │          │
  │          │          └── SDL窗口、手柄控制器、GPU解码器
  │          │
  │          ├── Xbox连接
  │          ├── PlaySession
  │          ├── SDP握手
  │          └── GPU检测
  │
  └── MSAL认证（Token自动刷新）
```

### 状态流转

```
PENDING → RUNNING → STEP1 → STEP2 → STEP3 → STEP4 → COMPLETED
                  ↓        ↓       ↓       ↓
                (任一步骤失败，任务立即失败)
```

## 核心模块说明

### CentralManager

中央管理器，负责 Agent 的整体运行管理。

```python
from agent.core.central_manager import CentralManager

manager = CentralManager(agent_id, agent_secret)
await manager.start()
```

### MicrosoftMsalAuthenticator

微软账号认证器，支持Token自动刷新。

```python
from agent.auth.microsoft_auth_msal import MicrosoftMsalAuthenticator

authenticator = MicrosoftMsalAuthenticator()
result = await authenticator.login_with_credentials("user@outlook.com", "password")
if result.success:
    print(f"用户哈希: {result.xbox_tokens.user_hash}")
```

**认证流程**：
1. 优先使用Refresh Token自动刷新（无需用户交互）
2. Refresh Token失效时使用设备码认证
3. 成功后将Refresh Token保存到本地

### XboxStreamController

Xbox流媒体控制器，负责与Xbox主机通信。

```python
from agent.xbox.stream_controller import XboxStreamController

controller = XboxStreamController()
await controller.connect_with_token(xbox_host, xbox_tokens)
await controller.send_input("gamepad", {"buttons": ["A"]})
```

### GPUDecoder

GPU硬件解码器，自动检测并配置GPU加速。

```python
from agent.vision.gpu_decoder import GPUDecoder, get_gpu_info

# 获取GPU信息
gpu_info = get_gpu_info()
print(f"GPU类型: {gpu_info.gpu_type}")
print(f"推荐解码器: {gpu_info.recommended_decoder}")

# 创建解码器
decoder = GPUDecoder()
await decoder.initialize(gpu_info)
```

### SDLStreamWindow

SDL2自绘串流窗口，支持高效画面捕获。

```python
from agent.windows.sdl_window import SDLStreamWindow

window = SDLStreamWindow(width=1280, height=720)
await window.initialize()

# 更新画面
frame = capture.read_frame()
window.update_frame(frame)

# 捕获用于处理
processing_frame = window.get_frame_for_detection()
```

### OptimizedSceneDetector

优化后的场景检测器，支持降频检测和缓存。

```python
from agent.scene.optimized_scene_detector import OptimizedSceneDetector, SceneConfig

config = SceneConfig(
    frame_interval=5,        # 每5帧检测一次
    confidence_threshold=0.7,
    cache_timeout_sec=2.0
)
detector = OptimizedSceneDetector(config)
detector.set_matcher(template_matcher)

# 检测场景
result = await detector.detect_scene(frame)
print(f"场景: {result.scene.value}, 置信度: {result.confidence}")

# 获取统计
stats = detector.get_stats()
print(f"跳过率: {stats['skip_rate']}, 缓存命中率: {stats['cache_rate']}")
```

### StreamingSceneDetector

Streaming风格场景检测器，支持多区域模板匹配。

```python
from agent.scene.streaming_scene_detector import StreamingSceneDetector

# 初始化
detector = StreamingSceneDetector(
    template_dir="templates",
    default_threshold=0.8
)

# 预加载模板
detector.preload_all_templates()

# 识别场景
result = detector.recognize_scene(frame)

if result.matched:
    print(f"场景ID: {result.scene_id}, 置信度: {result.confidence:.2f}")
    for template_result in result.template_results:
        print(f"  模板{template_result['template_id']}: {template_result['matched']}")
```

**参考项目**：[D:\auto-xbox\streaming\xsrpst.py](file:///D:/auto-xbox/streaming/xsrpst.py)

**详细配置指南**：[docs/TEMPLATE_CONFIG_GUIDE.md](docs/TEMPLATE_CONFIG_GUIDE.md)

### XboxPlaySessionManager

PlaySession管理器，负责Xbox Live会话生命周期。

```python
from agent.xbox.play_session import XboxPlaySessionManager

session_manager = XboxPlaySessionManager(access_token)
await session_manager.create_session(xbox_id)
await session_manager.exchange_sdp(sdp_offer)
```

### PlatformApiClient

平台 API 客户端，负责与后端通信。

```python
from agent.api.platform_api_client import PlatformApiClient

client = PlatformApiClient()

# 获取游戏账号状态
status = await client.get_game_accounts_status(task_id)

# 上报比赛完成
await client.report_match_complete(task_id, game_account_id, count)

# 上报任务进度
await client.report_task_progress(task_id, step, status, message)
```

### TaskExecutor

任务执行器，负责执行自动化任务。

```python
from agent.task.task_executor import TaskExecutor

executor = TaskExecutor(task_data)
await executor.execute()
```

## 任务类型扩展

Agent 支持多种自动化任务类型，并提供统一的任务框架便于扩展新类型。

### 任务类型分层设计

```
自动化任务 (automation)
├── stream_control      - Xbox串流控制任务（连接测试）
├── xbox_automation     - Xbox游戏自动化任务（四步骤）
├── game_training       - 游戏训练任务（预留）
└── custom_action       - 自定义操作任务（预留）
```

### 统一状态上报机制

#### 任务级别状态

| 状态 | 说明 |
|------|------|
| `pending` | 待执行 |
| `running` | 执行中 |
| `completed` | 已完成 |
| `failed` | 失败 |
| `cancelled` | 已取消 |
| `timeout` | 超时 |

#### 步骤级别状态

| 状态 | 说明 |
|------|------|
| `pending` | 待执行 |
| `running` | 执行中 |
| `completed` | 已完成 |
| `failed` | 失败 |
| `skipped` | 跳过 |

#### 子任务级别状态（游戏账号）

| 状态 | 说明 |
|------|------|
| `pending` | 待执行 |
| `running` | 操作中 |
| `game_preparing` | 游戏准备中 |
| `gaming` | 游戏中 |
| `completed` | 已完成 |
| `failed` | 失败 |
| `cancelled` | 已取消 |
| `timeout` | 超时 |

### 创建新任务类型

要添加新的自动化任务类型，只需遵循以下步骤：

#### 1. 创建任务类

继承自 `BaseAutomationTask` 并实现 `_execute_steps()` 方法：

```python
# src/agent/task/game_training_task_new.py
from agent.task.base_task import BaseAutomationTask, StepStatus
from typing import Dict, Any, Callable

class GameTrainingTask(BaseAutomationTask):
    """
    游戏训练任务示例
    """

    def __init__(self, task_id: str, params: Dict[str, Any], platform_client=None):
        super().__init__(task_id, "game_training", platform_client)
        self.params = params

    async def _execute_steps(self, check_cancel: Callable[[], bool]) -> Dict[str, Any]:
        """
        执行训练任务的步骤
        """
        # 步骤一：初始化训练环境
        await self._report_step_status("STEP1", StepStatus.RUNNING, "初始化训练环境")

        if check_cancel():
            await self._report_step_status("STEP1", StepStatus.SKIPPED, "任务被取消")
            return {"message": "任务被取消"}

        # 执行步骤一逻辑...
        await self._report_step_status("STEP1", StepStatus.COMPLETED, "训练环境初始化完成")

        # 步骤二：执行训练
        await self._report_step_status("STEP2", StepStatus.RUNNING, "开始执行训练")

        if check_cancel():
            await self._report_step_status("STEP2", StepStatus.SKIPPED, "任务被取消")
            return {"message": "任务被取消"}

        # 执行步骤二逻辑...
        await self._report_step_status("STEP2", StepStatus.COMPLETED, "训练执行完成")

        return {"message": "训练任务完成"}
```

#### 2. 注册任务类型

在 `TaskFactory` 中注册新任务类型：

```python
# 方式一：预注册（在 task_factory.py 中）
try:
    from .game_training_task_new import GameTrainingTask
    TaskFactory.register_task("game_training", GameTrainingTask)
except ImportError as e:
    print(f"预注册GameTrainingTask失败: {e}")

# 方式二：动态注册（运行时）
from agent.task.game_training_task_new import GameTrainingTask
from agent.task.task_factory import TaskFactory

TaskFactory.register_task("game_training", GameTrainingTask)
```

#### 3. 创建任务并执行

```python
from agent.task.task_factory import TaskFactory
from agent.api.platform_api_client import PlatformApiClient

# 创建平台客户端
client = PlatformApiClient()
client.set_credentials(agent_id, agent_secret)

# 创建任务实例
params = {
    "streamingAccountId": "xxx",
    "trainingMode": "aim_training"
}
task = TaskFactory.create_task("game_training", "task_123", params, client)

# 执行任务
result = await task.execute(timeout_seconds=1800)
```

### 任务工厂

`TaskFactory` 负责统一管理和创建不同类型的任务：

```python
from agent.task.task_factory import TaskFactory, TaskType

# 获取所有已注册的任务类型
types = TaskFactory.get_registered_types()

# 创建任务实例
task = TaskFactory.create_task(
    task_type=TaskType.GAME_TRAINING.value,
    task_id="task_123",
    params={"key": "value"},
    platform_client=client
)
```

### 核心文件说明

| 文件 | 说明 |
|------|------|
| `task/base_task.py` | 基础任务接口，定义统一的任务执行框架 |
| `task/task_factory.py` | 任务工厂，管理任务类型注册和实例创建 |
| `task/automation_task.py` | Xbox自动化任务实现（四步骤协调） |
| `api/platform_api_client.py` | 平台API客户端，提供统一的状态上报方法 |

## 与平台通信

### WebSocket 连接

Agent 通过 WebSocket 与平台保持长连接：

```
ws://localhost:8060/ws/agent/{agentId}?agentSecret={secret}
```

**认证方式**：`agentSecret` 通过 URL 参数直接传递（原始字符串）

### HTTP 认证

Agent 通过 HTTP 向平台上报数据时需要认证：

| 请求头 | 说明 |
|--------|------|
| `X-Agent-Id` | Agent ID（原始字符串） |
| `X-Agent-Secret` | Agent Secret（必须经过 Base64 编码） |

**注意**：WebSocket 和 HTTP 使用相同的凭证，但传递方式和格式要求不同。

### 心跳机制

- 发送频率：每 30 秒一次
- 平台超时：60 秒（2 倍心跳间隔）

### 消息类型

| 消息类型 | 方向 | 说明 |
|---------|------|------|
| `task` | 平台 → Agent | 下发任务 |
| `command` | 平台 → Agent | 控制命令 |
| `heartbeat` | Agent → 平台 | 心跳 |
| `task_ack` | Agent → 平台 | 任务确认 |
| `task_progress` | Agent → 平台 | 进度上报 |

详细协议请参考 [AGENTS.md](../AGENTS.md)。

## 构建发布版本

### Windows 可执行文件

```bash
# 使用 PyInstaller 构建
pyinstaller --onefile --windowed src/main.py
```

或使用构建脚本：

```bash
scripts\build.bat
```

## 常见问题

### 1. Xbox 主机无法发现

- 确保 Xbox 主机与 Agent 在同一局域网
- 检查 Xbox 主机「允许远程连接」设置
- 检查防火墙设置

### 2. WebSocket 连接失败

- 检查后端服务是否运行
- 验证 `backend.ws_url` 配置正确
- 检查网络连通性

### 3. 模板匹配失效

- 确认模板图片存在于 `templates/` 目录
- 调整 `template.threshold` 阈值
- 检查游戏画面分辨率是否匹配

### 4. GPU硬件加速不生效

- 检查显卡驱动是否安装
- 确认显卡支持硬件解码
- 查看日志中的GPU检测信息

### 5. 手柄控制无响应

- 检查pygame是否正常初始化
- 确认Xbox主机连接正常
- 查看日志中的手柄信号发送记录

## 相关文档

- [AGENTS.md](../AGENTS.md) - 全局技能文档
- [API 文档](../bend-platform-api.json) - 平台 API 定义
- [部署文档](../docker/DEPLOY.md) - Docker 部署指南
- [Streaming对比报告](../.trae/documents/streaming_agent_comparison_report.md) - 与Streaming项目功能对比
- [优化计划报告](../.trae/documents/agent_optimization_plan.md) - Agent优化计划与执行记录
- [模板配置指南](docs/TEMPLATE_CONFIG_GUIDE.md) - ✅ Streaming场景模板配置详解（新增）
