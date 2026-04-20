# Bend Platform - Xbox 自动化管理系统

## 系统概述

Bend Platform 是一个商户管理平台，用于管理 Xbox 云游戏自动化系统。主要功能包括商户管理、流媒体账号管理、Xbox主机管理、Agent控制等。

### 核心功能

- **多商户管理**：支持多租户隔离，每个商户独立管理自己的资源
- **流媒体账号管理**：管理 Xbox Game Pass 等流媒体服务账号
- **Xbox主机管理**：管理 Xbox 主机设备，实现主机锁定机制
- **Agent自动化控制**：Windows客户端程序，控制Xbox云游戏自动化任务
- **高并发支持**：单个Agent支持100+并发任务执行
- **实时监控**：系统监控和告警机制

### 系统架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        管理平台 (bend-platform)                    │
│                     Spring Boot + MySQL + Redis                    │
├─────────────────────────────────────────────────────────────────┤
│  前端 (bend-platform-web)                                        │
│  Vue 3 + Element Plus + Vite                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │ HTTP/WebSocket
┌────────────────────────▼────────────────────────────────────────┐
│                     Agent (bend-agent)                            │
│              Python 3 + asyncio + SmartGlass                      │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ CentralManager│  │ TaskExecutor │  │ XboxSessionManager   │   │
│  │   核心管理    │  │  高并发执行  │  │    会话管理(100+)    │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐   │
│  │ StreamCtrl   │  │ TemplateMath │  │   VideoCapture      │   │
│  │ SmartGlass   │  │  模板匹配    │  │    帧捕获           │   │
│  └──────────────┘  └──────────────┘  └──────────────────────┘   │
│                                                                   │
│                        Windows PC                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 技术栈

### 后端平台 (bend-platform)
- **框架**: Spring Boot 2.7.18
- **数据库**: MySQL 8.0
- **缓存/消息队列**: Redis
- **ORM**: MyBatis-Plus 3.5.3
- **安全**: JWT (jjwt 0.9.1)
- **加密**: AES
- **Java版本**: 1.8

### 前端 (bend-platform-web)
- **框架**: Vue 3
- **构建工具**: Vite
- **UI库**: Element Plus
- **状态管理**: Pinia
- **HTTP客户端**: Axios

### Agent (bend-agent)
- **语言**: Python 3
- **异步框架**: asyncio
- **协议**: SmartGlass (TCP)
- **图像处理**: OpenCV, PIL
- **窗口控制**: win32gui, win32ui
- **输入模拟**: pyautogui

---

## 项目结构

```
bend-platform/
├── bend-platform/                    # 后端服务
│   ├── src/main/java/
│   │   └── com/bend/platform/
│   │       ├── controller/           # 控制器层
│   │       ├── service/             # 服务层
│   │       ├── entity/              # 实体类
│   │       ├── dto/                 # 数据传输对象
│   │       ├── repository/          # MyBatis Mapper
│   │       ├── config/              # 配置类
│   │       ├── websocket/           # WebSocket处理
│   │       └── util/                # 工具类
│   ├── src/main/resources/
│   │   └── application.yml          # 配置文件
│   └── db/                          # 数据库脚本
│
├── bend-platform-web/               # 前端应用
│   ├── src/
│   │   ├── api/                    # API接口
│   │   ├── views/                  # 页面组件
│   │   ├── stores/                 # Pinia状态
│   │   ├── router/                 # 路由配置
│   │   └── utils/                  # 工具函数
│   └── package.json
│
└── bend-agent/                      # Agent客户端
    ├── configs/                    # 配置文件
    ├── src/agent/
    │   ├── api/                   # API客户端
    │   ├── core/                  # 核心组件
    │   ├── task/                  # 任务执行
    │   ├── xbox/                  # Xbox控制
    │   ├── vision/                # 视觉处理
    │   ├── input/                 # 输入控制
    │   └── windows/               # 窗口管理
    ├── scripts/                    # 打包脚本
    └── templates/                  # 模板图像
```

---

## 环境要求

### 后端环境
- JDK 1.8+
- MySQL 8.0+
- Redis 6.0+ (可选，用于分布式部署)
- Maven 3.6+

### 前端环境
- Node.js 16+
- npm 8+

### Agent环境
- Windows 10/11
- Python 3.8+
- 网络连接（访问后端服务）

---

## 一、前端构建部署

