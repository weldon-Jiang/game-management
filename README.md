# Bend Platform - Xbox 自动化管理系统

## 系统概述

Bend Platform 是一个商户管理平台，用于管理 Xbox 云游戏自动化系统。主要功能包括商户管理、流媒体账号管理、Xbox主机管理、Agent控制等。

---

## 文档导航

| 文档 | 说明 |
|------|------|
| [快速入门](docs/development.md#快速入门) | 环境搭建、启动方式 |
| [用户操作指南](docs/user-guide.md) | 商户注册、Agent管理、任务操作 |
| [系统流程说明](docs/flow.md) | 业务流程、数据流向 |

---

## 核心功能

| 功能 | 说明 |
|------|------|
| 多商户管理 | 支持多租户隔离，每个商户独立管理资源 |
| 流媒体账号管理 | 管理 Xbox Game Pass 等流媒体服务账号 |
| Xbox主机管理 | 管理 Xbox 主机设备，实现主机锁定机制 |
| Agent自动化控制 | Windows客户端，控制Xbox云游戏自动化任务 |
| 高并发支持 | 单个Agent支持100+并发任务执行 |
| 实时监控 | 系统监控和告警机制 |

---

## 技术架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        管理平台 (bend-platform)                    │
│                     Spring Boot 3.2 + MySQL + Redis                │
├─────────────────────────────────────────────────────────────────┤
│  前端 (bend-platform-web)                                        │
│  Vue 3 + Element Plus + Vite + Pinia                            │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/WebSocket
┌────────────────────────▼────────────────────────────────────────┐
│                     Agent (bend-agent)                            │
│              Python 3 + asyncio + SmartGlass                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ CentralManager│  │ TaskExecutor │  │ XboxSessionManager   │   │
│  │   核心管理    │  │  高并发执行  │  │    会话管理(100+)    │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                        Windows PC                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 技术栈

| 模块 | 技术 | 版本 |
|------|------|------|
| **后端平台** | Spring Boot | 3.2.5 |
| | MyBatis-Plus | 3.5.5 (Spring Boot 3 专用) |
| | MySQL | 8.0+ |
| | Redis | 6.0+ |
| | JWT | jjwt 0.12.x |
| **前端** | Vue 3 | 3.5.x |
| | Vite | 8.0.x |
| | Element Plus | 2.13.x |
| | Pinia | 3.0.x |
| **Agent** | Python 3 | 3.8+ |
| | asyncio | - |
| | SmartGlass | Xbox协议 |

---

## 项目结构

```
bend-platform/
├── bend-platform/           # 后端服务 (Spring Boot)
│   ├── src/main/java/      # Java源码
│   ├── src/main/resources/  # 配置文件
│   └── db/                 # 数据库脚本
│
├── bend-platform-web/       # 前端应用 (Vue 3)
│   ├── src/
│   │   ├── api/            # API接口模块化
│   │   ├── views/           # 页面组件
│   │   ├── stores/          # Pinia状态管理
│   │   ├── router/          # 路由配置
│   │   ├── utils/           # 工具函数
│   │   └── tests/           # 单元测试
│   ├── e2e/                 # E2E测试
│   └── docs/                # 开发文档
│
└── bend-agent/             # Agent客户端 (Python)
    ├── configs/             # 配置文件
    └── src/agent/           # 源码
```

---

## 快速链接

### 开发者
- [开发环境搭建](docs/development.md#开发环境要求)
- [数据库初始化](docs/development.md#数据库初始化)
- [启动调试](docs/development.md#启动项目)
- [测试框架](docs/development.md#测试)

### 运维
- [生产部署](docs/development.md#生产环境部署)
- [Nginx配置](docs/development.md#nginx-部署配置)
- [系统监控](docs/flow.md#系统监控)

### 用户
- [登录注册](docs/user-guide.md#登录注册)
- [商户管理](docs/user-guide.md#商户管理)
- [Agent管理](docs/user-guide.md#agent-管理)
- [任务操作](docs/user-guide.md#任务管理)

---

## 环境要求

| 环境 | 要求 |
|------|------|
| JDK | 17+ |
| Node.js | 16+ |
| MySQL | 8.0+ |
| Redis | 6.0+ (可选) |
| Python | 3.8+ (Agent) |
| OS | Windows 10/11 (Agent) |

---

## 版本信息

当前版本: 1.0.0

详细版本说明请参考 [CHANGELOG](docs/CHANGELOG.md)

---

## 许可证

专有软件 - 仅限内部使用
