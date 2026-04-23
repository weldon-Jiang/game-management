# 开发说明

本文档面向开发人员，描述 Bend Platform 系统的开发环境搭建、项目结构、代码规范和测试指南。

---

## 目录

1. [快速入门](#快速入门)
2. [开发环境要求](#开发环境要求)
3. [项目结构](#项目结构)
4. [后端开发](#后端开发)
5. [前端开发](#前端开发)
6. [Agent开发](#agent开发)
7. [数据库](#数据库)
8. [测试](#测试)
9. [生产环境部署](#生产环境部署)
10. [代码规范](#代码规范)

---

## 快速入门

### 1. 克隆代码

```bash
git clone <repository-url>
cd bend-platform
```

### 2. 初始化数据库

```bash
# 登录 MySQL
mysql -u root -p

# 执行建表脚本
source db/schema.sql
```

### 3. 启动后端

```bash
cd bend-platform
mvn spring-boot:run
```

### 4. 启动前端

```bash
cd bend-platform-web
npm install
npm run dev
```

### 5. 访问系统

- 前端: http://localhost:5173
- 后端: http://localhost:8090
- API文档: http://localhost:8090/swagger-ui.html

---

## 开发环境要求

### 后端环境

| 环境 | 版本 | 说明 |
|------|------|------|
| JDK | 17+ | 必需 |
| Maven | 3.6+ | 编译打包 |
| MySQL | 8.0+ | 数据库 |
| Redis | 6.0+ | 可选，用于消息队列 |

### 前端环境

| 环境 | 版本 | 说明 |
|------|------|------|
| Node.js | 16+ | 必需 |
| npm | 8+ | 包管理 |

### Agent环境

| 环境 | 版本 | 说明 |
|------|------|------|
| Python | 3.8+ | 必需 |
| Windows | 10/11 | 必需 |

---

## 项目结构

### 后端 (bend-platform)

```
bend-platform/
├── src/main/java/com/bend/platform/
│   ├── controller/        # REST API 控制器
│   │   ├── AuthController.java
│   │   ├── MerchantController.java
│   │   ├── AgentController.java
│   │   ├── TaskController.java
│   │   └── ...
│   │
│   ├── service/          # 业务逻辑层
│   │   ├── impl/         # Service 实现
│   │   └── *.java        # Service 接口
│   │
│   ├── repository/       # MyBatis Mapper
│   │   └── *Mapper.java
│   │
│   ├── entity/          # 数据库实体
│   │   └── *.java
│   │
│   ├── dto/             # 数据传输对象
│   │   ├── request/     # 请求 DTO
│   │   └── response/    # 响应 DTO
│   │
│   ├── config/          # 配置类
│   │   ├── JwtConfig.java
│   │   ├── RedisConfig.java
│   │   ├── WebSocketConfig.java
│   │   └── ...
│   │
│   ├── websocket/       # WebSocket 处理
│   │
│   ├── aspect/          # AOP 切面
│   │   ├── IdempotentInterceptor.java  # 幂等性校验
│   │   └── AuditLogAspect.java         # 审计日志
│   │
│   ├── annotation/      # 自定义注解
│   │
│   ├── enums/          # 枚举类
│   │
│   ├── exception/       # 异常处理
│   │
│   └── util/           # 工具类
│
├── src/main/resources/
│   ├── application.yml  # 主配置
│   └── mapper/         # MyBatis XML
│
└── db/
    └── schema.sql      # 数据库建表脚本
```

### 前端 (bend-platform-web)

```
bend-platform-web/
├── src/
│   ├── api/                    # API 接口（模块化）
│   │   ├── index.js           # 统一导出
│   │   ├── auth.js            # 认证相关
│   │   ├── merchant.js        # 商户管理
│   │   ├── agent.js           # Agent管理
│   │   ├── task.js            # 任务管理
│   │   └── ...
│   │
│   ├── views/                 # 页面组件
│   │   ├── login/             # 登录注册
│   │   ├── agent/              # Agent管理
│   │   ├── task/              # 任务管理
│   │   ├── merchant/           # 商户管理
│   │   └── ...
│   │
│   ├── components/             # 公共组件
│   │   └── common/            # 通用组件
│   │       ├── DataTable.vue
│   │       └── ConfirmDialog.vue
│   │
│   ├── stores/                 # Pinia 状态管理
│   │   └── auth.js             # 认证状态
│   │
│   ├── router/                 # Vue Router 配置
│   │   └── index.js
│   │
│   ├── utils/                  # 工具函数
│   │   ├── constants.js        # 常量定义
│   │   └── request.js          # Axios 封装
│   │
│   ├── tests/                  # 测试文件
│   │   ├── unit/               # 单元测试
│   │   ├── integration/        # 集成测试
│   │   └── mocks/              # Mock 数据
│   │
│   └── e2e/                    # E2E 测试
│
├── vitest.config.js            # Vitest 配置
├── playwright.config.js         # Playwright 配置
└── package.json
```

---

## 后端开发

### 项目结构规范

```
com.bend.platform
├── controller/    # REST API，参数校验，调用Service
├── service/      # 业务逻辑，事务管理
├── repository/    # 数据访问，MyBatis Mapper
├── entity/       # 数据库实体，与表一一对应
├── dto/         # 数据传输对象
├── config/      # Spring配置类
├── aspect/      # AOP切面
├── annotation/  # 自定义注解
├── enums/       # 枚举类型
├── exception/   # 异常定义和全局处理
└── util/       # 工具类
```

### API 响应格式

```java
// 成功响应
{
  "code": 200,
  "message": "success",
  "data": { ... }
}

// 错误响应
{
  "code": 400,
  "message": "业务错误描述",
  "data": null
}
```

### 新增 API 步骤

1. 创建 Entity（如需新表）
2. 创建 Mapper 接口
3. 创建 Service 接口和实现
4. 创建 Controller
5. 添加路由配置
6. 编写单元测试

### 常用命令

```bash
# 编译
mvn clean compile

# 运行
mvn spring-boot:run

# 打包
mvn clean package -DskipTests

# 运行测试
mvn test

# 查看依赖树
mvn dependency:tree
```

---

## 前端开发

### 项目结构规范

```
api/          # 按业务模块拆分，不允许一个大文件
views/        # 页面组件，按功能模块组织
components/   # 可复用组件，与业务无关
stores/       # Pinia store，按功能模块
utils/        # 纯工具函数，无副作用
```

### 新增页面步骤

1. 在 `views/` 下创建页面组件
2. 在 `router/index.js` 添加路由
3. 在 `api/` 下创建对应的 API 模块
4. 添加相应的常量定义
5. 编写单元测试

### 常用命令

```bash
# 安装依赖
npm install

# 开发模式
npm run dev

# 构建生产版本
npm run build

# 代码检查
npm run lint

# 代码格式
npm run format

# 运行测试
npm test

# E2E 测试
npm run test:e2e
```

### API 模块示例

```javascript
// src/api/example.js
import request from '@/utils/request'

export const exampleApi = {
  list: (params) => request.get('/api/examples', { params }),
  getById: (id) => request.get(`/api/examples/${id}`),
  create: (data) => request.post('/api/examples', data),
  update: (id, data) => request.put(`/api/examples/${id}`, data),
  delete: (id) => request.delete(`/api/examples/${id}`)
}
```

### HTTP 请求工具特性

| 特性 | 说明 |
|------|------|
| 请求取消 | 自动取消同一接口的重复请求 |
| 自动重试 | 超时/5xx错误自动重试3次 |
| 请求去重 | 相同接口并发请求自动合并 |
| Token注入 | 自动添加 Authorization Header |
| 错误处理 | 401自动跳转登录，其他显示错误消息 |

---

## Agent开发

### 项目结构

```
bend-agent/
├── configs/
│   └── agent.yaml           # 配置文件
│
├── scripts/
│   └── build.bat            # 打包脚本
│
├── src/agent/
│   ├── api/                 # API客户端
│   │   ├── client.py       # HTTP客户端
│   │   ├── websocket.py    # WebSocket客户端
│   │   └── registration.py # 注册相关
│   │
│   ├── core/               # 核心组件
│   │   ├── central_manager.py   # 中央管理器
│   │   ├── config.py        # 配置加载
│   │   └── logger.py       # 日志
│   │
│   ├── task/               # 任务执行
│   │   └── task_executor.py
│   │
│   ├── xbox/               # Xbox控制
│   │   ├── stream_controller.py
│   │   └── xbox_discovery.py
│   │
│   ├── vision/             # 视觉处理
│   │   ├── frame_capture.py
│   │   └── template_matcher.py
│   │
│   └── input/              # 输入控制
│       └── input_controller.py
│
└── templates/              # 模板图像
```

### 运行Agent

```bash
cd bend-agent

# 创建虚拟环境
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行（需配置 agent.yaml）
python src/main.py --agent-id <ID> --agent-secret <SECRET> --registration-code <CODE>
```

---

## 数据库

### 初始化数据库

```bash
# 登录 MySQL
mysql -u root -p

# 创建数据库
CREATE DATABASE bend_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bend_platform;

# 执行建表脚本
SOURCE db/schema.sql;
```

### 主要表结构

| 表名 | 说明 |
|------|------|
| merchant | 商户表 |
| merchant_user | 商户用户表 |
| agent_instance | Agent实例表 |
| agent_version | Agent版本表 |
| streaming_account | 流媒体账号表 |
| game_account | 游戏账号表 |
| task | 任务表 |
| template | 模板表 |
| activation_code | 激活码表 |
| xbox_host | Xbox主机表 |
| system_metrics | 系统监控指标表 |
| system_alert | 系统告警表 |

### 数据库设计规范

1. 表名使用小写，单词间用下划线分隔
2. 主键统一使用 VARCHAR(64) UUID
3. 时间字段使用 DATETIME 类型
4. 状态字段使用 VARCHAR(16)
5. 删除使用逻辑删除（deleted 字段）
6. 统一使用 created_at 和 updated_at

---

## 测试

### 前端测试

```bash
# 单元测试 + 集成测试
npm test

# 监听模式
npm run test:watch

# 覆盖率报告
npm run test:coverage

# 可视化 UI
npm run test:ui

# E2E 测试
npm run test:e2e
```

### 测试文件结构

```
src/tests/
├── unit/                    # 单元测试
│   ├── constants.test.js    # 常量函数测试
│   └── ComponentName.test.js # 组件测试
│
├── integration/              # 集成测试
│   └── api.test.js          # API 测试
│
└── mocks/                   # Mock 数据
    ├── handlers.js          # MSW 请求处理
    ├── server.js            # Mock 服务器
    └── data.js              # 模拟数据
```

### 编写测试

```javascript
// 示例：constants.test.js
import { describe, it, expect } from 'vitest'
import { TASK_STATUS_MAP, getTaskStatusText } from '@/utils/constants'

describe('constants.js', () => {
  it('应该包含所有任务状态', () => {
    expect(TASK_STATUS_MAP).toHaveProperty('pending')
    expect(TASK_STATUS_MAP).toHaveProperty('running')
  })

  it('getTaskStatusText 应该返回正确文本', () => {
    expect(getTaskStatusText('pending')).toBe('待执行')
    expect(getTaskStatusText('running')).toBe('执行中')
  })
})
```

---

## 生产环境部署

### 后端部署

```bash
# 1. 打包
mvn clean package -DskipTests

# 2. 上传 jar 到服务器
scp target/bend-platform-1.0.0.jar user@server:/opt/bend-platform/

# 3. 配置环境变量
export SPRING_PROFILES_ACTIVE=production
export JDBC_URL=jdbc:mysql://localhost:3306/bend_platform
export JDBC_USERNAME=root
export JDBC_PASSWORD=xxx

# 4. 运行
java -jar bend-platform-1.0.0.jar
```

### Nginx 部署配置

```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 前端静态文件
    root /var/www/bend-platform-web/dist;
    index index.html;

    # SPA路由支持
    location / {
        try_files $uri $uri/ /index.html;
    }

    # API代理
    location /api {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # WebSocket代理
    location /ws {
        proxy_pass http://127.0.0.1:8090;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

### 前端部署

```bash
# 1. 构建
npm run build

# 2. 上传 dist 目录到服务器
scp -r dist/* user@server:/var/www/bend-platform-web/dist/
```

---

## 代码规范

### Java 代码规范

1. 类名使用 PascalCase
2. 方法名、变量名使用 camelCase
3. 常量使用 UPPER_SNAKE_CASE
4. 包名全部小写
5. 缩进2个空格
6. 每行不超过120字符

### 前端代码规范

1. 组件名使用 PascalCase
2. 变量使用 camelCase
3. 常量使用 UPPER_SNAKE_CASE
4. CSS 类名使用 kebab-case
5. 缩进2个空格
6. 使用 ESLint + Prettier

### Git 规范

1. 分支命名: `feature/xxx`, `bugfix/xxx`, `hotfix/xxx`
2. Commit 消息: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`
3. PR 需要 Code Review 后合并

### API 命名规范

| 操作 | 方法 | URL |
|------|------|-----|
| 列表 | GET | /api/xxx |
| 详情 | GET | /api/xxx/{id} |
| 新增 | POST | /api/xxx |
| 更新 | PUT | /api/xxx/{id} |
| 删除 | DELETE | /api/xxx/{id} |

---

## 相关文档

- [用户操作指南](user-guide.md)
- [系统流程说明](flow.md)
- [API文档](../bend-platform-api.json)