### 1.1 开发环境运行

```bash
# 进入前端目录
cd bend-platform-web

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

开发服务器默认运行在 `http://localhost:5173`

### 1.2 生产环境构建

```bash
# 安装依赖
npm install

# 构建生产版本
npm run build
```

构建产物输出到 `dist/` 目录

### 1.3 前端配置

前端配置文件位于 `src/utils/constants.js`：

```javascript
// API配置
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8090'

// WebSocket配置
const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8090/ws/agents'
```

### 1.4 环境变量配置

创建 `.env.production` 文件：

```bash
# 后端API地址
VITE_API_BASE_URL=http://你的服务器IP:8090

# WebSocket地址
VITE_WS_URL=ws://你的服务器IP:8090/ws/agents
```

### 1.5 Nginx 部署配置

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

### 1.6 Docker 部署（可选）

```dockerfile
FROM nginx:alpine
COPY dist/ /usr/share/nginx/html/
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

---

## 二、后端构建部署

### 2.1 开发环境运行

```bash
# 进入后端目录
cd bend-platform

# 编译项目
mvn clean compile

# 运行项目
mvn spring-boot:run
```

后端服务默认运行在 `http://localhost:8090`

### 2.2 生产环境构建

```bash
# 编译并打包
mvn clean package -DskipTests

# 构建产物
# target/bend-platform-1.0.0.jar
```

### 2.3 数据库初始化

```bash
# 创建数据库
mysql -u root -p -e "CREATE DATABASE bend_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 执行建表脚本
mysql -u root -p bend_platform < db/migration.sql
mysql -u root -p bend_platform < db/monitoring.sql
```

### 2.4 后端配置

主配置文件：`src/main/resources/application.yml`

```yaml
server:
  port: 8090

spring:
  datasource:
    url: jdbc:mysql://localhost:3306/bend_platform?useUnicode=true&characterEncoding=utf8&useSSL=false&serverTimezone=Asia/Shanghai&allowPublicKeyRetrieval=true
    username: root
    password: 123456

  # Redis配置（可选，用于分布式部署）
  redis:
    host: localhost
    port: 6379
    password: your-redis-password

mybatis-plus:
  mapper-locations: classpath*:/mapper/**/*.xml
  type-aliases-package: com.bend.platform.entity

jwt:
  secret: your-jwt-secret-key-change-in-production
  expiration: 86400000

aes:
  secret: your-aes-secret-key-change
```

### 2.5 生产环境部署

#### 方式一：JAR 直接运行

```bash
# 设置环境变量
export SPRING_PROFILES_ACTIVE=production

# 运行
java -jar target/bend-platform-1.0.0.jar
```

#### 方式二：Systemd 服务

创建 `/etc/systemd/system/bend-platform.service`：

```ini
[Unit]
Description=Bend Platform Service
After=network.target mysql.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/opt/bend-platform
ExecStart=/usr/bin/java -jar bend-platform-1.0.0.jar --spring.profiles.active=production
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable bend-platform
sudo systemctl start bend-platform
sudo systemctl status bend-platform
```

#### 方式三：Docker 部署（可选）

```dockerfile
FROM openjdk:8-jdk-slim
WORKDIR /app
COPY target/bend-platform-1.0.0.jar app.jar
EXPOSE 8090
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 三、Agent 构建部署

### 3.1 开发环境运行

```bash
# 进入Agent目录
cd bend-agent

# 创建虚拟环境（推荐）
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 运行Agent
python src/main.py --agent-id <AGENT_ID> --agent-secret <AGENT_SECRET> --registration-code <REGISTRATION_CODE>
```

### 3.2 生产环境构建

双击运行 `scripts\build.bat`，或手动执行：

```batch
@echo off
REM ================================================
REM Bend Agent 打包脚本
REM ================================================

REM 1. 创建输出目录
if not exist "dist\release" mkdir dist\release

REM 2. 安装依赖
pip install -r requirements.txt

REM 3. 使用PyArmor加密代码（可选）
REM pyarmor gen --output dist/agent --assert all --assert call src/

REM 4. 直接复制源码到dist目录（开发测试用）
xcopy /S /Q src dist\agent\

REM 5. 复制配置和模板
copy /Y configs\* dist\agent\
xcopy /S /Q templates\* dist\agent\templates\

