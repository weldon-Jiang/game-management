# Bend Platform - Xbox 自动化管理系统

## 系统概述

Bend Platform 是一个企业级 Xbox 云游戏自动化管理平台，采用多租户架构，支持商户独立管理资源。系统由三大模块组成：后端管理平台、前端 Web 应用和客户端 Agent 自动化程序，通过 HTTP API 和 WebSocket 实现实时通信与任务调度。

---

## 文档导航

| 文档 | 说明 |
|------|------|
| [开发环境搭建](docs/development.md) | 环境要求、项目结构、启动调试、代码规范 |
| [用户操作指南](docs/user-guide.md) | 商户注册、Agent管理、任务操作 |
| [系统流程说明](docs/flow.md) | 业务流程、数据流向 |
| [数据库ER图](db/ER_diagram.md) | 表关系与ER图 |

---

## 核心功能

| 功能 | 说明 |
|------|------|
| 多商户管理 | 多租户隔离，商户组管理，子账号角色权限 |
| 流媒体账号管理 | Xbox Game Pass 等流媒体服务账号批量导入与管理 |
| Xbox主机管理 | 主机设备注册、MAC地址绑定、锁定机制 |
| Agent自动化控制 | Windows客户端，控制Xbox云游戏自动化任务 |
| 游戏账号管理 | 游戏账号绑定、切换和时长管理 |
| 订阅与计费 | 订阅计划管理、充值卡、激活码、积分系统、VIP等级 |
| 自动化任务调度 | 高并发任务执行，支持100+并发任务 |
| 实时监控 | 系统监控、Agent心跳检测、告警机制 |
| 模板管理 | 图像模板管理，支持自动化场景识别 |
| 审计与安全 | 操作审计日志、幂等性校验、AES加密、JWT认证 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                     前端 (bend-platform-web)                        │
│              Vue 3 + Element Plus + Vite + Pinia                    │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP / WebSocket
┌────────────────────────────▼────────────────────────────────────────┐
│                     后端 (bend-platform)                             │
│              Spring Boot 3.2 + MyBatis-Plus + Redis                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  REST API    │  │  WebSocket   │  │  定时任务                │  │
│  │  Controller  │  │  Endpoint    │  │  心跳/超时检测           │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                     MySQL 8.0 + Redis 6.0                           │
└────────────────────────────┬────────────────────────────────────────┘
                             │ HTTP API / WebSocket
┌────────────────────────────▼────────────────────────────────────────┐
│                     Agent (bend-agent)                               │
│              Python 3.8+ + asyncio + OpenCV                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ CentralManager│  │ TaskExecutor │  │ AutomationScheduler     │  │
│  │   核心管理    │  │  任务执行    │  │    自动化调度(100+并发)  │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ Vision       │  │ InputControl │  │ SceneDetector            │  │
│  │ 帧捕获/匹配  │  │ 鼠标键盘手柄 │  │    场景自动识别          │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
│                     Windows 10/11                                    │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 技术栈

| 模块 | 技术 | 版本 |
|------|------|------|
| **后端平台** | Spring Boot | 3.2.5 |
| | MyBatis-Plus (Spring Boot 3) | 3.5.5 |
| | MySQL Connector | 8.3.0 |
| | Spring Data Redis + Lettuce | - |
| | JWT (jjwt) | 0.12.5 |
| | SpringDoc OpenAPI | 2.3.0 |
| | Lombok | 1.18.30 |
| | Dotenv Java | 3.0.2 |
| **前端** | Vue | 3.5.x |
| | Vite | 8.0.x |
| | Element Plus | 2.13.x |
| | Pinia | 3.0.x |
| | Vue Router | 4.6.x |
| | Axios | 1.15.x |
| | Vitest | 2.0.x |
| | Playwright | 1.45.x |
| **Agent** | Python | 3.8+ |
| | aiohttp | 3.8+ |
| | websockets | 10.0+ |
| | OpenCV | 4.5+ |
| | scikit-image | 0.19+ |
| | PyAutoGUI | 0.9+ |
| | PyCryptodome | 3.15+ |

---

## 项目结构

