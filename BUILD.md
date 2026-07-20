# 生产打包指南

本文档说明如何将项目打包为 Windows 安装程序（`.exe`），分发给商户部署。

Docker 开发/测试部署见 [docker/README.md](docker/README.md)。

---

## 概览

| 包 | 部署位置 | 打包次数 | 安装次数 | 产物 |
|---|---|---|---|---|
| **总控** (Master) | 公网服务器 | **打一次** | 装一次 | `BendPlatformMasterSetup.exe` |
| **分控** (Tenant) | 商户局域网 | **打一次**（通用包） | 每商户装一次 | `BendPlatformTenantSetup.exe` |
| **Agent** | 挂机电脑 | **打一次**（通用包） | 每台装一次 | `BendAgentSetup.exe` |

> 三个包都是**通用安装包**，只打一次。分控包不含 License 和商户数据——商户安装时输入激活码，安装器实时向总控签发 License 并拉取数据。Agent 包不含分控地址——安装后自动通过 UDP 发现局域网分控。

---

## 前置条件

### 1. 安装工具

| 工具 | 用途 | 安装方式 |
|---|---|---|
| **Maven** 3.8+ | 构建 backend.jar / gateway.jar | `mvn -version` |
| **Node.js** 20+ | 构建前端 dist | `node -v` |
| **Inno Setup 6** (ISCC) | 编译 .exe 安装包 | 默认 `C:\Program Files (x86)\Inno Setup 6\ISCC.exe` |
| **Python** 3.10+ + PyInstaller | Agent 打包（仅 Agent 包） | `bend-agent/scripts/build.bat` |

### 2. 准备 green 资源（一次性，不入 git）

这些是体积大的绿色二进制，需打包者自行准备，放入 `deploy/standalone/staging/base/`：

```
deploy/standalone/staging/base/
├── jre/          ← JRE 21 (Windows x64, jlink 或解压版)
├── mysql/        ← MySQL 8.x green (zip 解压版, 含 my.ini, 端口 3306)
├── redis/        ← Redis Windows green (仅总控需要)
├── nginx/        ← nginx green (承载前端静态资源)
└── nssm.exe      ← Windows 服务托管 (https://nssm.cc/)
```

Agent 包额外准备 `deploy/standalone/staging/agent/`：

```
deploy/standalone/staging/agent/
├── chromium/           ← Playwright Chromium 目录 (从 %LOCALAPPDATA%\ms-playwright\ 复制)
├── vc_redist.x64.exe   ← VC++ 2015-2022 x64 (https://aka.ms/vs/17/release/vc_redist.x64.exe)
└── nssm.exe
```

### 3. 构建 Agent 可执行文件（仅 Agent 包）

```powershell
cd bend-agent
.\scripts\build.bat
# 产物: bend-agent\dist\BendAgent.exe
```

---

## 打包步骤

### 第一步：打总控包

总控部署在公网，一次打完即可。

```powershell
powershell -ExecutionPolicy Bypass -File deploy\standalone\master\build-master-package.ps1
```

**脚本做了什么：**
1. `mvn package` 构建 backend.jar + gateway.jar
2. `npm run build` 构建前端 dist
3. 复制 green 资源 (jre/mysql/redis/nginx/nssm) + schema.sql
4. 调用 ISCC 编译安装包

**产物：** `deploy\standalone\master\Output\BendPlatformMasterSetup.exe`

**安装后手动操作：**
- 登录总控后台（默认 `http://公网IP:8090`）
- 创建商户 → 签发 License → 记录 `licenseKey` 和 `licenseSecret`

---

### 第二步：打分控包

打一次出通用安装包，每个商户安装时输入激活码即可。

```powershell
powershell -ExecutionPolicy Bypass -File deploy\standalone\tenant\build-tenant-package.ps1
```

> 分控包是**通用包**，不含 License 和商户数据——商户安装时输入**激活码**，安装器向总控实时签发 License 并拉取数据。

**脚本做了什么：**
1. 构建 backend.jar + gateway.jar + 前端 dist
2. 组装 green 资源 + nginx.conf + 激活/升级脚本 + migration SQL
3. 生成占位 `tenant.env`（安装时由激活脚本回写真实值）
4. 调用 ISCC 编译安装包

**产物：** `deploy\standalone\tenant\Output\BendPlatformTenantSetup.exe`