REM 6. 使用PyInstaller打包
pyinstaller --name BendAgent ^
    --add-data "dist\agent;agent" ^
    --add-data "configs;configs" ^
    --add-data "templates;templates" ^
    --hidden-import=aiohttp ^
    --hidden-import=websockets ^
    --hidden-import=cv2 ^
    --hidden-import=numpy ^
    --hidden-import=PIL ^
    --hidden-import=pyautogui ^
    --hidden-import=yaml ^
    --hidden-import=win32gui ^
    --hidden-import=win32ui ^
    --hidden-import=win32con ^
    --hidden-import=pythonjsonlogger ^
    --onefile ^
    --console ^
    dist\agent\main.py

REM 7. 复制最终产物
copy /Y dist\BendAgent.exe dist\release\
copy /Y configs\agent.yaml dist\release\
xcopy /S /Q dist\agent\configs dist\release\configs\ 2>nul
xcopy /S /Q dist\agent\templates dist\release\templates\ 2>nul
copy /Y docs\README.txt dist\release\

echo.
echo Build completed! Output: dist\release\
pause
```

### 3.3 Agent 配置

配置文件：`configs/agent.yaml`

```yaml
# ================================================
# Bend Agent 配置文件
# ================================================

# ----------------------------------------------
# 后端服务器配置
# ----------------------------------------------
backend:
  base_url: "http://你的平台域名:8090"    # 后端HTTP地址
  ws_url: "ws://你的平台域名:8090/ws/agents"  # WebSocket地址
  api_prefix: "/api"

# ----------------------------------------------
# Agent基本设置
# ----------------------------------------------
agent:
  version: "1.0.0"                        # Agent版本号
  heartbeat_interval: 30                   # 心跳间隔（秒）
  reconnect_delay: 5                       # 重连延迟（秒）
  max_reconnect_attempts: 10               # 最大重连次数
  registration_code: ""                    # 注册码（首次运行时填写）
  port: 8888                              # 监听端口
  update_check_interval: 3600              # 版本检查间隔（秒）

# ----------------------------------------------
# 任务执行器配置（高并发支持）
# ----------------------------------------------
task:
  max_concurrent: 100                      # 最大并发任务数
  max_xbox_sessions: 100                   # 最大Xbox SmartGlass并发连接数
  result_ttl: 3600                         # 任务结果缓存有效期（秒）
  cleanup_interval: 300                    # 清理过期结果的间隔（秒）

# ----------------------------------------------
# 视频捕获配置
# ----------------------------------------------
video:
  fps: 10                                  # 每秒帧数
  capture_interval: 0.1                    # 捕获间隔（秒）
  max_frame_buffer: 5                      # 帧缓冲区大小

# ----------------------------------------------
# 模板匹配配置
# ----------------------------------------------
template:
  threshold: 0.8                          # 匹配阈值（0-1）
  template_dir: "./templates"             # 模板目录
  cache_enabled: true                     # 是否启用缓存

# ----------------------------------------------
# 场景检测配置
# ----------------------------------------------
scene:
  detection_interval: 0.5                   # 检测间隔（秒）
  confidence_threshold: 0.7                 # 置信度阈值

# ----------------------------------------------
# 输入控制配置
# ----------------------------------------------
input:
  click_delay: 0.1                        # 点击延迟（秒）
  key_press_delay: 0.05                   # 按键延迟（秒）
  move_duration: 0.2                      # 鼠标移动时长（秒）

# ----------------------------------------------
# 日志配置
# ----------------------------------------------
logging:
  level: "INFO"                            # 日志级别
  file: "./logs/agent.log"               # 日志文件路径
  max_size: 10                            # 单个日志文件最大大小（MB）
  backup_count: 5                          # 保留的备份文件数量
```

### 3.4 Agent 部署包内容

部署包应包含以下文件：

```
BendAgent/
├── BendAgent.exe      # 主程序
├── agent.yaml         # 配置文件
├── templates/          # 模板图像目录
│   ├── xbox_home.png
│   ├── xbox_login.png
│   └── ...
└── README.txt         # 使用说明
```

---

## 四、Agent 安装注册流程

### 4.1 准备工作

1. 确保已安装 Python 3.8+ 环境
2. 从平台管理员获取：
   - **注册码**：用于激活Agent并绑定到商户
   - **后端地址**：平台服务器的URL

### 4.2 安装步骤

#### 步骤1：解压安装包

将Agent安装包解压到任意目录（建议不要放在桌面或下载文件夹）

```
D:\BendAgent\
├── BendAgent.exe
├── agent.yaml
├── templates/
└── ...
```

#### 步骤2：配置后端地址

编辑 `agent.yaml` 文件：

```yaml
backend:
  base_url: "http://你的平台IP或域名:8090"
  ws_url: "ws://你的平台IP或域名:8090/ws/agents"