```
team-management/
├── bend-platform/                  # 后端服务 (Spring Boot)
│   ├── src/main/java/com/bend/platform/
│   │   ├── controller/             # REST API 控制器 (20+)
│   │   ├── service/                # 业务逻辑层
│   │   │   └── impl/               # Service 实现
│   │   ├── repository/             # MyBatis Mapper 数据访问
│   │   ├── entity/                 # 数据库实体
│   │   ├── dto/                    # 数据传输对象
│   │   ├── config/                 # Spring 配置类
│   │   ├── websocket/              # WebSocket 端点与消息服务
│   │   ├── aspect/                 # AOP 切面 (审计日志/幂等性)
│   │   ├── annotation/             # 自定义注解
│   │   ├── enums/                  # 枚举类型
│   │   ├── exception/              # 全局异常处理
│   │   ├── task/                   # 定时任务 (心跳/超时检测)
│   │   └── util/                   # 工具类 (JWT/AES/加密)
│   ├── src/main/resources/
│   │   └── application.yml         # 主配置文件
│   ├── db/                         # 数据库脚本
│   ├── .env.example                # 环境变量示例
│   └── pom.xml                     # Maven 配置
│
├── bend-platform-web/              # 前端应用 (Vue 3)
│   ├── src/
│   │   ├── api/                    # API 接口模块 (15+)
│   │   ├── views/                  # 页面组件
│   │   │   ├── login/              # 登录注册
│   │   │   ├── agent/              # Agent 管理
│   │   │   ├── task/               # 任务管理
│   │   │   ├── merchant/           # 商户管理
│   │   │   ├── streaming/          # 流媒体账号
│   │   │   ├── game/               # 游戏账号
│   │   │   ├── xbox/               # Xbox 主机
│   │   │   ├── activation/         # 激活码
│   │   │   ├── recharge/           # 充值卡
│   │   │   ├── subscription/       # 订阅管理
│   │   │   ├── registration/       # 注册码
│   │   │   ├── user/               # 用户管理
│   │   │   └── common/             # 仪表盘
│   │   ├── components/common/      # 通用组件 (DataTable/ConfirmDialog)
│   │   ├── composables/            # 组合式函数
│   │   ├── stores/                 # Pinia 状态管理
│   │   ├── router/                 # Vue Router 配置
│   │   ├── utils/                  # 工具函数
│   │   ├── styles/                 # 全局样式
│   │   └── tests/                  # 单元/集成/Mock测试
│   ├── e2e/                        # E2E 测试
│   ├── vite.config.js              # Vite 配置
│   └── package.json
│
├── bend-agent/                     # Agent 客户端 (Python)
│   ├── src/agent/
│   │   ├── api/                    # 后端通信 (HTTP/WebSocket/注册)
│   │   ├── auth/                   # Microsoft 认证
│   │   ├── automation/             # 自动化核心
│   │   │   ├── automation_scheduler.py  # 自动化调度器
│   │   │   ├── automation_task.py       # 自动化任务
│   │   │   ├── platform_api_client.py   # 平台API客户端
│   │   │   ├── task_context.py          # 任务上下文
│   │   │   ├── task_window_manager.py   # 窗口管理
│   │   │   ├── step1_stream_account_login.py  # 步骤1: 账号登录
│   │   │   ├── step2_xbox_streaming.py        # 步骤2: Xbox串流
│   │   │   ├── step3_gpu_decode.py             # 步骤3: GPU解码
│   │   │   ├── step4_game_automation.py        # 步骤4: 游戏自动化
│   │   │   └── tests/               # 自动化测试
│   │   ├── core/                   # 核心组件 (配置/日志/管理器/更新)
│   │   ├── game/                   # 游戏账号管理
│   │   ├── input/                  # 输入控制 (鼠标/键盘/手柄)
│   │   ├── scene/                  # 场景检测
│   │   ├── vision/                 # 视觉处理 (帧捕获/模板匹配)
│   │   ├── system/                 # 系统托盘
│   │   ├── task/                   # 任务执行 (流控/执行器)
│   │   ├── utils/                  # 工具类 (加密)
│   │   ├── windows/                # 窗口管理 (串流窗口)
│   │   ├── xbox/                   # Xbox控制 (串流/发现)
│   │   └── main.py                 # 入口文件
│   ├── configs/                    # 配置文件
│   ├── distribution/               # 商户分发包
│   ├── scripts/                    # 打包脚本
│   ├── requirements.txt
│   └── pytest.ini
│
├── db/                             # 数据库脚本与文档
│   ├── schema.sql                  # 建表脚本
│   ├── ER_diagram.md               # ER图
│   └── migration*.sql              # 迁移脚本
│
├── docs/                           # 项目文档
│   ├── development.md              # 开发手册
│   ├── user-guide.md               # 用户手册
│   ├── flow.md                     # 流程说明
│   └── 03_表结构和初始化数据脚本.md
│
└── .github/workflows/              # CI/CD
    ├── agent-automation-ci.yml     # Agent自动化测试流水线
    └── ui-tests.yml                # UI E2E测试流水线
```

---

## 快速开始

### 1. 克隆代码

```bash
git clone <repository-url>
cd team-management
```

### 2. 初始化数据库

```bash
mysql -u root -p
CREATE DATABASE bend_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bend_platform;
SOURCE db/schema.sql;
```

### 3. 启动后端

```bash
cd bend-platform
cp .env.example .env
# 编辑 .env 填入数据库密码、JWT密钥等
mvn spring-boot:run
```

后端启动在 `http://localhost:8090`，API文档在 `http://localhost:8090/swagger-ui.html`

### 4. 启动前端

```bash
cd bend-platform-web
npm install
npm run dev
```

前端开发服务器启动在 `http://localhost:3090`，自动代理 API 请求到后端 `8090` 端口

### 5. 启动 Agent

```bash
cd bend-agent
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
python src/main.py --agent-id <ID> --agent-secret <SECRET> --registration-code <CODE>
```

