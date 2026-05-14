# Bend Platform - Agent 全局技能文档

## ⚠️ 重要规则
**根据需求编写代码时，要走一步想十步，不能只顾当前需求，还要考虑未来可能的需求变化，以及涉及到的关联影响的功能模块。**

**改完代码后必须用 Docker Compose 构建重启验证功能：**
```bash
# 构建并重启所有服务（从项目根目录执行）
docker compose -f docker/docker-compose.yml up -d --build

# 重启单个服务
docker compose -f docker/docker-compose.yml up -d --build backend    # 重启后端
docker compose -f docker/docker-compose.yml up -d --build gateway    # 重启网关
docker compose -f docker/docker-compose.yml up -d --build frontend   # 重启前端

# 查看服务状态
docker compose -f docker/docker-compose.yml ps

# 查看日志
docker compose -f docker/docker-compose.yml logs -f backend
docker compose -f docker/docker-compose.yml logs -f gateway
```

**数据库变更必须写迁移脚本：**
涉及数据库结构或数据变更的操作，必须创建 SQL 迁移脚本，不能手工修改数据库。

迁移脚本位置：`bend-platform/db/`

```sql
-- update_xxx_description.sql
ALTER TABLE table_name ADD COLUMN column_name VARCHAR(64) COMMENT '字段说明';
```

**⚠️ 重要：必须同步更新 schema.sql 文件：**
- 迁移脚本仅用于更新已有数据库
- schema.sql 是数据库初始化脚本，必须保持与数据库结构完全一致
- 每次创建迁移脚本后，必须同步更新 schema.sql 中对应的表结构
- 确保新成员执行 `schema.sql` 初始化时能获得最新的完整表结构

**前端 API 请求必须使用封装的 request 实例：**
```javascript
// ✅ 正确：使用封装的 request
import request from '@/utils/request'
const response = await request.get('/api/xxx')

// ❌ 错误：直接使用 axios
import axios from 'axios'
const response = await axios.get('/api/xxx')
```

原因：项目支持统一的错误处理和响应拦截。

**Agent API 请求必须使用 PlatformApiClient：**
```python
# ✅ 正确：使用封装的 PlatformApiClient
from agent.automation.platform_api_client import PlatformApiClient

client = PlatformApiClient(base_url='http://localhost:8060/api')

# 获取游戏账号状态
status = await client.get_game_accounts_status(task_id)

# 上报比赛完成
result = await client.report_match_complete(task_id, game_account_id, completed_count)

# 上报任务进度
await client.report_task_progress(task_id, step, status, message)
```

```python
# ❌ 错误：直接使用 aiohttp/requests
import aiohttp
async with aiohttp.ClientSession() as session:
    async with session.get(url) as response:
        # 缺少重试机制
        # 缺少统一错误处理
        # 缺少日志记录
        pass
```

原因：PlatformApiClient 提供统一的重试机制、日志记录、错误处理，并支持 HTTP/WebSocket 双路上报。

**⚠️ 重要：设计变更必须同步更新 README.md：**
- 当架构设计、功能设计、接口设计等方案发生变更时，必须同步更新相关 README.md 文档
- 确保 README.md 是最新、最全的说明文档，新成员可以通过 README.md 快速了解项目
- **各模块 README.md 文档要求：**
  - 项目根目录：`README.md`（项目整体介绍）
  - `bend-platform/README.md`（后端服务说明）
  - `bend-platform-web/README.md`（前端说明）
  - `bend-gateway/README.md`（网关说明）
  - `bend-agent/README.md`（Agent 客户端说明）
  - `docker/README.md`（部署说明）
- 当新增模块时，必须同步创建对应的 README.md 文件

---

## 项目概述

Bend Platform 是一个商户自动化服务平台，支持：
- **商户管理**：用户注册、登录、VIP等级管理
- **流媒体账号管理**：Netflix、Hulu 等账号管理
- **游戏账号管理**：Xbox Live 游戏账号管理
- **Xbox 主机管理**：Xbox 主机发现、远程控制
- **自动化任务**：Agent 执行游戏自动化任务
- **激活码管理**：订阅激活码生成和兑换