```

#### 步骤3：填写注册码

编辑 `agent.yaml` 文件，填写注册码：

```yaml
agent:
  registration_code: "你从平台获取的注册码"
```

#### 步骤4：首次运行

双击 `BendAgent.exe` 运行程序

首次运行时，Agent会自动：
1. 连接后端服务器
2. 使用注册码激活
3. 完成Agent注册
4. 建立WebSocket长连接
5. 开始发送心跳

### 4.3 验证安装

登录平台管理后台，进入 **Agent管理** 页面，确认：
- Agent状态显示为"在线"
- 显示正确的商户名称
- 版本号正确

---

## 五、Agent 卸载流程

### 5.1 普通卸载（保留注册表）

如果只是重装或迁移Agent，保留注册表数据：

1. **正常关闭Agent**
   - 右键系统托盘图标，选择"退出"
   - 或直接关闭命令行窗口

2. **卸载程序**
   - 通过Windows设置 -> 应用 -> 卸载
   - 或直接删除Agent文件夹

3. **平台端状态**
   - Agent状态自动变为"离线"
   - 注册码保持"已使用"状态
   - 重新安装后无需新注册码

### 5.2 完全清除（更换机器）

如果需要更换电脑或彻底清除Agent身份：

1. **卸载时勾选"清除注册表"**
   - 运行卸载程序时勾选此选项
   - Agent会自动清除本地注册表数据

2. **手动清除注册表（可选）**
   - 删除注册表项：`HKEY_CURRENT_USER\Software\BendAgent`

3. **平台端行为**
   - Agent状态变为"已卸载"
   - 如需重新安装，需要新的注册码
   - 平台会创建新的Agent记录

---

## 六、Agent 注册与平台关联

### 6.1 注册流程图

```
商户操作                          平台后端                        Agent
   │                               │                              │
   │  1.生成注册码                  │                              │
   │─────────────────────────────>│                              │
   │                               │                              │
   │  2.发放注册码给商户            │                              │
   │<──────────────────────────────│                              │
   │                               │                              │
   │                               │        3.首次运行Agent        │
   │                               │<───────────────────────────── │
   │                               │                              │
   │                               │  4.API: /api/agents/register│
   │                               │<──────────────────────────── │
   │                               │                              │
   │                               │  5.创建AgentInstance记录    │
   │                               │  6.更新注册码状态为已使用    │
   │                               │                              │
   │                               │  7.返回agentId和secret      │
   │                               │─────────────────────────────>│
   │                               │                              │
   │  8.Agent上线                   │                              │
   │<──────────────────────────────│                              │
   │                               │                              │
```

### 6.2 重新上线流程

Agent因网络断开等原因离线后，重新上线的流程：

```
Agent                             平台后端
   │                                  │
   │  1.网络恢复，重新连接             │
   │                                  │
   │  2.API: /api/agents/register    │
   │     (使用原agentId和secret)      │
   │<────────────────────────────────>│
   │                                  │
   │  3.平台识别为已存在的Agent       │
   │  4.更新状态为"online"            │
   │                                  │
   │  5.返回确认                      │
   │<────────────────────────────────>│
   │                                  │
```

### 6.3 心跳机制

Agent运行时会定期发送心跳：

```yaml
agent:
  heartbeat_interval: 30    # 心跳间隔（秒）
```

心跳内容：
- Agent当前状态
- 正在执行的任务ID
- 当前流媒体账号ID
- 运行中的任务数
- Xbox会话数

---

## 七、系统数据流

### 7.1 任务下发流程

```
管理员                平台后端              WebSocket           Agent
   │                     │                    │                  │
   │  1.创建自动化任务    │                    │                  │
   │────────────────────>│                    │                  │
   │                     │                    │                  │
   │                     │  2.保存任务到数据库 │                  │
   │                     │                    │                  │
   │                     │  3.WebSocket推送任务│                  │
   │                     │───────────────────>│                  │
   │                     │                    │                  │
   │                     │                    │  4.接收并解析任务 │
   │                     │                    │                  │
   │                     │                    │  5.执行任务       │
   │                     │                    │                  │
   │                     │  6.任务结果回调    │                  │
   │                     │<───────────────────│                  │
   │                     │                    │                  │
   │  7.更新任务状态      │                    │                  │
   │<────────────────────│                    │                  │
   │                     │                    │                  │
