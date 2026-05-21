# Bend Agent

Bend Platform 的客户端 Agent 服务，负责在 Windows 主机上执行 Xbox 游戏自动化任务。

## 功能特性

- **Xbox 主机发现**：自动发现局域网内的 Xbox 主机
- **流媒体控制**：通过 Xbox Streaming 控制游戏主机
- **游戏自动化**：自动执行游戏任务（比赛、活动等）
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
├── distribution/
│   ├── agent.exe             # 打包后的可执行文件
│   └── agent.yaml.example    # 配置模板
├── scripts/
│   └── build.bat             # 构建脚本
├── src/
│   ├── main.py               # 程序入口
│   └── agent/
│       ├── api/              # API 通信模块
│       │   ├── credentials_provider.py  # 凭证管理
│       │   ├── platform_api_client.py   # 平台 API 客户端（含认证）
│       │   ├── registration.py          # 注册激活
│       │   └── websocket.py             # WebSocket 客户端
│       ├── auth/             # 认证模块
│       │   └── microsoft_auth.py        # Microsoft MSAL 认证
│       ├── automation/       # 自动化任务模块（四步骤实现）
│       │   ├── automation_scheduler.py  # 并发任务调度器
│       │   ├── automation_task.py       # 四步骤协调器
│       │   ├── step1_stream_account_login.py  # 步骤1：串流账号登录
│       │   ├── step2_xbox_streaming.py        # 步骤2：Xbox串流连接
│       │   ├── step3_streaming_init.py        # 步骤3：串流环境初始化
│       │   ├── step4_game_automation.py       # 步骤4：游戏比赛自动化
│       │   ├── task_context.py                # 任务上下文管理
│       │   └── task_window_manager.py         # 窗口管理器
│       ├── core/             # 核心模块
│       │   ├── central_manager.py  # 中央管理器（生命周期管理）
│       │   ├── config.py           # 配置管理
│       │   ├── logger.py           # 日志管理（JSON格式）
│       │   └── update_manager.py   # 更新管理
│       ├── game/              # 游戏模块
│       │   └── account_manager.py  # 游戏账号管理
│       ├── input/             # 输入控制模块
│       │   └── input_controller.py # 模拟按键输入
│       ├── scene/             # 场景检测模块
│       │   └── scene_detector.py   # 场景识别
│       ├── task/              # 任务执行模块
│       │   ├── task_executor.py    # 任务执行器（WebSocket入口）
│       │   └── task_factory.py     # 任务工厂
│       ├── vision/            # 视觉识别模块
│       │   ├── template_matcher.py  # 模板匹配
│       │   └── frame_capture.py     # 画面捕获
│       ├── windows/           # Windows 窗口模块
│       │   └── stream_window.py     # 串流窗口管理
│       └── xbox/              # Xbox 控制模块
│           ├── stream_controller.py  # 流媒体控制器
│           └── xbox_discovery.py     # Xbox SSDP 发现
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
pip install -r requirements.txt
```

### 2. 配置 Agent

复制配置文件并修改：

```bash
copy configs\agent.yaml.example configs\agent.yaml
```

编辑 `configs/agent.yaml`：

```yaml
backend:
  base_url: 'http://localhost:8060'       # 后端地址
  ws_url: 'ws://localhost:8060/ws/agents'  # WebSocket 地址

agent:
  heartbeat_interval: 30                   # 心跳间隔（秒）
  reconnect_delay: 5                       # 重连延迟（秒）
  max_reconnect_attempts: 10                # 最大重连次数
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
| `backend.ws_url` | WebSocket 地址 | `ws://localhost:8060/ws/agents` |
| `agent.heartbeat_interval` | 心跳间隔（秒） | 30 |
| `agent.reconnect_delay` | 重连延迟（秒） | 5 |
| `agent.max_reconnect_attempts` | 最大重连次数 | 10 |
| `video.fps` | 视频捕获帧率 | 10 |
| `template.threshold` | 模板匹配阈值 | 0.8 |

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
2. 调用 Microsoft 认证服务获取 Access Token
3. 使用 Access Token 获取 Xbox Live Token
4. 保存 Tokens 到任务上下文供后续步骤使用

### 步骤二：Xbox串流连接

**文件**：`step2_xbox_streaming.py`

**功能**：匹配并连接到Xbox主机

**流程**：
1. 判断是否指定Xbox主机
   - 已指定：直接使用指定主机，测试连接
   - 未指定：通过SSDP协议自动发现在线Xbox（`XboxDiscovery.discover()`）
2. 测试Xbox连接（端口5050）
3. 使用Xbox令牌建立串流连接

**注意**：`XboxDiscovery.discover()` 方法不接受 `timeout` 参数，调用时请勿传入该参数

### 步骤三：串流环境初始化

**文件**：`step3_streaming_init.py`

**功能**：为步骤四准备串流环境和画面捕获能力

**核心定位**：
- 这是步骤四的"准备工作"
- 为步骤四提供画面捕获器（VideoFrameCapture）
- 步骤四直接使用这些能力进行游戏自动化

**流程**：
1. 初始化串流窗口
2. 初始化画面捕获器（VideoFrameCapture）
3. 将画面捕获器保存到 `context.frame_capture`
4. 检测游戏主界面
5. 返回画面捕获器到上下文供步骤四使用

**输出**：
- `context.frame_capture`: VideoFrameCapture 实例，供步骤四使用

### 步骤四：游戏比赛自动化

**文件**：`step4_game_automation.py`

**功能**：使用步骤三的画面捕获能力自动执行游戏比赛

**核心依赖**：
- 使用 `context.frame_capture`（步骤三初始化）进行画面检测
- 通过画面状态判断比赛进度

**流程**：
1. 验证画面捕获器是否可用
2. 遍历所有游戏账号
3. 每个账号执行指定场比赛（默认3场/账号）
4. 使用画面检测判断比赛状态（开始、进行中、结束）
5. 实时上报比赛状态到平台
6. 记录比赛次数

**画面检测**：
- 使用步骤三初始化的 `context.frame_capture` 进行画面捕获
- 检测比赛准备、比赛开始、比赛进行中、比赛结束等状态
- 根据画面状态执行相应的自动化操作

### 步骤依赖关系

```
步骤一 ──► 步骤二 ──► 步骤三 ──► 步骤四
  │          │          │          │
  │          │          │          │
  │          │          └──────────┘
  │          │                     │
  │          │            步骤四依赖步骤三的
  │          │            frame_capture
  │          │
  └──────────┴──► Tokens ──► Xbox连接
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

### PlatformApiClient

平台 API 客户端，负责与后端通信。

```python
from agent.automation.platform_api_client import PlatformApiClient

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
| `task/stream_control_task_new.py` | 串流控制任务实现（示例） |
| `task/automation_task_new.py` | Xbox自动化任务实现（示例） |
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

## 相关文档

- [AGENTS.md](../AGENTS.md) - 全局技能文档
- [API 文档](../bend-platform-api.json) - 平台 API 定义
- [部署文档](../docker/DEPLOY.md) - Docker 部署指南
