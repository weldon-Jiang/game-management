# Bend Platform - Agent 全局技能文档

---

## 目录

1. [重要规则](#-重要规则)
2. [开发代码规范](#开发代码规范)
   - [后端服务（Java/Spring Boot）](#后端服务javaspring-boot)
   - [前端服务（Vue3 + TypeScript）](#前端服务vue3--typescript)
   - [Agent 服务（Python）](#agent-服务python)
3. [通用规范](#通用规范)
   - [安全规范](#安全规范)
   - [测试规范](#测试规范)
   - [版本控制规范](#版本控制规范)
   - [部署运维规范](#部署运维规范)
   - [代码设计规范](#代码设计规范)
4. [项目概述](#项目概述)
5. [Agent 与平台通信协议](#agent-与平台通信协议)
6. [任务下发协议](#任务下发协议)
7. [HTTP 回调接口](#http-回调接口)
8. [任务执行流程](#任务执行流程)
9. [数据库规范](#数据库规范)
10. [API 响应格式](#api-响应格式)
11. [Agent 配置](#agent-配置)
12. [最佳实践](#最佳实践)
13. [版本历史](#版本历史)
14. [相关文档](#相关文档)

---

## ⚠️ 重要规则

### 核心原则
- **前瞻设计**：根据需求编写代码时，要走一步想十步，不能只顾当前需求，还要考虑未来可能的需求变化，以及涉及到的关联影响的功能模块。

### Docker Compose 验证
- 改完代码后必须用 Docker Compose 构建重启验证功能，确保所有服务都能正常运行
- 只针对本项目的 docker 服务和镜像，不操作其他项目的 docker 服务和镜像

```bash
docker compose -f docker/docker-compose.yml up -d --build
docker compose -f docker/docker-compose.yml up -d --build backend
docker compose -f docker/docker-compose.yml up -d --build gateway
docker compose -f docker/docker-compose.yml up -d --build frontend
docker compose -f docker/docker-compose.yml ps
docker compose -f docker/docker-compose.yml logs -f backend
```

### 日志跟踪
- 部署完成后，必须立即检查各服务日志，确认没有 ERROR 或 Exception
- 如果用户反馈错误信息，必须主动读取容器日志进行分析定位问题

### 数据库变更
- 涉及数据库结构或数据变更的操作，必须创建 SQL 迁移脚本
- 迁移脚本位置：`bend-platform/db/`

### Schema 同步
- 迁移脚本仅用于更新已有数据库
- schema.sql 是数据库初始化脚本，必须保持与数据库结构完全一致
- 每次创建迁移脚本后，必须同步更新 schema.sql

### API 请求规范
- **前端**：必须使用封装的 `request` 实例，不直接使用 axios
- **Agent**：必须使用 `PlatformApiClient`，不直接使用 aiohttp/requests

### Agent 服务验证
- Agent 服务（Python）代码改动后，需要主动启动服务并验证功能
- 启动命令：`python -m agent.main` 或根据项目实际启动方式
- **聚焦验证原则**：只验证新增或改动的功能模块，不做全流程验证
  - 修改连接逻辑 → 验证连接功能
  - 修改心跳机制 → 验证心跳功能
  - 修改任务处理 → 验证任务接收和执行功能
  - 修改消息协议 → 验证消息序列化和解析
  - 修改认证逻辑 → 验证 Microsoft 账号登录
  - 修改自动化流程 → 验证自动化任务执行
  - 修改视觉识别 → 验证场景检测和模板匹配
  - 修改 Xbox 控制 → 验证 Xbox 发现和流控制
- 检查日志输出，确保无错误信息

### Agent 服务功能模块
| 模块 | 功能说明 | 文件位置 |
|------|---------|---------|
| **api** | WebSocket 通信、API 客户端、Agent 注册 | `src/agent/api/` |
| **auth** | Microsoft 账号认证 | `src/agent/auth/` |
| **automation** | 自动化调度、多步骤任务执行 | `src/agent/automation/` |
| **core** | 中央管理、配置、日志、更新管理 | `src/agent/core/` |
| **game** | 游戏账号管理 | `src/agent/game/` |
| **input** | 输入控制器（模拟按键等） | `src/agent/input/` |
| **scene** | 场景检测 | `src/agent/scene/` |
| **task** | 任务执行器、流控制任务 | `src/agent/task/` |
| **vision** | 视觉识别、帧捕获、模板匹配 | `src/agent/vision/` |
| **windows** | Windows 窗口管理 | `src/agent/windows/` |
| **xbox** | Xbox 设备发现、流控制 | `src/agent/xbox/` |

### 文档更新
- 当架构设计、功能设计、接口设计等方案发生变更时，必须同步更新相关 README.md 文档

---

## 开发代码规范

### 后端服务（Java/Spring Boot）

1. **统一 import 引入方式**
   - ✅ 正确：在类顶部使用 `import com.example.ClassName;`
   - ❌ 错误：在方法中直接使用 `com.example.ClassName.method()`

2. **清理未使用的 import**
   - 使用 IDE 的自动清理功能（如 IntelliJ 的 Optimize Imports）

3. **代码格式化**
   - 使用 IDE 的格式化工具确保代码格式一致

4. **代码注释**
   - 为关键方法、类、接口添加注释，使用英文注释

5. **代码命名规范**
   - 类名使用大驼峰（PascalCase）
   - 方法和变量使用小驼峰（camelCase）
   - 避免魔法值、魔法字符串硬编码，使用常量或枚举

6. **API 响应规范**
   - 统一使用 `ApiResponse<T>` 包装响应
   - 错误码使用枚举定义

7. **数据库操作**
   - 使用 MyBatis Plus 提供的方法，避免手写 SQL
   - 事务使用 `@Transactional` 注解

8. **字段变更同步**
   - 后端入参和出参新增、删除字段时，必须同步检查前端代码

---

### 前端服务（Vue3 + TypeScript）

1. **组件命名规范**
   - 组件名使用 PascalCase，如 `UserList.vue`

2. **代码风格**
   - 使用 TypeScript，添加类型定义
   - 使用 Composition API

3. **API 请求规范**
   - ✅ 使用封装的 `request` 实例
   - ❌ 不直接使用 axios

4. **状态管理**
   - 使用 Pinia 进行全局状态管理

5. **组件通信**
   - 父子组件使用 props 和 emits
   - 跨层级组件使用 provide/inject 或 Pinia

6. **样式规范**
   - 使用 SCSS，遵循 BEM 命名规范
   - 组件样式使用 scoped 属性

7. **性能优化**
   - 使用 `v-show` 替代 `v-if` 用于频繁切换的元素
   - 列表渲染使用 `key` 属性

---

### Agent 服务（Python）

1. **代码风格**
   - 遵循 PEP 8 代码规范
   - 使用 type hints（类型提示）
   - 使用 IDE 的自动格式化功能

2. **API 请求规范**
   - ✅ 使用封装的 `PlatformApiClient`
   - ❌ 不直接使用 aiohttp/requests

3. **异步编程**
   - 使用 `async/await` 语法
   - 避免阻塞调用，使用异步版本的库
   - 合理使用 `asyncio.sleep()` 替代 `time.sleep()`

4. **日志规范**
   - 使用 Python `logging` 模块
   - **账号专用日志**：流媒体账号日志存储在 `logs/stream_log/stream_账号名.log`，游戏账号日志存储在 `logs/game_log/game_账号名_YYYY-MM-DD.log`
   - **日志轮转策略**：
     - 流媒体日志：按大小轮转（5MB/文件，保留3个备份）
     - 游戏日志：按天轮转（保留30天）
   - **日志格式**：使用 JSON 格式便于后续分析

5. **配置管理**
   - 使用 YAML 配置文件管理配置项
   - 配置文件路径：`configs/agent.yaml`
   - 支持打包后运行时动态读取配置

6. **错误处理**
   - 使用 try-except 捕获异常
   - 自定义异常类
   - 异常信息需包含上下文（任务ID、账号信息等）

7. **WebSocket 通信**
   - 实现断线重连机制（指数退避策略）
   - 心跳保活（每30秒发送一次）
   - 消息序列化使用 JSON 格式

8. **自动化流程设计**
   - **步骤分离原则**：将复杂流程分解为独立步骤（如登录、连接、解码、游戏）
   - **步骤文件命名**：`stepN_功能描述.py`（如 `step1_stream_account_login.py`）
   - **聚焦验证原则**：修改某个步骤后仅验证该步骤功能，不做全流程验证
   - **上下文传递**：使用 `AgentTaskContext` 在步骤间传递数据

9. **模块化设计**
   - 每个模块职责单一
   - 使用工厂模式创建专用日志记录器
   - 避免模块间循环依赖

10. **代码复用性**
    - 提取公共逻辑到工具类
    - 使用装饰器处理重复逻辑
    - 遵循 DRY 原则

11. **密码安全**
    - 禁止日志中打印密码等敏感信息
    - 使用加密存储账号密码
    - 传输使用 HTTPS/WSS 协议

12. **并发安全**
    - **任务上下文隔离**：每个任务必须使用独立的 `AgentTaskContext` 实例，禁止共享上下文对象
    - **窗口隔离**：每个窗口操作必须绑定到特定的任务上下文，禁止跨任务访问窗口资源
    - **线程安全**：使用 `asyncio.Lock` 保护共享资源的并发访问
    - **状态管理**：避免使用全局变量存储任务状态，所有状态必须存储在任务上下文中
    - **资源清理**：任务完成或取消时必须释放所有窗口句柄和捕获资源
    - **并发控制**：限制同时执行的任务数量，防止资源耗尽

---

## 通用规范

### 安全规范

1. **密码安全**
   - 禁止明文存储密码，使用 AES 加密
   - 密码传输使用 HTTPS/WSS 协议

2. **敏感数据处理**
   - 日志中禁止打印敏感信息
   - API 响应中不应返回不必要的敏感数据

3. **XSS 防护**
   - 前端输入框注意 XSS 风险
   - 后端对用户输入进行校验和过滤

4. **SQL 注入防护**
   - 使用参数化查询或 ORM 框架
   - 禁止拼接 SQL 字符串

5. **认证与授权**
   - 使用 JWT Token 进行身份认证
   - 最小权限原则

---

### 测试规范

1. **单元测试**
   - 核心业务逻辑必须编写单元测试
   - 测试覆盖率目标：核心模块 ≥ 80%

2. **集成测试**
   - 测试 API 接口的完整调用链路

3. **测试命名规范**
   - 测试类命名：`{ClassName}Test`
   - 测试方法命名：`test{MethodName}_{Scenario}_{ExpectedResult}`

4. **测试数据**
   - 使用独立的测试数据库
   - 避免使用真实生产数据

---

### 版本控制规范

1. **分支管理**
   - `main`：生产环境
   - `develop`：开发主分支
   - `feature/*`：功能开发
   - `bugfix/*`：bug 修复
   - `hotfix/*`：紧急修复

2. **提交规范**
   - 格式：`[类型] 描述`
   - 类型：feat、fix、docs、style、refactor、test、chore

3. **代码审查**
   - 所有代码提交必须经过代码审查
   - 至少需要一位审核人批准

---

### 部署运维规范

1. **环境配置**
   - 区分开发、测试、预发布、生产环境
   - 使用环境变量管理敏感配置

2. **Docker 镜像**
   - 使用多阶段构建
   - 镜像命名规范：`bend-{service}:{version}`

3. **日志规范**
   - 统一日志格式
   - 日志级别：DEBUG、INFO、WARN、ERROR

4. **健康检查**
   - 为每个服务配置健康检查接口

---

### 代码设计规范

1. **代码复用性**
   - 提取公共逻辑到工具类
   - 遵循 DRY 原则

2. **扩展性设计**
   - 使用接口/抽象类定义契约
   - 开闭原则

3. **步骤明确性**
   - 复杂业务流程分解为清晰的步骤
   - 每个方法职责单一

4. **常量与枚举规范**
   - 使用常量类管理魔法值
   - 状态值、错误码使用枚举定义

5. **设计模式应用**
   - 工厂模式、单例模式、观察者模式、模板方法模式

---

## 项目概述

Bend Platform 是一个商户自动化服务平台，支持：
- 商户管理、流媒体账号管理、游戏账号管理
- Xbox 主机管理、自动化任务、激活码管理

**服务端口：**
| 服务 | 端口 |
|------|------|
| Gateway | 8060 |
| Platform | 8061 |
| Frontend | 3090 |

---

## 一、Agent 与平台通信协议

### 1.0 网关层 (Gateway)

#### 1.0.1 网关配置

**配置文件：** `bend-gateway/src/main/resources/application.yml`

#### 1.0.2 网关功能

| 功能 | 说明 |
|------|------|
| IP 过滤 | 支持白名单/黑名单 |
| 限流 | 基于 Redis 的令牌桶算法 |
| 路由转发 | 将 `/api/**` 请求转发到 Platform (8061) |
| 熔断 | Circuit Breaker 保护后端服务 |

#### 1.0.3 网关错误响应

| HTTP 状态码 | 说明 |
|------------|------|
| 403 | IP 被禁止访问 |
| 429 | 请求过于频繁 |
| 502/504 | 后端服务不可用 |

### 1.1 通信方式

| 方式 | 用途 |
|------|------|
| WebSocket | 实时双向通信 |
| HTTP REST | Agent 回调平台 |

### 1.2 WebSocket 连接

**连接地址：** `ws://{gateway_host}:8060/ws/agent/{agentId}?agentSecret={secret}`

### 1.3 心跳机制

- Agent 发送频率：每 30 秒一次
- 平台超时时间：60 秒

### 1.4 消息类型

| 消息类型 | 方向 | 说明 |
|---------|------|------|
| task | 平台 → Agent | 下发自动化任务 |
| heartbeat | Agent → 平台 | 心跳保活 |
| heartbeat_ack | 平台 → Agent | 心跳确认 |
| task_ack | Agent → 平台 | 任务接收确认 |

---

## 二、任务下发协议

### 2.1 任务消息格式

```json
{
  "type": "task",
  "data": {
    "taskId": "task_xxx",
    "type": "automation",
    "streamingAccount": {...},
    "gameAccounts": [...],
    "xboxHosts": [...]
  }
}
```

### 2.2 任务确认

```json
{
  "type": "task_ack",
  "data": {
    "taskId": "task_xxx",
    "status": "accepted"
  }
}
```

---

## 三、HTTP 回调接口

### 3.1 获取游戏账号状态

**接口：** `GET /api/task/{taskId}/game-accounts/status`

### 3.2 上报比赛完成

**接口：** `POST /api/task/{taskId}/match/complete`

### 3.3 上报任务进度

**接口：** `POST /api/task/{taskId}/progress`

### 3.4 上报游戏账号完成

**接口：** `POST /api/task/{taskId}/game-account/{gameAccountId}/complete`

### 3.5 重置每日比赛计数

**接口：** `POST /api/task/daily-match-count/reset`

---

## 四、任务执行流程

```
1. Agent 连接 WebSocket
2. 发送心跳
3. 接收任务消息
4. 回复任务确认
5. 获取账号列表
6. 对每个游戏账号执行比赛
7. 上报比赛完成
8. 上报账号完成
9. 上报任务完成
10. 任务结束
```

---

## 五、数据库规范

### 5.1 表命名规范

- 商户相关：`merchant_*`
- 流媒体账号：`streaming_account`
- 游戏账号：`game_account`
- Xbox 主机：`xbox_host`
- 任务：`task`
- 激活码：`activation_code`

### 5.2 字段命名规范

- 主键：`id`
- 创建时间：`created_time`
- 更新时间：`updated_time`
- 逻辑删除：`deleted`
- 状态：`status`

---

## 六、API 响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

**错误码：**
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

**配置文件位置：** `bend-agent/configs/agent.yaml`

**关键配置项：**
```yaml
backend:
  base_url: 'http://localhost:8061'
  ws_url: 'ws://localhost:8061/ws/agents'

agent:
  heartbeat_interval: 30
  reconnect_delay: 5
  max_reconnect_attempts: 10
```

---

## 八、最佳实践

### 8.1 断线重连
- 使用指数退避策略

### 8.2 任务超时
- 默认任务超时时间：3600 秒

### 8.3 状态同步
- 使用 `task_game_account_status` 表跟踪状态

### 8.4 并发控制
- 配置最大并发任务数

### 8.5 异常处理
- 遇到错误记录日志并继续执行其他任务

---

## 九、版本历史

| 版本 | 日期 | 说明 |
|-----|------|------|
| 1.0 | 2026-05-13 | 初始版本 |

---

## 十、相关文档

- [API 文档](bend-platform-api.json)
- [数据库脚本](bend-platform/db/schema.sql)
- [部署文档](docker/DEPLOY.md)
- [Agent 文档](bend-agent/README.md)