```

### 7.2 自动化控制流程

```
流媒体账号列表 ──> 创建自动化任务 ──> 分配给Agent ──> 执行自动化
                                        │
                                        ▼
                                   WebSocket下发
                                        │
                                        ▼
                        ┌───────────────┴───────────────┐
                        │                               │
                    Xbox SmartGlass                  输入模拟
                        │                               │
                        ▼                               ▼
                  连接Xbox主机                      模板匹配
                        │                               │
                        ▼                               ▼
                  控制云游戏                       图像识别
```

---

## 八、系统监控与告警

### 8.1 监控指标

| 指标类型 | 指标名称 | 说明 |
|---------|---------|------|
| JVM | memory_used | JVM已使用内存 |
| JVM | memory_usage_percent | JVM内存使用率 |
| 系统 | cpu_usage_percent | 系统CPU使用率 |
| 系统 | memory_usage_percent | 系统内存使用率 |
| 业务 | agent_online_count | 在线Agent数量 |
| 业务 | task_running_count | 运行中任务数量 |
| 业务 | task_success_rate | 任务成功率 |

### 8.2 告警类型

| 告警类型 | 告警级别 | 说明 |
|---------|---------|------|
| AGENT_OFFLINE | HIGH | Agent离线超过5分钟 |
| TASK_FAILED | MEDIUM | 任务连续失败3次 |
| HIGH_CPU | MEDIUM | CPU使用率超过90% |
| HIGH_MEMORY | MEDIUM | 内存使用率超过90% |
| XBOX_CONNECTION_FAILED | HIGH | Xbox连接失败 |

### 8.3 监控API

```bash
# 获取JVM信息
GET /api/monitoring/jvm

# 获取系统信息
GET /api/monitoring/system

# 获取业务统计
GET /api/monitoring/stats

# 获取告警列表
GET /api/monitoring/alerts

# 确认告警
POST /api/monitoring/alerts/{id}/acknowledge

# 解决告警
POST /api/monitoring/alerts/{id}/resolve
```

---

## 九、常见问题

### 9.1 后端问题

**Q: 启动报错"数据库连接失败"**
A: 检查MySQL服务是否启动，以及application.yml中的数据库配置是否正确

**Q: Redis连接失败影响运行吗？**
A: 不影响基本功能，Redis仅用于分布式部署和消息队列

### 9.2 Agent问题

**Q: Agent无法连接服务器**
A: 检查agent.yaml中的base_url和ws_url是否正确配置

**Q: 模板匹配不工作**
A: 确认templates/目录下有所需的模板图像，且图像清晰可识别

**Q: 多开失败**
A: 确认config.yaml中max_concurrent和max_xbox_sessions配置足够大

### 9.3 前端问题

**Q: 页面空白**
A: 检查浏览器控制台是否有跨域错误，确认后端服务正常运行

**Q: 登录后无数据**
A: 确认用户角色权限，检查商户是否正确关联

---

## 十、快速部署清单

### 环境准备
- [ ] MySQL 8.0+ 已安装并运行
- [ ] JDK 1.8+ 已安装
- [ ] Node.js 16+ 已安装
- [ ] Python 3.8+ 已安装（Agent用）

### 后端部署
- [ ] 创建数据库 `bend_platform`
- [ ] 执行 `db/migration.sql`
- [ ] 执行 `db/monitoring.sql`
- [ ] 配置 `application.yml`
- [ ] 编译打包：`mvn clean package`
- [ ] 启动服务：`java -jar bend-platform.jar`

### 前端部署
- [ ] 安装依赖：`npm install`
- [ ] 配置后端地址
- [ ] 构建生产版本：`npm run build`
- [ ] 部署到Nginx

### Agent部署
- [ ] 打包Agent安装包
- [ ] 分发安装包给商户
- [ ] 商户配置后端地址
- [ ] 商户填写注册码
- [ ] 商户运行Agent
- [ ] 平台确认Agent在线

---

## 联系方式

如有问题，请联系平台管理员或查阅开发团队文档。
