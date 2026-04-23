# 本地验证指南

本文档描述如何在本地机器上完整验证 Bend Platform 系统，包括管理平台和 Agent 的所有功能。

---

## 目录

1. [环境要求](#环境要求)
2. [环境准备](#环境准备)
3. [数据库初始化](#数据库初始化)
4. [管理平台启动](#管理平台启动)
5. [前端启动](#前端启动)
6. [Agent 配置与启动](#agent-配置与启动)
7. [验证流程](#验证流程)
8. [常见问题](#常见问题)

---

## 环境要求

### 硬件要求

| 组件 | 要求 |
|------|------|
| CPU | 4核+ |
| 内存 | 8GB+ |
| 硬盘 | 20GB+ |
| 网络 | 稳定网络连接 |

### 软件要求

| 软件 | 版本 | 说明 |
|------|------|------|
| JDK | 17+ | 后端运行 |
| Maven | 3.6+ | 后端构建 |
| Node.js | 16+ | 前端运行 |
| npm | 8+ | 前端依赖 |
| MySQL | 8.0+ | 数据库 |
| Redis | 6.0+ | 可选 |
| Python | 3.8+ | Agent运行 |
| Windows | 10/11 | Agent运行 |

---

## 环境准备

### 1. 安装 JDK 17

```bash
# 检查 Java 版本
java -version

# 如果没有，安装 OpenJDK 17
# Windows: https://adoptium.net/temurin/releases/?version=17
# macOS: brew install openjdk@17
# Linux: sudo apt install openjdk-17-jdk
```

### 2. 安装 Maven

```bash
# 检查 Maven 版本
mvn -version

# 如果没有，安装 Maven
# Windows: https://maven.apache.org/download.cgi
# macOS: brew install maven
```

### 3. 安装 Node.js

```bash
# 检查 Node 版本
node -v

# 如果没有，安装 Node.js 18+
# Windows/macOS: https://nodejs.org/
# Linux: curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash - && sudo apt-get install -y nodejs
```

### 4. 安装 MySQL 8.0

```bash
# Windows: https://dev.mysql.com/downloads/installer/
# macOS: brew install mysql
# Linux: sudo apt install mysql-server

# 启动 MySQL
# Windows: net start mysql
# macOS: brew services start mysql
# Linux: sudo systemctl start mysql
```

### 5. 安装 Redis（可选）

```bash
# Redis 用于缓存和消息队列，如果禁用可以跳过
# Windows: https://github.com/tporadowski/redis/releases
# macOS: brew install redis
# Linux: sudo apt install redis-server
```

---

## 数据库初始化

### 1. 创建数据库

```bash
mysql -u root -p

# 执行以下 SQL
CREATE DATABASE bend_platform CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE bend_platform;
EXIT;
```

### 2. 执行建表脚本

```bash
cd d:\auto-xbox\team-management\bend-platform

mysql -u root -p bend_platform < db\schema.sql

# 或者在 MySQL 客户端中执行
# SOURCE db/schema.sql;
```

### 3. 验证表结构

```bash
mysql -u root -p bend_platform -e "SHOW TABLES;"
```

应该看到以下表：
- merchant
- vip_config
- merchant_user
- streaming_account
- game_account
- agent_instance
- agent_version
- task
- template
- activation_code
- xbox_host
- system_metrics
- system_alert

---

## 管理平台启动

### 1. 配置环境变量

创建或编辑 `bend-platform/src/main/resources/.env` 文件：

```env
# 数据库配置
DB_HOST=localhost
DB_PORT=3306
DB_NAME=bend_platform
DB_USERNAME=root
DB_PASSWORD=your_mysql_password

# Redis 配置（如果启用）
REDIS_HOST=127.0.0.1
REDIS_PORT=6379

# JWT 配置（32位密钥）
JWT_SECRET=your-32-character-secret-key-here

# AES 加密配置（Agent 需要相同密钥）
AES_SECRET=your-32-character-secret-key-here

# 服务器配置
SERVER_PORT=8090
```

### 2. 编译项目

```bash
cd d:\auto-xbox\team-management\bend-platform

mvn clean compile -DskipTests
```

### 3. 启动后端

```bash
mvn spring-boot:run
```

或者打包后运行：

```bash
mvn clean package -DskipTests
java -jar target\bend-platform-1.0.0.jar
```

### 4. 验证后端启动

访问以下地址：
- API: http://localhost:8090/api
- Swagger文档: http://localhost:8090/swagger-ui.html
- Actuator: http://localhost:8090/actuator

---

## 前端启动

### 1. 安装依赖

```bash
cd d:\auto-xbox\team-management\bend-platform-web

npm install
```

### 2. 配置环境变量

创建 `bend-platform-web/.env` 文件：

```env
VITE_API_BASE_URL=http://localhost:8090
```

### 3. 启动前端

```bash
npm run dev
```

### 4. 访问前端

打开浏览器访问：http://localhost:5173

默认登录账号：
- 用户名: admin
- 密码: admin123

---

## Agent 配置与启动

### 1. 安装 Python 依赖

```bash
cd d:\auto-xbox\team-management\bend-agent

# 创建虚拟环境（推荐）
python -m venv venv
.\venv\Scripts\activate  # Windows
# source venv/bin/activate  # macOS/Linux

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 Agent

编辑 `bend-agent/configs/agent.yaml`：

```yaml
agent:
  id: "agent-dev-001"           # 唯一ID，首次会自动生成
  secret: "your-agent-secret"    # 认证密钥
  heartbeat_interval: 30         # 心跳间隔（秒）
  api_base_url: "http://localhost:8090"

# AES 解密密钥，必须与平台配置一致！
aes:
  secret: "your-32-character-secret-key-here"

logging:
  level: INFO
  file: logs/agent.log
```

### 3. 获取注册码

在管理平台创建商户后，生成注册码：

1. 登录管理平台
2. 进入"注册码管理"
3. 点击"生成注册码"
4. 复制生成的注册码

### 4. 启动 Agent

```bash
cd d:\auto-xbox\team-management\bend-agent

python src/main.py --registration-code YOUR_REGISTRATION_CODE
```

参数说明：
- `--registration-code`: 商户注册码（必需）
- `--agent-id`: 指定 Agent ID（可选）
- `--agent-secret`: 指定 Agent 密钥（可选）

### 5. 验证 Agent 在线

在管理平台：
1. 进入"Agent管理"页面
2. 应该能看到刚启动的 Agent
3. 状态显示为"在线"

---

## 验证流程

### 验证 1: 商户注册

1. 登录管理平台
2. 进入"商户管理"
3. 点击"新建商户"
4. 填写商户信息
5. 点击"确定"保存

### 验证 2: 创建流媒体账号

1. 进入"流媒体账号"页面
2. 点击"添加账号"
3. 填写信息：
   - 账号名称: 测试账号
   - 邮箱: your_email@outlook.com
   - 密码: （你的微软账号密码，会加密存储）
4. 点击"确定"

### 验证 3: 创建游戏账号

1. 进入"游戏账号"页面
2. 点击"添加"
3. 填写信息：
   - 账号名称: 测试游戏账号
   - Xbox Gamertag: 你的Xbox昵称
   - 关联流媒体账号: 选择刚才创建的账号
4. 点击"确定"

### 验证 4: Agent 接收任务

1. 进入"Agent管理"
2. 确认 Agent 状态为"在线"
3. 点击 Agent 的"查看任务"
4. 应该显示"暂无任务"

### 验证 5: 启动自动化（核心验证）

1. 进入"流媒体账号"页面
2. 找到刚才创建的账号
3. 点击"启动自动化"按钮
4. 确认启动

**预期结果**：
- 任务创建成功
- 任务状态变为"执行中"
- Agent 收到任务
- Agent 执行微软登录
- 登录成功后绑定 Xbox

### 验证 6: 查看执行结果

1. 进入"任务管理"页面
2. 找到刚创建的任务
3. 查看：
   - 状态是否为"已完成"或"执行中"
   - 是否有错误信息

---

## 常见问题

### 问题 1: 数据库连接失败

**错误**: `Connection refused` 或 `Access denied`

**解决**:
1. 确认 MySQL 服务已启动
2. 检查用户名密码是否正确
3. 确认数据库已创建

```bash
mysql -u root -p -e "SHOW DATABASES;"
```

### 问题 2: 前端无法访问后端 API

**错误**: `Network Error` 或 `CORS error`

**解决**:
1. 确认后端已启动在 8090 端口
2. 检查 `.env` 文件配置
3. 检查后端 CORS 配置

### 问题 3: Agent 无法连接平台

**错误**: `Connection refused` 或 `WebSocket error`

**解决**:
1. 确认平台后端已启动
2. 检查 `agent.yaml` 中的 `api_base_url`
3. 检查网络连通性

```bash
curl http://localhost:8090/api/health
```

### 问题 4: AES 解密失败

**错误**: `AES 解密失败` 或 `Invalid padding`

**解决**:
1. 确认平台和 Agent 的 AES 密钥一致
2. 确认密钥长度足够（至少16字符）

### 问题 5: 微软登录失败

**错误**: `认证失败` 或 `Invalid credentials`

**解决**:
1. 确认微软账号密码正确
2. 确认网络可以访问微软登录接口
3. 检查 Agent 日志中的详细错误

### 问题 6: Xbox 连接失败

**错误**: `Connection timeout`

**解决**:
1. 确认 Xbox 主机 IP 正确
2. 确认 Xbox 和 Agent 在同一网络
3. 确认 Xbox 已开机且联网

---

## 验证检查清单

```
□ MySQL 数据库已启动
□ 数据库已创建（bend_platform）
□ 建表脚本已执行
□ 后端已启动（8090端口）
□ 前端已启动（5173端口）
□ 可以登录管理平台
□ Agent 已启动
□ Agent 状态为"在线"
□ 流媒体账号已创建
□ 游戏账号已创建
□ 自动化任务已触发
□ 任务状态已更新
□ 微软登录成功（如有真实账号）
```

---

## 联系方式

如有验证问题，请联系技术支持。