---

## 环境要求

| 环境 | 版本 | 说明 |
|------|------|------|
| JDK | 17+ | 后端必需 |
| Maven | 3.6+ | 后端编译 |
| Node.js | 16+ | 前端必需 |
| MySQL | 8.0+ | 数据库 |
| Redis | 6.0+ | 缓存/消息队列 |
| Python | 3.8+ | Agent必需 |
| Windows | 10/11 | Agent运行环境 |

---

## 后端环境变量

复制 `bend-platform/.env.example` 为 `.env`，配置以下变量：

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `DB_URL` | 数据库连接URL | `jdbc:mysql://localhost:3306/bend_platform` |
| `DB_USERNAME` | 数据库用户名 | `root` |
| `DB_PASSWORD` | 数据库密码 | - |
| `REDIS_HOST` | Redis地址 | `127.0.0.1` |
| `REDIS_PORT` | Redis端口 | `6379` |
| `REDIS_PASSWORD` | Redis密码 | - |
| `JWT_SECRET` | JWT签名密钥 | - |
| `JWT_EXPIRATION` | JWT过期时间(ms) | `86400000` |
| `AES_SECRET` | AES加密密钥 | - |
| `SERVER_PORT` | 服务端口 | `8090` |
| `CORS_ALLOWED_ORIGINS` | CORS允许的源 | `http://localhost:5173,http://localhost:3090` |

---

## 数据库表结构

共 29 张表，按业务模块分组：

### 商户与用户

| 表名 | 说明 |
|------|------|
| merchant | 商户表 |
| merchant_user | 商户用户表（子账号） |
| merchant_group | 商户组表 |
| merchant_balance | 商户余额表 |
| merchant_registration_code | 商户注册码表 |
| operation_log | 操作审计日志表 |

### 流媒体与游戏

| 表名 | 说明 |
|------|------|
| streaming_account | 串流账号表 |
| streaming_account_login_record | 串流账号Xbox登录记录表 |
| streaming_error_log | 串流错误日志表 |
| game_account | 游戏账号表 |

### Xbox与设备

| 表名 | 说明 |
|------|------|
| xbox_host | Xbox主机表 |
| device_binding | 设备绑定表 |

### Agent与任务

| 表名 | 说明 |
|------|------|
| agent_instance | Agent实例表 |
| agent_version | Agent版本表 |
| task | 任务表 |
| automation_task | 自动化任务表 |
| task_statistics | 任务统计表 |
| automation_usage | 自动化使用量表 |

### 计费与订阅

| 表名 | 说明 |
|------|------|
| activation_code | 激活码表 |
| activation_code_batch | 激活码批次表 |
| recharge_card | 充值卡表 |
| recharge_card_batch | 充值卡批次表 |
| recharge_denomination_config | 充值面额配置表 |
| recharge_record | 充值记录表 |
| point_transaction | 点数交易记录表 |
| subscription | 订阅表 |
| subscription_price | 订阅价格表 |

### 模板与监控

| 表名 | 说明 |
|------|------|
| template | 模板表 |
| system_metrics | 系统监控指标表 |
| system_alert | 系统告警表 |

---

## CI/CD

项目使用 GitHub Actions 进行持续集成：

| 流水线 | 触发条件 | 包含阶段 |
|--------|----------|----------|
| Agent Automation CI/CD | push/PR 到 main/develop | Agent单元测试 → 集成测试 → 性能测试 → 平台单元测试 → UI E2E测试 |
| UI Tests | push/PR | Playwright E2E测试 |

---

## 常用命令

### 后端

```bash
cd bend-platform
mvn clean compile          # 编译
mvn spring-boot:run        # 运行
mvn clean package -DskipTests  # 打包
mvn test                   # 运行测试
```

### 前端

```bash
cd bend-platform-web
npm install                # 安装依赖
npm run dev                # 开发模式
npm run build              # 构建生产版本
npm run lint               # 代码检查
npm run format             # 代码格式化
npm test                   # 单元测试
npm run test:coverage      # 测试覆盖率
npm run test:e2e           # E2E测试
```

### Agent

```bash
cd bend-agent
pip install -r requirements.txt  # 安装依赖
python src/main.py               # 运行
pytest                           # 运行测试
scripts\build.bat                # 打包分发
```

---

## 快速链接

### 开发者
- [开发环境搭建](docs/development.md#开发环境要求)
- [数据库初始化](docs/development.md#数据库)
- [启动调试](docs/development.md#快速入门)
- [测试框架](docs/development.md#测试)
- [代码规范](docs/development.md#代码规范)

### 运维
- [生产部署](docs/development.md#生产环境部署)
- [Nginx配置](docs/development.md#nginx-部署配置)
- [环境变量配置](bend-platform/.env.example)

### 用户
- [登录注册](docs/user-guide.md)
- [商户管理](docs/user-guide.md)
- [Agent管理](docs/user-guide.md)
- [任务操作](docs/user-guide.md)

---

## 许可证

专有软件 - 仅限内部使用
