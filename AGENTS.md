# Bend Platform - Agent 全局技能文档

---

## 📋 文档说明

**版本**: 3.0  
**最后更新**: 2026-06-02  
**适用范围**: Bend Platform 后端服务（Java）、网关（Java）、前端服务（Vue3）、Agent服务（Python）

---

## ⚠️ 核心原则（✅ 必须遵守）

| 优先级 | 原则 | 说明 |
|--------|------|------|
| P0 | **前瞻设计** | 编写代码时考虑未来需求变化及关联模块影响 |
| P0 | **双向适配** | 修改后端需同步检查前端，修改前端需同步检查后端 |
| P0 | **部署验证** | 代码改动后必须通过 Docker Compose 重新部署验证 |
| P1 | **聚焦验证** | 仅验证新增或改动的功能模块，不做全流程验证 |

---

## 🚀 快速开始

### Docker Compose 验证（✅ 必须遵守）

```bash
# 完整环境（MySQL + Redis + 后端 + 网关 + 前端）
docker compose -f docker/docker-compose.yml --profile full up -d --build

# 仅核心服务（Redis + 后端 + 网关，不含 MySQL/前端）
docker compose -f docker/docker-compose.yml --profile core up -d --build

# 单独构建服务
docker compose -f docker/docker-compose.yml --profile full up -d --build backend
docker compose -f docker/docker-compose.yml --profile full up -d --build gateway
docker compose -f docker/docker-compose.yml --profile full up -d --build frontend

# 检查服务状态
docker compose -f docker/docker-compose.yml ps

# 查看日志
docker compose -f docker/docker-compose.yml logs -f backend
```

### 日志检查清单（✅ 必须遵守）

- [ ] 部署完成后检查各服务日志
- [ ] 确认无 ERROR 或 Exception
- [ ] 用户反馈错误时主动读取容器日志分析

### 数据库变更规范（✅ 必须遵守）

- 迁移脚本位置：`bend-platform/db/migration/`
- 全量建表脚本：`bend-platform/db/schema.sql`
- 每次创建迁移脚本后必须同步更新 `schema.sql`

---

## 📁 项目结构

### 网关服务 (bend-gateway)

```
bend-gateway/
├── src/main/java/com/bend/gateway/
│   ├── filter/         # 限流、IP 过滤
│   └── config/         # CORS 等配置
└── src/main/resources/
    └── application.yml # 路由 :8060 → backend:8061
```

### 后端服务 (bend-platform)

```
bend-platform/
├── src/main/java/com/bend/platform/
│   ├── controller/     # REST API 控制层
│   ├── service/        # 业务逻辑层（接口+实现）
│   ├── repository/     # 数据访问层（MyBatis Mapper）
│   ├── entity/         # 数据库实体类
│   ├── dto/            # 数据传输对象
│   ├── config/         # 配置类（过滤器、拦截器等）
│   ├── websocket/      # WebSocket 端点
│   ├── exception/      # 异常处理
│   ├── task/           # 定时任务
│   └── util/           # 工具类
├── src/main/resources/
│   ├── application.yml # 应用配置
│   └── mapper/         # MyBatis XML 映射
└── db/                 # 数据库迁移脚本
```

### Agent 服务 (bend-agent)

```
bend-agent/
├── src/agent/
│   ├── automation/     # ✅ 核心四步骤实现（必须在此目录开发）
│   │   ├── step1_stream_account_login.py   # 步骤一：MSAL认证(Token自动刷新)
│   │   ├── step2_xbox_streaming.py         # 步骤二：Xbox连接+PlaySession
│   │   ├── step3_streaming_init.py          # 步骤三：SDL窗口+GPU捕获
│   │   └── step4_game_automation.py        # 步骤四：游戏自动化
│   ├── task/           # 任务调度与上下文管理
│   ├── api/            # WebSocket/HTTP 通信
│   ├── auth/           # Microsoft MSAL 认证
│   ├── xbox/           # Xbox 设备发现、流控制、PlaySession、WebRTC
│   ├── vision/         # 视觉识别、画面捕获、GPU解码
│   │   ├── template_matcher.py      # 基础模板匹配
│   │   └── template_manager.py       # ✅ Streaming模板管理器（新增）
│   ├── windows/        # Windows 窗口管理、SDL自绘窗口
│   ├── core/           # 中央管理与配置
│   ├── game/           # 游戏账号管理、账号切换
│   ├── scene/          # 场景检测（降频+缓存优化）
│   │   ├── scene_detector.py              # 基础场景检测
│   │   └── streaming_scene_detector.py    # ✅ Streaming场景检测器（新增）
│   ├── input/          # 输入控制（pygame手柄、键盘映射）
│   └── utils/          # 工具类
├── configs/            # 配置文件
│   └── scene_schemas.py   # ✅ Streaming场景模板配置（新增）
├── templates/          # ✅ 模板图片目录（需创建）
└── logs/              # 日志目录
```

