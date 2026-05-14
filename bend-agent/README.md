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
│       │   ├── client.py     # HTTP 客户端
│       │   ├── registration.py # 注册激活
│       │   └── websocket.py  # WebSocket 客户端
│       ├── auth/             # 认证模块
│       │   └── microsoft_auth.py
│       ├── automation/        # 自动化任务模块
│       │   ├── automation_scheduler.py  # 任务调度器
│       │   ├── automation_task.py      # 自动化任务基类
│       │   ├── platform_api_client.py # 平台 API 客户端
│       │   ├── step1_stream_account_login.py  # 步骤1：流媒体账号登录
│       │   ├── step2_xbox_streaming.py        # 步骤2：Xbox 流媒体连接
│       │   ├── step3_gpu_decode.py            # 步骤3：GPU 解码设置
│       │   └── step4_game_automation.py       # 步骤4：游戏自动化
│       ├── core/             # 核心模块
│       │   ├── central_manager.py  # 中央管理器
│       │   ├── config.py     # 配置管理
│       │   ├── logger.py     # 日志管理
│       │   └── update_manager.py # 更新管理
│       ├── game/              # 游戏模块
│       │   └── account_manager.py
│       ├── input/            # 输入控制模块
│       │   └── input_controller.py
│       ├── scene/             # 场景检测模块
│       │   └── scene_detector.py
│       ├── task/              # 任务执行模块
│       │   ├── task_executor.py
│       │   └── stream_control_task.py
│       ├── vision/            # 视觉识别模块
│       │   ├── template_matcher.py  # 模板匹配
│       │   └── frame_capture.py     # 画面捕获
│       ├── windows/           # Windows 窗口模块
│       │   └── stream_window.py
│       └── xbox/              # Xbox 控制模块
│           ├── stream_controller.py  # 流媒体控制器
│           └── xbox_discovery.py     # Xbox 发现
└── requirements.txt           # Python 依赖
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

## 与平台通信

### WebSocket 连接

Agent 通过 WebSocket 与平台保持长连接：

```
ws://localhost:8060/ws/agent/{agentId}?agentSecret={secret}
```

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