**安装体验（商户侧）：**
1. 双击安装 → 选路径
2. 安装器提示输入**总控地址** + **激活码**
3. 自动：初始化 MySQL → 建库导表 → 向总控激活 License → 拉取商户数据 → 注册服务 → 启动
4. 完成后自动打开 `http://localhost:8090`

---

### 第三步：打 Agent 包

每台挂机电脑一个，Agent 启动后 **UDP 自动发现分控**，无需预填地址。

```powershell
powershell -ExecutionPolicy Bypass -File deploy\standalone\agent\build-agent-package.ps1
```

**脚本做了什么：**
1. 复制 `BendAgent.exe` + 场景模板
2. 生成占位 `agent.yaml`（首次启动 UDP 自动发现分控 IP 并回写）
3. 调用 ISCC 编译安装包（内嵌 Chromium + VC++ redist）

**产物：** `deploy\standalone\agent\Output\BendAgentSetup.exe`

**安装体验（商户侧）：**
1. 双击安装 → 选路径
2. 安装前自动检测局域网是否有分控在运行，无则中止提示"请先装分控"
3. 静默装 VC++ redist → 配置 Chromium → 注册 BendAgent 自启动服务 → 启动
4. Agent 首次启动：UDP 发现分控 IP → 免注册码注册 → 连分控 WS 开始工作

---

## 产物清单

打包完成后，`deploy/standalone/` 下的 Output 目录：

```
deploy/standalone/
├── master/Output/
│   └── BendPlatformMasterSetup.exe    ← 总控安装包（运维持有）
├── tenant/Output/
│   └── BendPlatformTenantSetup.exe    ← 分控安装包（发给商户）
└── agent/Output/
    └── BendAgentSetup.exe             ← Agent 安装包（发给商户）
```

> **发给商户的两个包：** `BendPlatformTenantSetup.exe` + `BendAgentSetup.exe`

---

## 部署架构

```
公网:   总控 (Master)
          backend + gateway + web + MySQL + Redis
          ▲ 分控主动出站 (license 校验 + 指标上报)
          │
局域网:  分控 (Tenant)  ← 每商户一套
          backend(tenant) + gateway + web + MySQL green
          端口: web 8090 / gateway 8060 / backend 8061 / MySQL 3306
          ▲ Agent 局域网内连 (UDP 47820 自动发现)
          │
        Agent × N  ← 挂机电脑, 可装分控同机
          不监听入站端口, 只出站连分控 8060
```

---

## 打包后验证

- [ ] **总控**：安装后 `curl http://公网:8060/actuator/health` → `UP`，后台能登录
- [ ] **分控**：安装后 `http://localhost:8090` 可打开，`logs/bend-platform.log` 可见 `license 校验 valid=true`
- [ ] **Agent**：服务 `BendAgent` 状态 Running，`logs/service_stdout.log` 可见 "已发现分控" + "自动注册成功"
- [ ] 三端时间戳一致（时区 `Asia/Shanghai`）

---

## 常见问题

### 构建失败

| 现象 | 解决 |
|---|---|
| `mvn` 报错 | 检查 Java 17+ 和 Maven 3.8+ 是否安装，`mvn -version` 确认 |
| `npm run build` 报错 | `cd bend-platform-web && npm install` 后重试 |
| `ISCC 未找到` | 安装 Inno Setup 6，或传 `-IsccPath "路径"` 参数 |
| `BendAgent.exe 不存在` | 先执行 `bend-agent/scripts/build.bat` |

### 安装后问题

| 现象 | 解决 |
|---|---|
| 分控 license 校验失败 | 检查总控地址是否可达、`LICENSE_SIGN_SECRET` 总控与分控是否一致 |
| 分控提示"已有分控运行" | 同局域网只允许一个分控，先卸载旧的 |
| Agent 发现不了分控 | 确认 Agent 与分控在同一局域网，分控 UDP 广播在运行 |
| 同局域网其他电脑访问不了分控 | 检查 Windows 防火墙是否放行 8090（安装脚本已自动处理） |
| 分控后台登录不了 | 使用总控创建的商户用户名/密码（非总控 admin） |

---

## 相关文档

- [总控安装说明](deploy/standalone/master/README.md)
- [分控安装说明](deploy/standalone/tenant/README.md)
- [Agent 安装说明](deploy/standalone/agent/README.md)
- [Docker 开发部署](docker/README.md)
- [本地三端验证](deploy/standalone/local-dev-verify.md)
- [架构设计决策](AGENTS.md)