---

## 🎯 Streaming场景模板匹配规范（✅ 必须遵守）

参考项目：[D:\auto-xbox\streaming\xsrpst.py](file:///D:/auto-xbox/streaming/xsrpst.py)

### 核心组件

| 组件 | 文件路径 | 说明 |
|------|---------|------|
| 场景配置 | [configs/scene_schemas.py](file:///d:/auto-xbox/team-management/bend-agent/configs/scene_schemas.py) | 场景模板配置定义 |
| 场景检测器 | [scene/streaming_scene_detector.py](file:///d:/auto-xbox/team-management/bend-agent/src/agent/scene/streaming_scene_detector.py) | Streaming风格场景识别 |
| 模板管理器 | [vision/template_manager.py](file:///d:/auto-xbox/team-management/bend-agent/src/agent/vision/template_manager.py) | 模板文件加载和缓存 |

### 模板配置规范（✅ 必须遵守）

**配置位置**：`configs/scene_schemas.py`

**模板命名规则**：`{场景ID}.{模板ID}.png`

**示例**：
```
templates/
├── 1.1.png    # 场景1的模板1
├── 2.1.png    # 场景2的模板1
├── 2.2.png    # 场景2的模板2
└── ...
```

### 场景配置格式

```python
[
    场景ID,           # 1, 2, 3...
    场景宽度,        # 960
    场景高度,        # 540

    模板ID,          # 1, 2, 3...
    模板左上X,        # 模板区域
    模板左上Y,
    模板右下X,
    模板右下Y,

    搜索区域ID,      # 搜索区域
    搜索区域左上X,
    搜索区域左上Y,
    搜索区域右下X,
    搜索区域右下Y,

    相似度阈值,      # 90 (百分比)
    算法编号          # 3 (TM_CCORR_NORMED)
]
```

### 推荐算法

| 编号 | 算法 | 推荐度 |
|------|------|--------|
| **3** | **TM_CCORR_NORMED** | ⭐ **推荐** |
| 5 | TM_CCOEFF_NORMED | 高 |
| 1 | TM_SQDIFF_NORMED | 中 |

### 使用示例

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
    print(f"场景: {result.scene_id}, 置信度: {result.confidence:.2f}")
```

### 场景清单（23个场景）

| 分类 | 场景ID | 说明 |
|------|--------|------|
| **UI导航** | 1-9 | 主页、西瓜主页、档案和系统、关机/重启等 |
| **账号登录** | 10-23 | 登录页面、小键盘输入等 |

详细场景配置见：[bend-agent/docs/TEMPLATE_CONFIG_GUIDE.md](file:///d:/auto-xbox/team-management/bend-agent/docs/TEMPLATE_CONFIG_GUIDE.md)

---

## 🛠️ 开发代码规范

### 后端服务（Java/Spring Boot）

#### ✅ 必须遵守

| 规则 | 说明 |
|------|------|
| 统一 import | 在类顶部使用 `import com.example.ClassName;` |
| 清理未使用 import | 使用 IDE 的 Optimize Imports |
| 代码格式化 | 使用 IDE 格式化工具确保格式一致 |
| 代码注释 | 为关键方法、类、接口添加英文注释 |
| 命名规范 | 类名 PascalCase，方法/变量 camelCase |
| 避免魔法值 | 使用常量或枚举定义 |
| API 响应规范 | 统一使用 `ApiResponse<T>` 包装 |
| 数据库操作 | 使用 MyBatis Plus，避免手写 SQL |
| 事务管理 | 使用 `@Transactional` 注解 |

#### ⚠️ 数据库操作注意事项

```java
// ✅ 正确：逻辑删除场景下的唯一键处理
// 对于可能被软删除后重新创建的记录（如Xbox主机），建议使用物理删除
@Delete("DELETE FROM xbox_host WHERE id = #{id}")
void physicalDeleteById(Long id);

// ⚠️ 错误：逻辑删除后再次插入会触发唯一键冲突
@TableLogic
private Integer deleted;
```

#### 代码编译检查清单（✅ 必须通过）

- [ ] **方法重复定义检查**：同一类中不允许存在方法名和参数类型完全相同的方法
- [ ] **导入语句检查**：使用的所有类必须在文件顶部正确导入
- [ ] **依赖注入检查**：使用 `@RequiredArgsConstructor` 注入的依赖必须声明为 `final`
- [ ] **枚举引用检查**：使用枚举值前必须确认该枚举值存在
- [ ] **异常构造检查**：`BusinessException` 构造函数必须传入 `ResultCode` 枚举

---

### 前端服务（Vue3 + JavaScript）

#### ✅ 必须遵守

| 规则 | 说明 |
|------|------|
| 组件命名 | PascalCase，如 `UserList.vue` |
| 代码风格 | 使用 JavaScript 和 Composition API（`<script setup>`） |
| API 请求 | 使用封装的 `request` 实例，禁止直接使用 axios |
| 状态管理 | 使用 Pinia |
| 组件通信 | 父子组件使用 props/emits，跨层级使用 provide/inject 或 Pinia |
| 样式规范 | 使用 CSS + scoped；组件样式保持 BEM 命名习惯 |
| 性能优化 | 列表渲染使用 `key` 属性 |

> 说明：当前代码库为 JavaScript + CSS。TypeScript/SCSS 迁移为可选后续工作，新增代码应遵循上表实际栈。

---

### Agent 服务（Python）

#### ✅ 必须遵守

##### 1. 代码风格
- 遵循 PEP 8 规范
- 使用 type hints（类型提示）
- 使用 IDE 自动格式化

##### 2. API 请求规范
- ✅ 使用封装的 `PlatformApiClient`
- ❌ 禁止直接使用 aiohttp/requests

##### 3. 异步编程
- 使用 `async/await` 语法
- 使用 `asyncio.sleep()` 替代 `time.sleep()`

##### 4. 日志规范
- 使用 Python `logging` 模块
- 流媒体账号日志：`logs/stream_log/stream_账号名.log`
- 游戏账号日志：`logs/game_log/game_账号名_YYYY-MM-DD.log`
- **日志格式**：JSON 格式便于分析

##### 5. 认证规范

```python
# ✅ 正确：HTTP请求时对secret进行Base64编码
import base64

encoded_secret = base64.b64encode(agent_secret.encode('utf-8')).decode('utf-8')
headers['X-Agent-Secret'] = encoded_secret

# ❌ 错误：直接发送原始secret会导致401认证失败
headers['X-Agent-Secret'] = agent_secret
```

##### 6. 资源清理规范

```python
# 优雅关闭顺序（✅ 必须遵守）
# 1. 关闭 API 客户端
# 2. 断开 WebSocket 连接  
# 3. 停止任务调度器
# 4. 释放窗口句柄和捕获资源
```

#### 🔧 自动化流程核心规范（✅ 必须遵守）

**所有自动化流程开发必须在 `automation/` 目录下进行！**

| 步骤 | 文件名 | 核心职责 | 依赖模块 |
|------|--------|----------|----------|
| 步骤一 | `step1_stream_account_login.py` | MSAL设备码认证获取Xbox令牌(Token自动刷新) | `auth/`, `api/` |
| 步骤二 | `step2_xbox_streaming.py` | 发现并连接Xbox主机(PlaySession+SDP) | `xbox/` |
| 步骤三 | `step3_streaming_init.py` | 初始化画面捕获能力(SDL+GPU) | `vision/`, `windows/` |
| 步骤四 | `step4_game_automation.py` | 执行游戏比赛并上报状态(场景优化+手柄控制) | `vision/`, `game/`, `scene/`, `input/` |

**步骤文件结构模板（✅ 必须遵守）**

```python
"""
步骤N：功能名称
================

功能说明：
- 核心功能描述
- 技术实现要点

方法拆分：
- stepN_execute_xxx(): 主入口函数（必须）
- _helper_function(): 辅助函数（前缀下划线）

作者：技术团队
版本：x.x
"""

import asyncio
from typing import Callable, Optional, Dict, Any

from ..core.logger import get_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext, StepNResult, TaskStepStatus

async def stepN_execute_xxx(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str], None]
) -> StepNResult:
    """
    步骤N执行：功能名称
    
    参数：
    - context: 任务上下文（包含前序步骤结果）
    - check_cancel: 取消检查函数（定期调用检测任务是否被取消）
    - report_progress: 进度上报函数
    
    返回：
    - StepNResult: 步骤执行结果
    """
    # 1. 获取日志记录器
    logger = get_logger(f'stepN_xxx_{context.task_id}')
    stream_logger = get_stream_logger(context.streaming_account_email)
    
    # 2. 更新步骤状态并上报
    context.update_step_status("stepN", TaskStepStatus.RUNNING, "步骤开始...")
    await report_progress(context.task_id, "STEPN", "RUNNING", "步骤开始...")
    
    # 3. 主流程逻辑
    try:
        # 定期检查取消
        if check_cancel():
            return StepNResult(success=False, error_code="CANCELLED", message="任务被取消")
        
        # 执行核心逻辑...
        
        # 完成状态
        context.update_step_status("stepN", TaskStepStatus.COMPLETED, "步骤完成")
        await report_progress(context.task_id, "STEPN", "COMPLETED", "步骤完成")
        return StepNResult(success=True, message="步骤完成")
        
    except asyncio.CancelledError:
        context.update_step_status("stepN", TaskStepStatus.SKIPPED, "任务被取消")
        return StepNResult(success=False, error_code="CANCELLED", message="任务被取消")
        
    except Exception as e:
        context.update_step_status("stepN", TaskStepStatus.FAILED, str(e))
        await report_progress(context.task_id, "STEPN", "FAILED", str(e))
        return StepNResult(success=False, error_code="EXCEPTION", message=str(e))
```

**步骤间数据传递规范**

| 步骤 | 写入上下文 | 读取上下文 |
|------|-----------|-----------|
| 步骤一 | `microsoft_tokens`, `xbox_tokens` | `streaming_account_email`, `streaming_account_password` |
| 步骤二 | `current_xbox`, `xbox_session` | `xbox_tokens` |
| 步骤三 | `frame_capture`, `scene_detector` | `xbox_session`, `current_xbox` |
| 步骤四 | `matches_completed_today` | `frame_capture`, `scene_detector`, `game_accounts`, `task_type` |

**⚠️ 任务类型生效规则（✅ 必须遵守）**

> **核心规则**：任务类型（`task_type`）**仅在步骤四（`step4_game_automation.py`）中生效**，且必须在**确认当前游戏账号登录成功后**才能应用。

**任务类型生效流程**：

```
┌─────────────────────────────────────────────────────────────┐
│                   步骤四：游戏比赛自动化                    │
├─────────────────────────────────────────────────────────────┤
│                                                           │
│   遍历游戏账号列表                                         │
│        │                                                  │
│        ▼                                                  │
│   ┌──────────────────┐                                    │
│   │ 登录游戏账号      │                                    │
│   │ （模拟按键操作）   │                                    │
│   └────────┬─────────┘                                    │
│            │                                              │
│            ▼                                              │
│   ┌──────────────────┐                                    │
│   │ 确认登录成功      │ ←── 画面检测验证（使用Streaming场景检测器）│
│   └────────┬─────────┘                                    │
│            │                                              │
│            ▼                                              │
│   ┌──────────────────┐                                    │
│   │ 应用任务类型      │ ←── task_type 在此处生效          │
│   │ （比赛模式选择）   │                                    │
│   └────────┬─────────┘                                    │
│            │                                              │
│            ▼                                              │
│   执行指定场比赛（默认3场/账号）                           │
│                                                           │
└─────────────────────────────────────────────────────────────┘
```

**任务类型应用原则**：
- **时机**：必须在游戏账号登录确认后应用，禁止提前使用
- **位置**：仅在 `step4_game_automation.py` 中处理，其他步骤不应涉及任务类型逻辑
- **验证**：使用画面检测确认游戏账号登录状态后，才能根据任务类型执行相应操作

**四步骤串行执行规则**

```
步骤一 ──► 步骤二 ──► 步骤三 ──► 步骤四
   │          │          │          │
   └──────────┴──────────┴──────────┘
        (任一步骤失败，整个任务失败)
```

#### 🔗 调用链规范

```
WebSocket消息 ──► TaskExecutor ──► AutomationScheduler ──► AutomationTask
                                                               │
                    ┌───────────────┼───────────────┐          │
                    ▼               ▼               ▼          ▼
               step1_stream      step2_xbox      step3_init   step4_game
               _account_login    _streaming      _streaming   _automation
```

#### 🔧 场景模板匹配规范

详见上方 **"🎯 Streaming场景模板匹配规范"** 章节。

---

## 🔒 安全规范

### ✅ 必须遵守

| 规则 | 说明 |
|------|------|
| 密码安全 | 使用 AES 加密存储，HTTPS/WSS 传输 |
| 敏感数据 | 禁止日志打印密码等敏感信息 |
| XSS 防护 | 前端输入校验，后端过滤 |
| SQL 注入 | 使用参数化查询，禁止拼接 SQL |
| 认证授权 | 使用 JWT Token，最小权限原则 |

---

## 🧪 测试规范

### ✅ 必须遵守

| 规则 | 说明 |
|------|------|
| 单元测试 | 核心业务逻辑必须编写单元测试 |
| 测试覆盖率 | 核心模块 ≥ 80% |
| 测试命名 | 类名：`{ClassName}Test`，方法名：`test{MethodName}_{Scenario}_{ExpectedResult}` |
| 测试数据 | 使用独立测试数据库，禁止使用生产数据 |

---

## 📦 版本控制规范

### ✅ 必须遵守

| 分支 | 用途 |
|------|------|
| `main` | 生产环境 |
| `develop` | 开发主分支 |
| `feature/*` | 功能开发 |
| `bugfix/*` | Bug 修复 |
| `hotfix/*` | 紧急修复 |

**提交规范**：`[类型] 描述`
- 类型：feat、fix、docs、style、refactor、test、chore

---

## 📊 部署运维规范

### ✅ 必须遵守

| 规则 | 说明 |
|------|------|
| 环境配置 | 区分开发、测试、预发布、生产环境 |
| Docker 镜像 | 多阶段构建，命名规范：`bend-{service}:{version}` |
| 日志规范 | 统一格式，级别：DEBUG、INFO、WARN、ERROR |
| 健康检查 | 每个服务配置健康检查接口 |

---

## 🎯 代码设计规范

### ✅ 必须遵守

| 规则 | 说明 |
|------|------|
| 代码复用 | 提取公共逻辑到工具类，遵循 DRY 原则 |
| 扩展性设计 | 使用接口/抽象类定义契约，开闭原则 |
| 职责单一 | 每个方法职责明确 |
| 常量枚举 | 使用常量类管理魔法值，状态值使用枚举 |
| 设计模式 | 合理应用工厂模式、单例模式、观察者模式、模板方法模式 |

---

## 🔄 与平台通信协议

### WebSocket 连接

**地址**：`ws://{gateway_host}:8060/ws/agent/{agentId}?agentSecret={secret}`  
**认证**：`agentSecret` 通过 URL 参数直接传递（原始字符串）

### HTTP 认证

**请求头**：
- `X-Agent-Id`：Agent ID（原始字符串）
- `X-Agent-Secret`：Agent Secret（**必须 Base64 编码**）

**后端验证逻辑**：
```java
String decodedSecret = new String(Base64.getDecoder().decode(agentSecret), StandardCharsets.UTF_8);
```

### 消息类型

| 类型 | 方向 | 说明 |
|------|------|------|
| `task` | 平台→Agent | 下发自动化任务 |
| `heartbeat` | Agent→平台 | 心跳保活 |
| `heartbeat_ack` | 平台→Agent | 心跳确认 |
| `task_ack` | Agent→平台 | 任务接收确认 |
| `task_progress` | Agent→平台 | 任务进度上报 |

---

## 📝 API 响应格式

```json
{
  "code": 200,
  "message": "success",
  "data": { ... }
}
```

**错误码**：

| 错误码 | 说明 |
|--------|------|
| 200 | 成功 |
| 400 | 请求参数错误 |
| 401 | 认证失败 |
| 403 | 权限不足 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |

---

## ⚙️ Agent 配置

**配置文件**：`bend-agent/configs/agent.yaml`

```yaml
backend:
  base_url: 'http://localhost:8060'
  ws_url: 'ws://localhost:8060/ws/agent'

agent:
  heartbeat_interval: 30      # 心跳间隔（秒）
  reconnect_delay: 5          # 重连延迟（秒）
  max_reconnect_attempts: 10  # 最大重连次数

template:
  dir: 'templates'            # 模板目录
  threshold: 0.8              # 匹配阈值
  cache_enabled: true         # 启用缓存
```

---

## 🌟 最佳实践

| 实践 | 说明 |
|------|------|
| 断线重连 | 使用指数退避策略 |
| 任务超时 | 默认 3600 秒 |
| 状态同步 | 使用 `task_game_account_status` 表跟踪 |
| 并发控制 | 配置最大并发任务数 |
| 异常处理 | 记录日志并继续执行其他任务 |
| 模板管理 | 使用Streaming模板管理器，预加载常用模板 |
| 场景检测 | 使用Streaming场景检测器，支持多区域匹配 |

---

## 📅 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-05-13 | 初始版本 |
| 2.0 | 2026-05-16 | 添加认证规范、资源清理规范 |
| 2.1 | 2026-05-21 | 优化文档结构、添加检查清单、完善代码模板 |
| 3.0 | 2026-05-30 | 添加优化模块说明：GPU解码、SDL窗口、场景检测优化、手柄信号发送 |
| 3.1 | 2026-06-02 | 添加Streaming场景模板匹配规范（scene_schemas.py、streaming_scene_detector.py、template_manager.py）|

---

## 📚 相关文档

- [API 文档](bend-platform-api.json)
- [数据库脚本](bend-platform/db/schema.sql)
- [部署文档](docker/DEPLOY.md)
- [Agent 文档](bend-agent/README.md)
- [模板配置指南](bend-agent/docs/TEMPLATE_CONFIG_GUIDE.md)

---

## 🤖 AI 工具执行指南

### 规则优先级说明

| 标记 | 优先级 | 说明 |
|------|--------|------|
| ✅ | P0 | 必须遵守，违反将导致任务失败 |
| ⚠️ | P1 | 建议遵守，违反将发出警告 |
| 💡 | P2 | 最佳实践，建议参考 |

### 自动化规则（供工具解析）

```json
{
  "rules": [
    {
      "id": "R001",
      "name": "API请求规范",
      "priority": "P0",
      "type": "must_follow",
      "check": "使用PlatformApiClient而非直接使用aiohttp",
      "location": ["src/agent/api/"]
    },
    {
      "id": "R002",
      "name": "日志规范",
      "priority": "P1",
      "type": "recommended",
      "check": "使用JSON格式日志",
      "location": ["src/agent/core/"]
    },
    {
      "id": "R003",
      "name": "自动化步骤位置",
      "priority": "P0",
      "type": "must_follow",
      "check": "四步骤文件必须放在automation/目录下",
      "location": ["src/agent/automation/"]
    },
    {
      "id": "R004",
      "name": "HTTP认证编码",
      "priority": "P0",
      "type": "must_follow",
      "check": "X-Agent-Secret必须Base64编码",
      "location": ["src/agent/api/platform_api_client.py"]
    },
    {
      "id": "R005",
      "name": "代码复用",
      "priority": "P1",
      "type": "recommended",
      "check": "避免代码重复，提取公共逻辑到工具类",
      "location": ["src/agent/"]
    },
    {
      "id": "R006",
      "name": "任务类型生效位置",
      "priority": "P0",
      "type": "must_follow",
      "check": "task_type仅在step4_game_automation.py中处理",
      "location": ["src/agent/automation/step4_game_automation.py"]
    },
    {
      "id": "R007",
      "name": "任务类型生效时机",
      "priority": "P0",
      "type": "must_follow",
      "check": "task_type必须在确认游戏账号登录成功后才能应用",
      "location": ["src/agent/automation/step4_game_automation.py"]
    },
    {
      "id": "R008",
      "name": "Streaming场景模板匹配",
      "priority": "P0",
      "type": "must_follow",
      "check": "使用configs/scene_schemas.py配置模板，模板文件命名为{场景ID}.{模板ID}.png",
      "location": ["configs/scene_schemas.py", "src/agent/scene/streaming_scene_detector.py"]
    }
  ]
}
```

---

*文档结束*