### 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          客户端/Agent                             │
│                    前端 Web (3090) | Agent                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                     Bend Gateway (网关层)                        │
│                          Port: 8060                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │                    Spring Cloud Gateway                     │  │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────────────────────┐  │  │
│  │  │ IP过滤   │  │ 限流    │  │ 路由转发                │  │  │
│  │  │ Filter  │  │ Filter  │  │ Route: /api/** → 8061  │  │  │
│  │  └─────────┘  └─────────┘  └─────────────────────────┘  │  │
│  └──────────────────────────────────────────────────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Bend Platform (后端)                       │
│                         Port: 8061                                │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐  │
│  │ WebSocket│  │  HTTP    │  │  Task    │  │  Agent Load      │  │
│  │ Endpoint │  │  REST    │  │  Executor│  │  Control        │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────────┬─────────┘  │
│       │             │             │                 │             │
│  ┌────┴─────────────┴─────────────┴─────────────────┴─────────┐  │
│  │                      Service Layer                            │  │
│  │  AutomationService │ TaskService │ GameAccountService       │  │
│  └──────────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │                      MyBatis Plus ORM                        │  │
│  └──────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
         │                         ▲
         │ WebSocket / HTTP        │ HTTP Callback
         ▼                         │
┌─────────────────────────────────────────────────────────────────┐
│                        Bend Agent (客户端)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐   │
│  │WebSocket │  │  Task    │  │  Xbox    │  │  Game        │   │
│  │ Client   │  │  Executor│  │  Control │  │  Automation  │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

**服务端口：**
| 服务 | 端口 | 说明 |
|------|------|------|
| Gateway | 8060 | API 网关，统一入口 |
| Platform | 8061 | 后端服务 |
| Frontend | 3090 | 前端页面 |

---

## 一、Agent 与平台通信协议

### 1.0 网关层 (Gateway)

所有客户端请求（包括 Agent）通过 Gateway 网关层统一入口。

#### 1.0.1 网关配置

**配置文件：** `bend-gateway/src/main/resources/application.yml`

```yaml
spring:
  cloud:
    gateway:
      routes:
        - id: platform-api
          uri: http://localhost:8061
          predicates:
            - Path=/api/**
          filters:
            - StripPrefix=1

bend:
  gateway:
    rate-limit:
      enabled: true
      default-limit:
        qps: 100      # 每秒最大请求数
        burst: 50     # 突发容量
      paths:
        - path: /api/task/**
          qps: 10
          burst: 5
    ip-filter:
      enabled: true
      whitelist:      # IP白名单
        - 127.0.0.1
        - 192.168.0.0/16
      blacklist:      # IP黑名单
        - 10.0.0.1
```

#### 1.0.2 网关功能

| 功能 | 说明 |
|------|------|
| **IP 过滤** | 支持白名单/黑名单，可配置启用/禁用 |
| **限流** | 基于 Redis 的令牌桶算法，支持按路径差异化限流 |
| **路由转发** | 将 `/api/**` 请求转发到 Platform 后端 (8061) |
| **熔断** | Circuit Breaker 保护后端服务 |

#### 1.0.3 网关错误响应

| HTTP 状态码 | 说明 |
|------------|------|
| 403 | IP 被禁止访问 |
| 429 | 请求过于频繁，触发限流 |
| 502/504 | 后端服务不可用 |

**429 限流响应：**
```json
{
  "code": 429,
  "message": "请求过于频繁，请稍后再试"
}
```

#### 1.0.4 Agent 请求网关

Agent 请求应发送到网关端口 (8060)，网关会自动路由到后端 (8061)：

```
Agent → ws://localhost:8060/ws/agent/{agentId}
Agent → http://localhost:8060/api/task/{taskId}/match/complete
```

### 1.1 通信方式

| 方式 | 用途 | 端口/路径 |
|------|------|----------|
| **WebSocket** | 实时双向通信：任务下发、心跳、控制命令 | `ws://host:port/ws/agent/{agentId}` |
| **HTTP REST** | Agent 回调平台：进度上报、状态同步 | `http://host:port/api/task/...` |

### 1.2 WebSocket 连接

**连接地址（通过网关）：**
```
ws://{gateway_host}:8060/ws/agent/{agentId}?agentSecret={secret}
```

**注意：** WebSocket 连接由网关转发到后端 Platform (8061) 处理。

**连接认证参数：**
| 参数 | 说明 |
|------|------|
| `agentId` | Agent 唯一标识符 |
| `agentSecret` | Agent 密钥 |

**JavaScript 连接示例：**
```javascript
const ws = new WebSocket('ws://localhost:8061/ws/agent/agent_001?agentSecret=your_secret')

ws.onopen = () => {
  console.log('WebSocket connected')
  // 接收消息
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data)
    handleMessage(msg)
  }
}
```

### 1.3 心跳机制

- **Agent 发送频率**：每 30 秒一次
- **平台超时时间**：60 秒（2 倍心跳间隔）
- **心跳超时**：Agent 超过 60 秒未发送心跳，平台认为 Agent 离线

**心跳消息格式（Agent → 平台）：**
```json
{
  "type": "heartbeat",
  "data": {
    "agentId": "agent_001",
    "timestamp": 1704067200000,
    "status": "online",
    "currentTaskId": null,
    "cpuUsage": 45.2,
    "memoryUsage": 62.8
  }
}
```

**心跳响应（平台 → Agent）：**
```json
{
  "type": "heartbeat_ack",
  "data": {
    "serverTime": 1704067200000
  }
}
```

### 1.4 消息类型

| 消息类型 | 方向 | 说明 |
|---------|------|------|
| `task` | 平台 → Agent | 下发自动化任务 |
| `command` | 平台 → Agent | 控制命令（停止、重启等） |
| `control` | 平台 → Agent | 控制指令（与 command 类似） |
| `heartbeat` | Agent → 平台 | 心跳保活 |
| `heartbeat_ack` | 平台 → Agent | 心跳确认 |
| `task_ack` | Agent → 平台 | 任务接收确认 |
| `task_progress` | Agent → 平台 | 任务进度上报（WebSocket） |
| `task_result` | Agent → 平台 | 任务执行结果 |
| `status_report` | Agent → 平台 | 状态上报 |
| `xbox_discovered` | Agent → 平台 | Xbox 设备发现 |
| `connected` | 平台 → Agent | 连接成功通知 |
| `error` | 平台 → Agent | 错误消息 |

---

## 二、任务下发协议

### 2.1 任务消息格式（平台 → Agent）

```json
{
  "type": "task",
  "data": {
    "taskId": "task_xxx",
    "type": "automation",
    "streamingAccount": {
      "id": "sa_001",
      "name": "Netflix Account 1",
      "email": "user@example.com",
      "authCode": "xxx",
      "passwordToken": "encrypted_password_token"
    },
    "gameAccounts": [
      {
        "gameAccountId": "ga_001",
        "xboxGameName": "PlayerOne",
        "xboxLiveEmail": "player1@example.com",
        "isPrimary": true,
        "priority": 1,
        "dailyMatchLimit": 3,
        "todayMatchCount": 0
      }
    ],
    "xboxHosts": [
      {
        "id": "xh_001",
        "xboxId": "XboxSeriesX001",
        "name": "Living Room Xbox",
        "ipAddress": "192.168.1.100",
        "boundGamertag": "PlayerOne"
      }
    ]
  }
}
```

### 2.2 任务确认（Agent → 平台）

```json
{
  "type": "task_ack",
  "data": {
    "taskId": "task_xxx",
    "status": "accepted",
    "message": "Task accepted"
  }
}
```

### 2.3 停止任务命令（平台 → Agent）

```json
{
  "type": "control",
  "data": {
    "action": "stop",
    "streamingAccountId": "sa_001",
    "reason": "user_requested"
  }
}
```

---

## 三、HTTP 回调接口

Agent 完成任务特定操作后回调平台接口。

### 3.1 获取游戏账号状态

**接口：** `GET /api/task/{taskId}/game-accounts/status`

**响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": [
    {
      "id": "ga_001",
      "completedCount": 2,
      "failedCount": 0,
      "totalMatches": 3,
      "status": "running",
      "completed": false
    }
  ]
}
```

### 3.2 上报比赛完成

**接口：** `POST /api/task/{taskId}/match/complete`

**Content-Type：** `application/x-www-form-urlencoded`

**参数：**
| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| gameAccountId | String | 是 | 游戏账号ID |
| completedCount | Integer | 是 | 当前完成的场次 |
| success | Boolean | 否 | 是否成功，默认 true |

**响应：**
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "allAccounts": [...],
    "allCompleted": false
  }
}
```

### 3.3 上报任务进度

**接口：** `POST /api/task/{taskId}/progress`

**Content-Type：** `application/json`

**请求体：**
```json
{
  "taskId": "task_xxx",
  "step": "step3_game_automation",
  "status": "RUNNING",
  "message": "Playing match 2 of 3"
}
```

**status 值：**
| 值 | 说明 |
|----|------|
| `PENDING` | 等待执行 |
| `RUNNING` | 执行中 |
| `COMPLETED` | 已完成 |
| `FAILED` | 失败 |

### 3.4 上报游戏账号完成

**接口：** `POST /api/task/{taskId}/game-account/{gameAccountId}/complete`

**请求体：**
```json
{
  "status": "completed",
  "completedCount": 3,
  "failedCount": 0,
  "errorMessage": null
}
```

### 3.5 重置每日比赛计数

**接口：** `POST /api/task/daily-match-count/reset`

**响应：**
```json
{
  "code": 200,
  "message": "已重置所有游戏账号的今日比赛数"
}
```

---

## 四、任务执行流程

```
1. Agent 连接 WebSocket
      ↓
2. 发送心跳 (type: heartbeat)
      ↓
3. 接收任务消息 (type: task)
      ↓
4. 回复任务确认 (type: task_ack)
      ↓
5. 调用 GET /api/task/{taskId}/game-accounts/status 获取账号列表
      ↓
6. 对每个游戏账号执行比赛
      ↓
7. 每完成一场 → POST /api/task/{taskId}/match/complete
      ↓
8. 单个账号完成 → POST /api/task/{taskId}/game-account/{id}/complete
      ↓
9. 全部完成 → POST /api/task/{taskId}/progress (status=COMPLETED)
      ↓
10. 任务结束，等待下一个任务
```

---

## 五、数据库规范

### 5.1 表命名规范

- 商户相关：`merchant_*`
- 流媒体账号：`streaming_account`
- 游戏账号：`game_account`
- Xbox 主机：`xbox_host`
- 任务：`task`
- 任务游戏账号状态：`task_game_account_status`
- 激活码：`activation_code`
- 订阅：`subscription`

### 5.2 字段命名规范

- 主键：`id` (VARCHAR(64) 或 VARCHAR(36))
- 创建时间：`created_time` (DATETIME)
- 更新时间：`updated_time` (DATETIME)
- 逻辑删除：`deleted` (TINYINT, 0=正常, 1=删除)
- 状态：`status` (VARCHAR 或 ENUM)

### 5.3 完整表结构

**详细表结构请参考：** [schema.sql](bend-platform/db/schema.sql)

该文件包含完整的 27 张数据表定义。

---

## 六、API 响应格式

### 6.1 统一响应结构

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

### 6.2 错误码

| 错误码 | 说明 |
|-------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## 七、Agent 配置

### 7.1 配置文件位置

```
bend-agent/configs/agent.yaml
```

### 7.2 关键配置项

```yaml
backend:
  base_url: 'http://localhost:8061'       # 后端HTTP地址
  ws_url: 'ws://localhost:8061/ws/agents'  # WebSocket地址
  api_prefix: '/api'                        # API路由前缀

agent:
  heartbeat_interval: 30                 # 心跳间隔（秒）
  reconnect_delay: 5                      # 重连延迟（秒）
  max_reconnect_attempts: 10              # 最大重连次数
  ws_heartbeat_interval: 30               # WebSocket心跳间隔
```

### 7.3 Agent 端核心类

| 类 | 文件 | 说明 |
|---|------|------|
| WSClient | `bend-agent/src/agent/api/websocket.py` | WebSocket 客户端 |
| PlatformApiClient | `bend-agent/src/agent/automation/platform_api_client.py` | Platform API 客户端 |
| CentralManager | `bend-agent/src/agent/core/central_manager.py` | Agent 中央管理器 |
| TaskExecutor | `bend-agent/src/agent/task/task_executor.py` | 任务执行器 |

---

## 八、最佳实践

### 8.1 断线重连

- WebSocket 断开后，Agent 应在 5 秒后尝试重连
- 使用指数退避策略：delay = reconnect_delay * min(attempt, 5)
- 重连时需要重新进行认证

### 8.2 任务超时

- 默认任务超时时间：3600 秒（1 小时）
- Agent 应在超时前完成任务或主动上报进度
- 平台每分钟检查一次任务超时 (`TaskTimeoutChecker`)

### 8.3 状态同步

- Agent 每次上报 `match/complete` 后，平台会返回最新的所有账号状态
- Agent 应根据返回结果判断是否继续执行或结束任务
- 使用 `task_game_account_status` 表跟踪每个游戏账号的完成情况

### 8.4 并发控制

- Agent 支持配置最大并发任务数 (`max_concurrent_tasks`)
- 平台使用 `AgentLoadControlService` 跟踪 Agent 负载
- 使用本地 `ConcurrentHashMap` 或 Redis 计数

### 8.5 异常处理

- 遇到错误时，应记录错误日志并继续执行其他任务
- 任务完全失败时，调用 `/progress` 接口并设置 `status: FAILED`
- 重要错误应上报到平台 (`report_task_error`)

---

## 九、版本历史

| 版本 | 日期 | 说明 |
|-----|------|------|
| 1.0 | 2026-05-13 | 初始版本，完整的通信协议文档 |

---

## 十、相关文档

- [API 文档](bend-platform-api.json) - OpenAPI 3.0 格式的完整 API 定义
- [数据库 ER 图](bend-platform/db/ER_diagram.md) - 数据库表关系图
- [数据库脚本](bend-platform/db/schema.sql) - 数据库初始化脚本
- [部署文档](docker/DEPLOY.md) - Docker 部署指南
- [Agent 文档](bend-agent/README.md) - Bend Agent 客户端使用说明
