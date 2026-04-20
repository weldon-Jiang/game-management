# XStreaming 管理平台设计方案

## 一、项目概述

```Java
┌─────────────────────────────────────────────────────────────────────────────┐
│                        XStreaming 管理平台 (B-End)                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────────┐         ┌─────────────────┐         ┌─────────────┐ │
│   │   Vue Frontend  │  REST   │   Java Backend  │   JDBC  │    MySQL    │ │
│   │   (管理后台)    │ ←────→  │   (Spring Boot) │ ←─────→ │  (数据库)   │ │
│   └─────────────────┘         └─────────────────┘         └─────────────┘ │
│           │                            │                                      │
│           │                            │                                      │
│           │                     ┌──────┴──────┐                              │
│           │                     │             │                              │
│           │                     ▼             ▼                              │
│           │              ┌───────────┐ ┌───────────┐                       │
│           │              │ Automation│ │  Agent    │                       │
│           └──────────────│  Service  │ │ Service  │                       │
│                          └───────────┘ └───────────┘                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 多商户架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         平台管理员 (Platform Admin)                          │
│                    负责管理商户、生成点卡验证码                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  平台管理员                                                                    │
│  ├── 添加/编辑/删除商户                                                      │
│  ├── 设置商户购买类型（包月/包年/按量/长期）                                    │
│  ├── 生成点卡验证码                                                          │
│  ├── 查看所有商户运营数据                                                     │
│  └── 系统配置                                                                │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    │ 点卡验证码
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           商户 (Merchant)                                    │
│                  拥有独立的账号空间和数据隔离                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  商户管理员                                                                   │
│  ├── 串流账号管理                                                            │
│  ├── 游戏账号管理                                                            │
│  ├── Agent 管理                                                             │
│  ├── 任务监控                                                               │
│  └── 统计数据                                                               │
│                                                                             │
│  ⚠ 数据隔离：商户只能看到自己商户下的数据                                       │
└─────────────────────────────────────────────────────────────────────────────┘
```

**商户-Agent-串流账号层级关系：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              商户 (Merchant)                                  │
│  VIP/SVIP 决定可绑定的 Agent 数量上限                                        │
│  管理员可配置每个 Agent 的最大串流数量（根据硬件配置）                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                        │
│  │  Agent 1   │  │  Agent 2   │  │  Agent N   │                        │
│  │ (电脑 A)   │  │ (电脑 B)   │  │ (电脑 N)   │                        │
│  │             │  │             │  │             │                        │
│  │ max: 4     │  │ max: 8     │  │ max: 4     │                        │
│  │ curr: 2    │  │ curr: 5    │  │ curr: 0    │                        │
│  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘                        │
│         │                  │                  │                              │
│    ┌────┴────┐        ┌────┴────┐        ┌────┴────┐                        │
│    │ 串流账号 │        │ 串流账号 │        │ 串流账号 │                        │
│    │  1, 2   │        │ 3,4,5,6,7│        │   无    │                        │
│    └──────────┘        └──────────┘        └──────────┘                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Agent 部署架构：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         云服务器 (B-End 管理平台)                              │
│                                                                               │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                          │
│   │  WebSocket  │  │  REST API   │  │   MySQL     │                          │
│   │   Server    │  │   Server    │  │  Database   │                          │
│   │  (任务下发)  │  │  (管理操作)  │  │  (数据存储)  │                          │
│   └──────┬──────┘  └──────┬──────┘  └─────────────┘                          │
│          │                │                                                   │
└──────────│────────────────│───────────────────────────────────────────────────┘
           │                │
           │  ←── WebSocket (Agent 主动连接) ──→
           │  ←── REST API (心跳、数据上报) ──→
           │
           │
           │                    商户电脑 A (Agent 1)
           │                    ┌──────────────────────────────────────┐
           │                    │              Agent 程序                 │
           │                    │  - 主动连接云服务器                     │
           │                    │  - 管理多台 Xbox 主机（窗口）            │
           │                    │  - 自主分配串流账号到空闲 Xbox           │
           │                    │  - 实时上报每个 Xbox 状态               │
           │                    └──────────────┬───────────────────────┘
           │                                 │
           │    ┌────────────────────────────┼────────────────────────────┐
           │    │                            │                            │
           │    ▼                            ▼                            ▼
           │  ┌──────────┐             ┌──────────┐              ┌──────────┐
           │  │ 窗口 0   │             │ 窗口 1   │              │ 窗口 N   │
           │  │ Xbox-1   │             │ Xbox-2   │    ...       │ Xbox-N   │
           │  │192.168.1 │             │192.168.1 │              │192.168.1 │
           │  │    .50   │             │    .51   │              │    .X    │
           │  └────┬─────┘             └────┬─────┘              └────┬─────┘
           │       │                        │                        │
           │       ▼                        ▼                        ▼
           │  ┌──────────┐             ┌──────────┐              ┌──────────┐
           │  │串流账号 A│             │串流账号 B│              │串流账号 N│
           │  │ 串流成功  │             │  串流中   │              │  空闲    │
           │  └──────────┘             └──────────┘              └──────────┘
```

**监控粒度：**

| 层级      | 监控内容                      | 状态字段                                        |
| ------- | ------------------------- | ------------------------------------------- |
| Agent   | 在线状态、心跳、CPU/内存、Xbox 数量    | status, last\_heartbeat, xbox\_count        |
| Xbox 主机 | Xbox 状态、IP、绑定的串流账号、当前游戏账号 | status, streaming\_account\_id, gamertag    |
| 串流账号    | 账号状态、所在 Xbox、今日比赛次数       | status, xbox\_host\_id, today\_match\_count |
| 游戏账号    | 今日完成次数、当前 Xbox            | today\_match\_count, locked\_xbox\_id       |

**通信机制说明：**

| 方向           | 方式                     | 说明                                |
| ------------ | ---------------------- | --------------------------------- |
| Agent → 云服务器 | WebSocket ( outbound ) | Agent 启动后主动连接到云服务器，建立长连接          |
| Agent → 云服务器 | REST API (心跳)          | 定时 POST /api/agent/heartbeat，上报状态 |
| 云服务器 → Agent | WebSocket (已建立连接)      | 通过 Agent 的连接下发任务指令                |
| 商户电脑         | 无需公网IP                 | Agent 主动连接云服务器，突破 NAT 限制          |

**为什么这样设计？**

1. **商户电脑无需公网IP**：Agent 主动连接到云服务器，绕过网络限制
2. **云服务器端口开放**：只需云服务器开放 WebSocket/REST 端口即可
3. **多窗口支持**：每台电脑的 Agent 可管理多个 Xbox 窗口实例
4. **实时控制**：通过 WebSocket 实现实时任务下发和状态反馈

**Agent 程序架构：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Agent 程序架构                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  程序形态: Windows 系统托盘程序（后台服务，无界面）                           │
│  - 启动后最小化到系统托盘                                                    │
│  - 不弹窗，不占用桌面空间                                                    │
│  - 可通过托盘图标右键菜单操作                                                │
│                                                                             │
│  运行模式:                                                                  │
│  - 后台 Windows 服务（可选）                                                │
│  - 或普通进程开机自启                                                        │
│                                                                             │
│  主要模块:                                                                  │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │                        Agent 主程序                                   │  │
│  ├─────────────────────────────────────────────────────────────────────┤  │
│  │  WebSocket Client    │ 心跳上报 / 接收任务 / 状态推送                  │  │
│  │  Xbox Discovery      │ 自动发现局域网 Xbox                           │  │
│  │  Template Manager    │ 模板下载 / 缓存 / 比对                        │  │
│  │  Task Executor       │ 自动化任务执行                                │  │
│  │  Stream Controller   │ Xbox 串流控制                                 │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  数据流:                                                                    │
│  ┌─────────────┐      ┌─────────────┐      ┌─────────────┐               │
│  │  云服务器   │ ──── │   Agent     │ ──── │    Xbox     │               │
│  │  (任务下发) │      │  (执行)     │      │  (执行)     │               │
│  └─────────────┘      └─────────────┘      └─────────────┘               │
│         ↑                    ↑                                           │
│         │                    │                                           │
│  模板文件下载            截图比对                                          │
│  (HTTPS)               (本地执行)                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Xbox 自动发现机制：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         Xbox 自动发现流程                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【自动发现】                                                              │
│                                                                             │
│  1. Agent 启动时自动扫描                                                  │
│     - 扫描局域网 IP 段（根据电脑 IP 自动推断网段）                          │
│     - 尝试连接 Xbox 默认端口 5050                                          │
│     - 通过 Xbox Discovery Protocol 发现设备                                  │
│                                                                             │
│  2. 发现后的处理                                                          │
│     - 获取 Xbox IP、MAC、Gamertag                                         │
│     - 上报给管理平台                                                        │
│     - 自动添加到 xbox_host 表                                              │
│                                                                             │
│  【自动发现异常时的处理】                                                  │
│                                                                             │
│  3. 自动发现可能失败的原因:                                                 │
│     - Xbox 与 Agent 不在同一网段（跨路由器）                                │
│     - Xbox 关闭了 Discovery Protocol                                       │
│     - 网络防火墙阻断                                                        │
│                                                                             │
│  4. 解决方案:                                                              │
│     - Agent 安装向导中提供"手动添加 Xbox"选项                              │
│     - 员工手动输入 Xbox IP 地址                                            │
│     - Agent 尝试连接该 IP，验证是否是 Xbox                                 │
│     - 验证成功后上报管理平台                                                │
│                                                                             │
│  【手动添加 Xbox】                                                         │
│                                                                             │
│  5. 手动添加时的检测流程:                                                   │
│     ┌─────────────────────────────────────────────────────────────────┐     │
│     │ 员工输入 Xbox IP: 192.168.2.100                               │     │
│     │          │                                                    │     │
│     │          ▼                                                    │     │
│     │  Agent 尝试连接 IP:5050                                       │     │
│     │          │                                                    │     │
│     │     ┌────┴────┐                                              │     │
│     │     │ 连接成功 │                                              │     │
│     │     │  是Xbox │                                              │     │
│     │     └────┬────┘                                              │     │
│     │          │                                                    │     │
│     │     ┌────┴────┐                                              │     │
│     │     │ 连接失败 │                                              │     │
│     │     │ 不是Xbox │                                              │     │
│     │     └─────────┘                                              │     │
│     └─────────────────────────────────────────────────────────────────┘     │
│                                                                             │
│  6. 手动添加 Xbox 信息:                                                    │
│     - Xbox IP（必填）                                                      │
│     - Xbox 名称（可选，如：客厅 Xbox）                                     │
│     - MAC 地址（可选，用于 WoL 唤醒）                                      │
│                                                                             │
│  【商户在管理平台手动管理 Xbox】                                           │
│                                                                             │
│  7. 查看所有 Xbox（包括自动发现和手动添加）                                │
│  8. 编辑 Xbox 信息（名称、IP、MAC）                                        │
│  9. 删除 Xbox（释放绑定）                                                 │
│  10. 标记 Xbox 为"不监控"（不参与自动分配）                                │
│                                                                             │
│  【Xbox 状态管理】                                                         │
│                                                                             │
│  | 状态 | 说明 |                                                            │
│  |------|------|                                                            │
│  | idle | 空闲，可分配 |                                                    │
│  | online | Xbox 在线 |                                                    │
│  | offline | Xbox 离线 |                                                  │
│  | disabled | 商户标记不监控 |                                            │
│                                                                             │
│  Xbox Discovery Protocol:                                                   │
│  - 广播地址: 255.255.255.255:5050                                          │
│  - 请求格式: {"type":"xnaddr","req_id":"..."}                              │
│  - 响应格式: {"type":"xnaddr","ip":"...","mac":"..."}                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**手动添加 Xbox API：**

```json
// POST /api/agents/{id}/xbox/manual-add - Agent 手动添加 Xbox
Request:
{
  "ipAddress": "192.168.2.100",
  "name": "客厅 Xbox",
  "macAddress": "AA:BB:CC:DD:EE:FF"
}

Response:
{
  "success": true,
  "xboxHost": {
    "id": 1,
    "ipAddress": "192.168.2.100",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "name": "客厅 Xbox",
    "status": "idle"
  }
}

// Response - 连接失败，不是 Xbox
{
  "success": false,
  "error": "ERR_XBOX_004",
  "message": "该 IP 不是 Xbox 主机，请确认 IP 地址"
}

// POST /api/xbox/{id}/toggle-monitor - 标记是否参与监控
Request:
{"enabled": false}

Response:
{"success": true}
```

**模板匹配流程：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          模板匹配流程                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 模板存储位置                                                            │
│     - 云服务器: /templates/{game}/{template_name}.png                       │
│     - 本地缓存: ~/.xstreaming/templates/{game}/{template_name}.png          │
│                                                                             │
│  2. 模板下载                                                                │
│     - Agent 启动时从云服务器同步模板                                          │
│     - 或任务下发时附带模板URL，Agent按需下载                                  │
│     - 使用 HTTPS 传输，验证服务器证书                                          │
│                                                                             │
│  3. 模板匹配                                                                │
│     - Agent 对 Xbox 界面截图                                                │
│     - 本地使用 OpenCV/Sikuli 进行模板匹配                                    │
│     - 匹配成功/失败上报给云服务器                                            │
│                                                                             │
│  4. 模板更新                                                                │
│     - 云服务器模板更新后，标记版本号                                          │
│     - Agent 检测到版本变化，自动下载最新模板                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**断网/关机补偿机制：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        异常情况处理                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【Agent 突然离线】                                                          │
│                                                                             │
│  1. 检测机制                                                                │
│     - 心跳超时: 超过 120 秒未收到心跳 → 标记为离线                           │
│     - Agent 重启后自动重连                                                   │
│                                                                             │
│  2. 任务恢复                                                                │
│     - 正在执行的任务 → 状态标记为 error，等待人工处理                        │
│     - 或配置自动重试（商户可选）                                             │
│                                                                             │
│  3. Xbox 释放                                                              │
│     - 离线超过 5 分钟 → 自动释放 Xbox 绑定                                    │
│     - Xbox 可被其他 Agent 使用                                              │
│                                                                             │
│  【商户续费后】                                                             │
│                                                                             │
│  - Agent 无需重装                                                           │
│  - 续费只是更新 merchant.expire_at 字段                                     │
│  - Agent 正常运行，不受影响                                                  │
│                                                                             │
│  【商户账号过期】                                                           │
│                                                                             │
│  - Agent 收到心跳响应中的状态                                                │
│  - Agent 进入受限模式: 仅保留基础功能                                        │
│  - 商户续费后自动恢复正常                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Agent 自动启动架构                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. Windows 任务计划程序（系统级别开机自启）                                  │
│     - 设置 Agent 服务开机自动启动                                            │
│     - 电脑重启后自动运行                                                     │
│                                                                             │
│  2. Wake-on-LAN 远程唤醒（可选，需要 BIOS 配置）                             │
│     - 管理平台发送魔术包到 Xbox MAC 地址                                     │
│     - 电脑通电后自动启动到操作系统                                           │
│     - Agent 开机自启 → 连接云服务器                                          │
│                                                                             │
│  3. 管理平台监控 Agent 状态                                                  │
│     - Agent 离线超过阈值 → 标记为离线                                        │
│     - 商户可在管理平台手动触发"重新连接"提醒                                   │
│     - 或使用 Wake-on-LAN 唤醒（如配置了）                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**开机自启动配置（商户电脑一次性设置）：**

| 步骤 | 操作                 | 说明                      |
| -- | ------------------ | ----------------------- |
| 1  | 下载 Agent 安装包       | 从管理平台下载 Agent 程序        |
| 2  | 运行安装向导             | 配置 Backend URL、Agent ID |
| 3  | 勾选"开机自启"           | 自动配置 Windows 任务计划程序     |
| 4  | （可选）配置 Wake-on-LAN | 在 BIOS 中启用，网络接口启用唤醒     |

**管理平台 Agent 状态监控：**

```json
{
  "agentId": "agent-001",
  "name": "电脑A",
  "status": "offline",        // online | offline | error
  "lastHeartbeat": "2024-01-15T10:30:00Z",  // 最后心跳
  "offlineDuration": 3600,    // 离线时长（秒）
  "autoStartEnabled": true,    // 是否配置了开机自启
  "wakeOnLanConfigured": true, // 是否配置了 Wake-on-LAN
  "lastKnownIp": "192.168.1.100"
}
```

**管理平台唤醒 Agent（Wake-on-LAN）：**

| 功能   | 说明                       |
| ---- | ------------------------ |
| 远程唤醒 | 点击"唤醒"按钮，发送魔术包到电脑 MAC 地址 |
| 状态检查 | 检查电脑是否已上线（Agent 是否连上）    |
| 通知商户 | 唤醒失败时通知商户检查电脑电源/网络       |
| 定时任务 | 可配置定时唤醒（如每天特定时间自动开机）     |

**硬件配置说明：**

| 配置项     | 说明          |
| ------- | ----------- |
| CPU 核心数 | 影响并行处理能力    |
| 内存大小    | 影响同时运行的窗口数量 |
| GPU 型号  | 影响视频编解码性能   |
| 最大串流数量  | 根据硬件配置自动计算  |

***

### 会员等级系统

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          会员等级 (VIP Level)                                 │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐          │
│  │      VIP       │     │     SVIP       │     │     NONE      │          │
│  │                 │     │                 │     │    (无会员)    │          │
│  │  按周/按月/按年  │     │  按周/按月/按年  │     │    按周/按月    │          │
│  │  不限(平台分成)  │     │  不限(平台分成)  │     │     --        │          │
│  │                 │     │                 │     │               │          │
│  │ 价格: 较低      │     │ 价格: 较高      │     │  价格: 最低    │          │
│  └────────┬────────┘     └────────┬────────┘     └───────┬───────┘          │
│           │                         │                      │                  │
│           │    ┌────────────────────┴────────────────────┐    │                  │
│           │    │                                         │    │                  │
│           ▼    ▼                                         ▼    ▼                  │
│    ┌─────────────────────────────────────────────────────────────┐             │
│    │                   平台分成 (Revenue Share)                    │             │
│    │                                                               │             │
│    │   商户比赛产出金币 → 平台回收 → 按比例分成给商户                │             │
│    │                                                               │             │
│    │   示例：1000金币 × 分成比例 × 兑换比例 = 分成金额              │             │
│    │                                                               │             │
│    └───────────────────────────────────────────────────────────────┘             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**会员等级价格配置：**

| 等级       | 计费类型     | 说明   | 平台分成        |
| -------- | -------- | ---- | ----------- |
| **VIP**  | 按周/按月/按年 | 固定价格 | 无           |
| **VIP**  | 不限       | 固定价格 | 有           |
| **SVIP** | 按周/按月/按年 | 较高价格 | 无           |
| **SVIP** | 不限       | 较高价格 | 有（分成比例可能更高） |
| **NONE** | 按周/按月    | 最低价格 | 无           |

**金币分成流程：**

```
1. 商户购买"不限"类型会员
       ↓
2. 自动化运行，比赛产出金币
       ↓
3. 第三方金币系统记录游戏账号金币
       ↓
4. B-End 平台定时同步金币数据
       ↓
5. 根据分成比例计算商户收益
       ↓
6. 收益加入商户金币余额
       ↓
7. 商户可查看金币分成明细
```

***

## 二、技术栈

| 层级   | 技术                           | 说明                 |
| ---- | ---------------------------- | ------------------ |
| 前端   | Vue 3 + Element Plus + Pinia | 赛博朋克・霓虹电竞风主题       |
| 后端   | Java 17 + Spring Boot 3      | RESTful API + 安全框架 |
| 数据库  | MySQL 8.0                    | 账户、配置、监控数据         |
| 缓存   | Redis                        | 点卡验证码存储（防重复）       |
| 通信   | HTTP/WebSocket               | API 调用 + 实时状态推送    |
| 自动化  | Python + Electron            | 多窗口自动化串流           |
| 权限控制 | Spring Security + JWT        | 商户隔离 + 点卡认证        |
| 实时监控 | WebSocket + MJPEG            | 浏览器内窗口预览           |

***

## 三、数据库设计

### 3.1 ER 图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           数据库设计原则                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【主键策略】                                                                │
│  - 所有表使用 BIGINT 类型主键                                                │
│  - 主键值由雪花算法（Snowflake）在应用层生成                                 │
│  - 不使用数据库自增主键                                                      │
│                                                                             │
│  【外键策略】                                                                │
│  - 数据库层不建立外键约束（FOREIGN KEY）                                     │
│  - 外键关系由应用层在 SQL 查询时通过 WHERE 条件带入                          │
│  - 例如: JOIN 时使用 WHERE a.merchant_id = b.id                            │
│                                                                             │
│  【为什么这样设计？】                                                        │
│  - 分布式场景下雪花ID更适用                                                  │
│  - 避免跨库/跨表的外键级联删除带来的性能问题                                 │
│  - 应用层控制更灵活，便于后期分库分表                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│ streaming_account│       │   game_account  │       │   agent_instance│
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (BIGINT,PK)  │1     N│ id (BIGINT,PK)  │       │ id (BIGINT,PK)  │
│ merchant_id      │──────<│ streaming_id     │       │ merchant_id     │
│ name             │       │ name            │       │ agent_id        │
│ email            │       │ xbox_gamertag   │       │ host            │
│ password (加密)  │       │ is_primary      │       │ port            │
│ auth_code       │       │ created_at      │       │ status          │
│ status          │       │ updated_at      │       │ current_task    │
│ created_at      │       └─────────────────┘       └─────────────────┘
│ updated_at      │                                        │
└─────────────────┘                                        │
                                                            │ N
┌─────────────────┐                                        │
│ automation_task │                                        │
├─────────────────┤                                        │
│ id (BIGINT,PK)  │<─────────────────────────────────────┘
│ merchant_id     │
│ agent_id        │
│ streaming_id    │
│ game_id         │
│ task_type       │
│ status          │
│ started_at      │
│ finished_at     │
└─────────────────┘
```

### 3.2 表结构设计原则

│ result         │
└─────────────────┘

````

### 3.2 商户与权限表 SQL

```sql
-- 数据库创建
CREATE DATABASE IF NOT EXISTS xstreaming_manager
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE xstreaming_manager;

-- 商户表
CREATE TABLE merchant (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    name VARCHAR(200) NOT NULL COMMENT '商户名称',
    contact_person VARCHAR(100) COMMENT '联系人',
    phone VARCHAR(20) COMMENT '联系电话',
    email VARCHAR(255) COMMENT '邮箱',
    timezone VARCHAR(50) DEFAULT 'Asia/Shanghai' COMMENT '商户时区（用于比赛次数重置）',
    status ENUM('active', 'suspended', 'closed') DEFAULT 'active' COMMENT '状态',
    vip_level ENUM('none', 'vip', 'svip') DEFAULT 'none' COMMENT '会员等级',
    gold_balance DECIMAL(20,2) DEFAULT 0.00 COMMENT '金币余额',
    expire_at DATETIME COMMENT '到期时间（包月/包年/不限）',
    max_agents INT DEFAULT 5 COMMENT '最大 Agent 数量（由 VIP 配置决定）',
    allow_running_on_expire TINYINT(1) DEFAULT 0 COMMENT '到期后是否允许运行自动化',
    allow_running_on_suspended TINYINT(1) DEFAULT 0 COMMENT '禁用后是否允许运行自动化',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_vip_level (vip_level),
    INDEX idx_expire_at (expire_at),
    INDEX idx_timezone (timezone)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商户表';

-- Agent 硬件配置表
CREATE TABLE agent_hardware_config (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    name VARCHAR(100) NOT NULL COMMENT '配置名称（如：标准版/高配版）',
    cpu_cores INT COMMENT 'CPU 核心数',
    memory_gb INT COMMENT '内存大小（GB）',
    gpu_model VARCHAR(100) COMMENT 'GPU 型号',
    gpu_count INT DEFAULT 1 COMMENT 'GPU 数量',
    max_concurrent_streams INT NOT NULL COMMENT '最大同时串流数量',
    max_concurrent_tasks INT NOT NULL COMMENT '最大同时任务数量',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent硬件配置表';

-- 会员等级价格配置表
CREATE TABLE vip_price_config (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    vip_level ENUM('vip', 'svip') NOT NULL COMMENT '会员等级',
    billing_type ENUM('weekly', 'monthly', 'yearly', 'unlimited') NOT NULL COMMENT '计费类型',
    price DECIMAL(10,2) NOT NULL COMMENT '价格',
    duration_days INT NOT NULL COMMENT '持续天数',
    max_agents INT DEFAULT 5 COMMENT '最大 Agent 数量',
    revenue_share_rate DECIMAL(5,4) DEFAULT 0.00 COMMENT '平台分成比例（仅不限类型）',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_vip_billing (vip_level, billing_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='会员等级价格配置表';

-- 点卡验证码表
CREATE TABLE activation_code (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    code VARCHAR(19) NOT NULL COMMENT '验证码（格式：XXXX-XXXX-XXXX，全局唯一）',
    code_hash VARCHAR(64) NOT NULL COMMENT '验证码哈希（SHA-256，用于比对）',
    vip_level ENUM('vip', 'svip') NOT NULL COMMENT '会员等级',
    billing_type ENUM('weekly', 'monthly', 'yearly', 'unlimited') NOT NULL COMMENT '计费类型',
    duration_days INT COMMENT '有效天数',
    amount DECIMAL(10,2) COMMENT '金额',
    revenue_share_rate DECIMAL(5,4) DEFAULT 0.00 COMMENT '平台分成比例（仅不限类型）',
    expired_at DATETIME NOT NULL COMMENT '失效时间',
    used_at DATETIME COMMENT '使用时间',
    used_by VARCHAR(100) COMMENT '使用人',
    status ENUM('unused', 'used', 'expired') DEFAULT 'unused' COMMENT '状态',
    created_by BIGINT COMMENT '创建人（管理员）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='点卡验证码表';

-- 商户余额变动记录表
CREATE TABLE balance_transaction (
    id BIGINT PRIMARY KEY,
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    type ENUM('recharge', 'deduct_task', 'deduct_daily') NOT NULL COMMENT '类型',
    amount DECIMAL(10,2) NOT NULL COMMENT '变动金额（正=充值，负=扣费）',
    balance_before DECIMAL(10,2) NOT NULL COMMENT '变动前余额',
    balance_after DECIMAL(10,2) NOT NULL COMMENT '变动后余额',
    remark VARCHAR(255) COMMENT '备注',
    related_task_id BIGINT COMMENT '关联任务ID（扣费时）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商户余额变动记录表';

-- 金币分成记录表
CREATE TABLE gold_revenue (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    game_account_id BIGINT NOT NULL COMMENT '游戏账号ID',
    gold_amount DECIMAL(20,2) NOT NULL COMMENT '产出金币数量',
    revenue_amount DECIMAL(10,2) NOT NULL COMMENT '兑换分成金额',
    share_rate DECIMAL(5,4) NOT NULL COMMENT '分成比例',
    exchange_rate DECIMAL(10,4) DEFAULT 1.0000 COMMENT '金币兑换比例（金币->金额）',
    source_system VARCHAR(100) COMMENT '金币来源系统',
    source_batch_id VARCHAR(100) COMMENT '来源批次ID',
    recorded_at DATETIME COMMENT '记录时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_game_account_id (game_account_id),
    INDEX idx_recorded_at (recorded_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='金币分成记录表';

-- 第三方金币系统对接配置表
CREATE TABLE gold_system_config (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    system_name VARCHAR(100) NOT NULL COMMENT '系统名称',
    api_url VARCHAR(500) NOT NULL COMMENT 'API 地址',
    api_key VARCHAR(255) COMMENT 'API 密钥（加密存储）',
    game_account_id_field VARCHAR(50) COMMENT '游戏账号ID字段名',
    start_time_field VARCHAR(50) COMMENT '开始时间字段名',
    gold_amount_field VARCHAR(50) COMMENT '金币数量字段名',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    last_sync_at DATETIME COMMENT '最后同步时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_system_name (system_name),
    INDEX idx_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='第三方金币系统对接配置表';

-- 平台管理员表
CREATE TABLE admin_user (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    role ENUM('super_admin', 'operator') NOT NULL DEFAULT 'operator' COMMENT '角色',
    merchant_id BIGINT COMMENT '所属商户（平台管理员为 NULL）',
    status ENUM('active', 'disabled') DEFAULT 'active' COMMENT '状态',
    last_login_at DATETIME COMMENT '最后登录时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_username (username),
    INDEX idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='平台管理员表';

-- 商户用户表（商户子账号）
CREATE TABLE merchant_user (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    username VARCHAR(50) NOT NULL COMMENT '用户名',
    phone VARCHAR(20) NOT NULL COMMENT '手机号',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    role ENUM('owner', 'admin', 'operator') DEFAULT 'operator' COMMENT '角色（owner=所有者，admin=管理员，operator=操作员）',
    status ENUM('active', 'disabled') DEFAULT 'active' COMMENT '状态',
    last_login_at DATETIME COMMENT '最后登录时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_phone (phone),
    INDEX idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商户用户表';

-- 模板表（商户维度的自动化模板）
CREATE TABLE template (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    category VARCHAR(100) NOT NULL COMMENT '模板分类（如：common, game_a）',
    name VARCHAR(100) NOT NULL COMMENT '模板名称（如：main_menu, login_screen）',
    version VARCHAR(20) NOT NULL COMMENT '版本号（如：1.0.0）',
    content_type ENUM('image', 'json', 'script') NOT NULL COMMENT '内容类型',
    file_path VARCHAR(500) COMMENT '文件路径（本地存储路径）',
    file_size BIGINT COMMENT '文件大小（字节）',
    checksum VARCHAR(64) COMMENT '文件校验和（SHA-256）',
    is_current TINYINT(1) DEFAULT 1 COMMENT '是否为当前版本（1=是，0=否）',
    changelog TEXT COMMENT '更新日志',
    created_by BIGINT COMMENT '创建人（管理员ID）',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_category_name (category, name),
    INDEX idx_is_current (is_current),
    UNIQUE KEY uk_merchant_category_name_version (merchant_id, category, name, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模板表';

-- 串流账号表
CREATE TABLE streaming_account (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    name VARCHAR(100) NOT NULL COMMENT '账号名称',
    email VARCHAR(255) NOT NULL COMMENT '邮箱',
    password_encrypted VARCHAR(512) COMMENT '加密密码',
    auth_code VARCHAR(512) COMMENT '认证码(可为空)',
    status ENUM('idle', 'ready', 'running', 'paused', 'error') DEFAULT 'idle' COMMENT '状态',
    last_heartbeat DATETIME COMMENT '最后心跳时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_email (email),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='串流账号表';

-- Agent 实例表
CREATE TABLE agent_instance (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    hardware_config_id BIGINT COMMENT '硬件配置ID',
    agent_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Agent唯一标识',
    name VARCHAR(100) COMMENT 'Agent名称（如：电脑A-1）',
    host VARCHAR(255) NOT NULL COMMENT '主机地址',
    mac_address VARCHAR(17) COMMENT 'MAC物理地址（格式：XX:XX:XX:XX:XX:XX）',
    port INT NOT NULL COMMENT '端口',
    status ENUM('online', 'offline', 'busy') DEFAULT 'offline' COMMENT '状态',
    current_streaming_count INT DEFAULT 0 COMMENT '当前运行的串流数量',
    max_streaming_accounts INT DEFAULT 4 COMMENT '该Agent最大串流数量（由硬件配置决定）',
    auto_start_enabled TINYINT(1) DEFAULT 0 COMMENT '是否配置开机自启',
    wol_enabled TINYINT(1) DEFAULT 0 COMMENT '是否配置Wake-on-LAN',
    wol_broadcast_address VARCHAR(45) COMMENT 'WoL广播地址（如：192.168.1.255）',
    last_known_ip VARCHAR(45) COMMENT '最后已知IP',
    last_heartbeat DATETIME COMMENT '最后心跳时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_hardware_config_id (hardware_config_id),
    INDEX idx_status (status),
    INDEX idx_mac_address (mac_address)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent实例表';

-- Xbox 主机表
CREATE TABLE xbox_host (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    agent_id BIGINT NOT NULL COMMENT '所属 Agent ID（1 Agent = 1电脑）',
    streaming_account_id BIGINT COMMENT '当前绑定的串流账号ID',
    name VARCHAR(100) COMMENT 'Xbox 名称（如：Xbox One X-1）',
    ip_address VARCHAR(45) COMMENT 'Xbox IP 地址（IPv4/IPv6）',
    mac_address VARCHAR(17) COMMENT 'Xbox MAC 地址（用于唤醒）',
    gamertag VARCHAR(50) COMMENT '当前登录的 Gamertag',
    status ENUM('idle', 'online', 'streaming', 'error', 'offline', 'maintenance') DEFAULT 'idle' COMMENT '状态（idle=空闲, online=在线, streaming=串流中, error=异常, offline=离线, maintenance=维护中）',
    window_index INT NOT NULL COMMENT '窗口索引（对应 Agent 上的第 N 个 Xbox）',
    last_heartbeat DATETIME COMMENT '最后心跳时间',
    last_seen_at DATETIME COMMENT '最后在线时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_streaming_account_id (streaming_account_id),
    INDEX idx_ip_address (ip_address),
    UNIQUE KEY uk_agent_window (agent_id, window_index)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Xbox 主机表';

-- 串流任务表
CREATE TABLE streaming_task (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    xbox_host_id BIGINT NOT NULL COMMENT 'Xbox 主机ID',
    streaming_account_id BIGINT NOT NULL COMMENT '串流账号ID',
    game_account_id BIGINT COMMENT '当前使用的游戏账号ID',
    status ENUM('idle', 'starting', 'running', 'paused', 'stopping', 'completed', 'error') DEFAULT 'idle' COMMENT '状态',
    started_at DATETIME COMMENT '开始时间',
    finished_at DATETIME COMMENT '结束时间',
    error_message VARCHAR(500) COMMENT '错误信息',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_xbox_host_id (xbox_host_id),
    INDEX idx_streaming_account_id (streaming_account_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='串流任务表';
````

### 3.3 串流任务与自动化任务区别

**streaming\_task（串流任务表）**：

- 站在 Xbox 主机视角
- 记录 Xbox 的串流执行状态
- 一个 Xbox 同一时间只有一条记录
- 状态：idle / starting / running / paused / stopping / completed / error

**automation\_task（自动化任务表）**：

- 站在任务执行视角
- 记录每次自动化操作的完整历史
- 一个任务（start 请求）可能产生多条记录（如游戏账号切换）
- 状态：pending / running / paused / completed / failed / cancelled

**示例场景**：

1. 商户启动串流账号A → 创建 automation\_task（login 类型）+ streaming\_task（starting）
2. Xbox1 串流成功 → streaming\_task 状态变为 running
3. 3小时后切换到游戏账号B → 创建新的 automation\_task（game\_switch 类型）
4. 商户暂停 → streaming\_task 状态变为 paused
5. 商户恢复 → streaming\_task 状态恢复为 running

### 3.4 串流账号状态说明

| 状态      | 英文      | 说明       | 触发条件             |
| ------- | ------- | -------- | ---------------- |
| **空闲**  | idle    | 无任务执行    | 初始化、任务结束、用户终止    |
| **就绪中** | ready   | 登录+串流准备中 | 启动自动化，登录和串流步骤执行中 |
| **运行中** | running | 串流成功     | Xbox 连接成功，开始自动化  |
| **暂停中** | paused  | 暂停执行     | 用户主动暂停           |
| **异常**  | error   | 执行失败     | 登录失败、串流失败、异常断开   |

### 3.4 独占性约束

**业务规则：**

| 约束               | 说明                          |
| ---------------- | --------------------------- |
| **串流账号独占**       | 一个串流账号同一时间只能在一台 Xbox 上串流    |
| **游戏账号独占**       | 一个游戏账号同一时间只能在一台 Xbox 主机上登录  |
| **Xbox 独占**      | 一台 Xbox 主机只能串流一个串流账号（一对一）   |
| **Agent 多 Xbox** | 一个 Agent 可连接多台 Xbox 主机（多窗口） |
| **Agent 自主分配**   | 串流账号登录哪个 Xbox 由 Agent 按需分配  |

**层级关系：**

```
Agent (电脑) - 1 Agent = 1 台电脑
│
├── 窗口 0 → Xbox 主机 1 (IP: 192.168.1.50) → 串流账号 A
├── 窗口 1 → Xbox 主机 2 (IP: 192.168.1.51) → 串流账号 B
├── 窗口 2 → Xbox 主机 3 (IP: 192.168.1.52) → 串流账号 C
└── 窗口 3 → Xbox 主机 4 (IP: 192.168.1.53) → 串流账号 D
    ...

商户配置 Agent 时指定最大 Xbox 数量（如：4）
Agent 根据可用 Xbox 数量，动态分配串流账号到空闲 Xbox
```

**Agent 自主分配逻辑：**

```java
// Agent 端任务分配逻辑
public class AgentTaskAllocator {

    public XboxHost allocateXboxForStreaming(Long streamingAccountId) {
        // 1. 获取该串流账号下所有可用的游戏账号
        List<GameAccount> availableAccounts = getAvailableGameAccounts(streamingAccountId);

        // 2. 获取 Agent 管理的所有 Xbox（按状态筛选）
        List<XboxHost> idleXboxList = getIdleXboxHosts();

        // 3. 遍历找到第一个空闲的 Xbox
        for (XboxHost xbox : idleXboxList) {
            if (xbox.getStatus() == XboxStatus.IDLE) {
                // 绑定串流账号到 Xbox
                xbox.setStreamingAccountId(streamingAccountId);
                xbox.setStatus(XboxStatus.STREAMING);
                return xbox;
            }
        }

        // 4. 所有 Xbox 都在使用中，返回错误
        throw new BusinessException("无可用 Xbox 主机");
    }
}
```

**数据库层面实现：**

```sql
-- Xbox 主机表通过 streaming_account_id 直接关联串流账号
-- 无需额外的 locked_xbox_id 字段

-- 游戏账号表通过 locked_xbox_id 记录当前登录的 Xbox
ALTER TABLE game_account ADD COLUMN locked_xbox_id BIGINT;
CREATE INDEX idx_game_locked_xbox ON game_account(locked_xbox_id);
```

**锁定逻辑：**

```java
// 启动串流时 - Agent 自主分配 Xbox
@Service
public class StreamingService {

    // 云服务器下发任务给 Agent，Agent 自主选择空闲 Xbox
    public void requestStartStreaming(Long streamingAccountId, Long agentId) {
        // 1. 检查该串流账号是否已在某个 Xbox 上运行
        Optional<XboxHost> existingXbox = xboxHostRepo.findByStreamingAccountId(streamingAccountId);
        if (existingXbox.isPresent()) {
            throw new BusinessException("串流账号已在 Xbox " + existingXbox.get().getName() + " 上运行");
        }

        // 2. 检查该串流账号下游戏账号是否还有可用次数
        List<GameAccount> availableAccounts = gameAccountRepo
            .findByStreamingAccountIdAndStatus(streamingAccountId);
        boolean hasAvailable = availableAccounts.stream()
            .anyMatch(ga -> ga.getTodayMatchCount() < ga.getDailyMatchLimit());
        if (!hasAvailable) {
            throw new BusinessException("今日所有游戏账号已完成最大比赛次数");
        }

        // 3. 云服务器发送任务请求给 Agent
        // Agent 收到后自主选择空闲 Xbox 并绑定
        taskPublisher.publishStartStreamingTask(agentId, streamingAccountId);
    }
}

// Agent 端处理
@AgentEndpoint
public class AgentStreamingHandler {

    public XboxHost handleStartStreaming(Long streamingAccountId) {
        // 1. 获取所有空闲的 Xbox
        List<XboxHost> idleXboxList = xboxHostRepo.findByAgentIdAndStatus(agentId, "idle");

        if (idleXboxList.isEmpty()) {
            throw new BusinessException("无可用 Xbox 主机");
        }

        // 2. 选择第一个空闲 Xbox
        XboxHost xbox = idleXboxList.get(0);

        // 3. 绑定串流账号到 Xbox
        xbox.setStreamingAccountId(streamingAccountId);
        xbox.setStatus("streaming");
        xboxHostRepo.save(xbox);

        // 4. 创建串流任务记录
        StreamingTask task = new StreamingTask();
        task.setXboxHostId(xbox.getId());
        task.setStreamingAccountId(streamingAccountId);
        task.setStatus("starting");
        streamingTaskRepo.save(task);

        // 5. 开始自动化流程
        startAutomation(xbox, streamingAccountId);

        return xbox;
    }
}
```

**Xbox 状态变更流程：**

```
Xbox 状态: idle → streaming → idle
              ↑
              │ Agent 分配串流账号
              │
              ↓
         开始自动化
              │
              ├─ 正常结束 → idle
              │
              ├─ 异常错误 → error（需人工干预或自动重试）
              │
              └─ 暂停 → streaming（暂停后保持绑定）
```

**冲突检测时序：**

```
场景：账号 A 点击启动，但已被绑定在 Xbox-1 上运行

用户A 点击启动
    ↓
云服务器检查 xbox_host 表
    ↓
发现 streaming_account_id = 账号A 已存在于 Xbox-1
    ↓
❌ 拒绝启动，提示："串流账号 A 正在 Xbox-1 上运行，请先停止"

用户A 点击停止 Xbox-1
    ↓
Agent 解绑 Xbox-1 → streaming_account_id = null, status = idle
    ↓
再次点击启动
    ↓
Agent 收到任务，自主选择空闲 Xbox（如 Xbox-2）
    ↓
✅ 成功分配，Xbox-2 绑定账号 A
```

***

\-- 游戏账号表
CREATE TABLE game\_account (
id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
streaming\_id BIGINT NOT NULL COMMENT '所属串流账号ID',
name VARCHAR(100) NOT NULL COMMENT '游戏账号名称',
xbox\_gamertag VARCHAR(50) NOT NULL COMMENT 'Xbox Gamertag',
xbox\_live\_email VARCHAR(255) COMMENT 'Xbox Live 邮箱（用于账号切换）',
xbox\_live\_password\_encrypted VARCHAR(512) COMMENT '密码加密存储（AES）',
locked\_xbox\_id BIGINT COMMENT '当前登录的Xbox主机ID（NULL=未登录）',
is\_primary TINYINT(1) DEFAULT 0 COMMENT '是否主账号',
is\_active TINYINT(1) DEFAULT 1 COMMENT '是否启用',
priority INT DEFAULT 0 COMMENT '优先级（数字越小越优先，0=不设置按列表顺序）',
daily\_match\_limit INT DEFAULT 3 COMMENT '每日比赛次数限制',
today\_match\_count INT DEFAULT 0 COMMENT '今日已完成比赛数',
total\_match\_count INT DEFAULT 0 COMMENT '历史总比赛数（仅记录）',
last\_used\_at DATETIME COMMENT '最后使用时间',
created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,
updated\_at DATETIME DEFAULT CURRENT\_TIMESTAMP ON UPDATE CURRENT\_TIMESTAMP,
INDEX idx\_streaming\_id (streaming\_id),
INDEX idx\_locked\_xbox\_id (locked\_xbox\_id),
UNIQUE KEY uk\_gamertag (xbox\_gamertag),
UNIQUE KEY uk\_email (xbox\_live\_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏账号表';

\-- 唯一性约束说明:
\-- 1. xbox\_gamertag 全局唯一：确保一个游戏账号只能出现在一个串流账号下
\-- 2. xbox\_live\_email 全局唯一：确保一个邮箱只能绑定一个游戏账号
\-- 3. 添加/编辑游戏账号时，系统自动校验 Gamertag 和邮箱是否已被其他串流账号使用
\-- 4. locked\_xbox\_id 用于标记当前登录的 Xbox，确保游戏账号独占性

\-- 比赛记录表
CREATE TABLE match\_record (
id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
streaming\_account\_id BIGINT NOT NULL COMMENT '串流账号ID',
game\_account\_id BIGINT NOT NULL COMMENT '游戏账号ID',
match\_type VARCHAR(50) COMMENT '比赛类型',
started\_at DATETIME NOT NULL COMMENT '开始时间',
finished\_at DATETIME COMMENT '结束时间',
duration\_seconds INT COMMENT '持续时长（秒）',
result ENUM('win', 'lose', 'draw', 'ongoing') DEFAULT 'ongoing' COMMENT '结果',
status ENUM('playing', 'completed', 'interrupted') DEFAULT 'playing' COMMENT '状态',
created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,
INDEX idx\_streaming\_account\_id (streaming\_account\_id),
INDEX idx\_game\_account\_id (game\_account\_id),
INDEX idx\_started\_at (started\_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='比赛记录表';

\-- Agent 实例表
CREATE TABLE agent\_instance (
id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
agent\_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Agent唯一标识',
host VARCHAR(255) NOT NULL COMMENT '主机地址',
port INT NOT NULL COMMENT '端口',
status ENUM('online', 'offline', 'busy') DEFAULT 'offline' COMMENT '状态',
current\_streaming\_id BIGINT COMMENT '当前执行的串流账号ID',
current\_task\_id BIGINT COMMENT '当前任务ID',
last\_heartbeat DATETIME COMMENT '最后心跳时间',
created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,
updated\_at DATETIME DEFAULT CURRENT\_TIMESTAMP ON UPDATE CURRENT\_TIMESTAMP,
INDEX idx\_agent\_id (agent\_id),
INDEX idx\_status (status),
INDEX idx\_current\_streaming\_id (current\_streaming\_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent实例表';

\-- 自动化任务表
CREATE TABLE automation\_task (
id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
agent\_id BIGINT COMMENT '执行的Agent',
streaming\_id BIGINT NOT NULL COMMENT '串流账号ID',
game\_id BIGINT COMMENT '游戏账号ID',
task\_type ENUM('login', 'stream', 'game\_switch', 'custom') NOT NULL COMMENT '任务类型',
status ENUM('pending', 'running', 'paused', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
started\_at DATETIME COMMENT '开始时间',
finished\_at DATETIME COMMENT '结束时间',
result JSON COMMENT '执行结果',
created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,
updated\_at DATETIME DEFAULT CURRENT\_TIMESTAMP ON UPDATE CURRENT\_TIMESTAMP,
INDEX idx\_agent\_id (agent\_id),
INDEX idx\_streaming\_id (streaming\_id),
INDEX idx\_status (status),
INDEX idx\_created\_at (created\_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动化任务表';

\-- 任务历史统计表 (每日统计)
CREATE TABLE task\_statistics (
id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
streaming\_id BIGINT NOT NULL,
game\_id BIGINT,
stat\_date DATE NOT NULL,
total\_tasks INT DEFAULT 0,
completed\_tasks INT DEFAULT 0,
failed\_tasks INT DEFAULT 0,
total\_duration\_seconds BIGINT DEFAULT 0,
created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,
updated\_at DATETIME DEFAULT CURRENT\_TIMESTAMP ON UPDATE CURRENT\_TIMESTAMP,
UNIQUE KEY uk\_stream\_game\_date (streaming\_id, game\_id, stat\_date),
INDEX idx\_stat\_date (stat\_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务统计表';

\-- 告警表
CREATE TABLE alert (
id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
merchant\_id BIGINT NOT NULL COMMENT '所属商户ID',
agent\_id BIGINT COMMENT '关联的Agent ID',
xbox\_host\_id BIGINT COMMENT '关联的Xbox ID',
streaming\_account\_id BIGINT COMMENT '关联的串流账号ID',
type VARCHAR(50) NOT NULL COMMENT '告警类型',
severity ENUM('LOW', 'MEDIUM', 'HIGH', 'CRITICAL') NOT NULL COMMENT '严重程度',
message TEXT NOT NULL COMMENT '告警消息',
status ENUM('pending', 'acknowledged', 'resolved', 'ignored') DEFAULT 'pending' COMMENT '状态',
acknowledged\_at DATETIME COMMENT '确认时间',
acknowledged\_by BIGINT COMMENT '确认人（管理员ID）',
resolved\_at DATETIME COMMENT '解决时间',
metadata JSON COMMENT '附加数据',
created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,
updated\_at DATETIME DEFAULT CURRENT\_TIMESTAMP ON UPDATE CURRENT\_TIMESTAMP,
INDEX idx\_merchant\_id (merchant\_id),
INDEX idx\_agent\_id (agent\_id),
INDEX idx\_type (type),
INDEX idx\_severity (severity),
INDEX idx\_status (status),
INDEX idx\_created\_at (created\_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='告警表';

\-- 操作日志表
CREATE TABLE operation\_log (
id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
merchant\_id BIGINT NOT NULL COMMENT '所属商户ID',
user\_id BIGINT COMMENT '操作用户ID（商户用户或管理员）',
user\_type ENUM('merchant', 'admin', 'system') DEFAULT 'merchant' COMMENT '用户类型',
module VARCHAR(50) NOT NULL COMMENT '操作模块',
action VARCHAR(100) NOT NULL COMMENT '操作动作',
target\_type VARCHAR(50) COMMENT '操作对象类型',
target\_id BIGINT COMMENT '操作对象ID',
request\_ip VARCHAR(45) COMMENT '请求IP',
request\_method VARCHAR(10) COMMENT '请求方法',
request\_path VARCHAR(255) COMMENT '请求路径',
request\_body TEXT COMMENT '请求body（脱敏）',
response\_status INT COMMENT '响应状态码',
error\_message TEXT COMMENT '错误信息',
execution\_time\_ms INT COMMENT '执行时长（毫秒）',
metadata JSON COMMENT '附加数据（如旧值、新值）',
created\_at DATETIME DEFAULT CURRENT\_TIMESTAMP,
INDEX idx\_merchant\_id (merchant\_id),
INDEX idx\_user\_id (user\_id),
INDEX idx\_module (module),
INDEX idx\_action (action),
INDEX idx\_target (target\_type, target\_id),
INDEX idx\_created\_at (created\_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='操作日志表';

\-- 告警类型说明:
\-- AGENT\_OFFLINE: Agent离线
\-- AGENT\_ERROR: Agent异常
\-- XBOX\_OFFLINE: Xbox离线
\-- XBOX\_ERROR: Xbox异常
\-- TASK\_FAILED: 任务失败
\-- MERCHANT\_EXPIRING: 商户即将过期
\-- MERCHANT\_EXPIRED: 商户已过期
\-- HEARTBEAT\_TIMEOUT: 心跳超时
\-- TEMPLATE\_UPDATE\_FAILED: 模板更新失败

````

---

## 四、后端 API 设计

### 4.0 统一规范

#### 4.0.1 统一响应格式

```json
// 成功响应
{
  "code": 200,
  "message": "success",
  "data": { ... }
}

// 错误响应
{
  "code": 400,
  "message": "错误描述",
  "data": null
}
```

#### 4.0.2 统一分页规范

```typescript
// 分页请求参数
interface PageRequest {
  page: number;       // 当前页码 (从1开始)
  pageSize: number;   // 每页条数 (默认10)
  sortField?: string; // 排序字段
  sortOrder?: 'asc' | 'desc'; // 排序方向
}

// 分页响应格式
{
  "code": 200,
  "message": "success",
  "data": {
    "list": [...],
    "pagination": {
      "page": 1,
      "pageSize": 10,
      "total": 100,
      "totalPages": 10
    }
  }
}
```

#### 4.0.3 分页API示例

```
GET /api/streaming?page=1&pageSize=10&sortField=created_at&sortOrder=desc

GET /api/streaming?page=1&pageSize=10&keyword=测试&status=running
```

### 4.1 认证 API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/auth/login | 商户登录（点卡验证码） |
| POST | /api/auth/logout | 登出 |
| GET | /api/auth/me | 获取当前用户信息 |
| POST | /api/auth/validate | 验证商户状态（检查到期/余额） |

**POST /api/auth/login** - 商户登录（点卡验证码）
```json
// Request
{
  "activationCode": "A1B2-C3D4-E5F6"
}

// 验证流程：
// 1. 检查 Redis 中是否存在该验证码 key
// 2. 存在则验证通过，删除 Redis key，写入 MySQL 使用记录
// 3. 不存在则返回 401

// Response 200
{
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "merchant": {
    "id": 1,
    "name": "商户A",
    "vipLevel": "vip",
    "expireAt": "2024-02-15T00:00:00Z",
    "timezone": "Asia/Shanghai"
  }
}

// Response 401
{
  "error": "INVALID_CODE",
  "message": "验证码无效或已使用"
}
````

**Redis 点卡验证码存储方案：**

```java
// Redis Key 设计
Key: "activation_code:{code}"
Value: JSON {"merchantId": 1, "vipLevel": "vip", ...}
TTL: 24小时（过期自动删除）

// 生成验证码流程
1. 生成随机验证码 "A1B2-C3D4-E5F6"
2. 检查 Redis: EXISTS activation_code:A1B2-C3D4-E5F6
3. 如果存在，重新生成，直到不存在
4. 写入 Redis (SETEX 24小时)
5. 写入 MySQL activation_code 表

// 登录验证流程
1. 接收验证码 "A1B2-C3D4-E5F6"
2. 检查 Redis: GET activation_code:A1B2-C3D4-E5F6
3. 不存在 → 返回 401
4. 存在 → 获取商户信息，删除 Redis key，写入 MySQL 使用记录
```

### 4.1 商户管理 (平台管理员)

| 方法     | 路径                               | 说明       |
| ------ | -------------------------------- | -------- |
| GET    | /api/merchants                   | 获取商户列表   |
| GET    | /api/merchants/{id}              | 获取商户详情   |
| POST   | /api/merchants                   | 新增商户     |
| PUT    | /api/merchants/{id}              | 更新商户     |
| DELETE | /api/merchants/{id}              | 删除商户     |
| PUT    | /api/merchants/{id}/status       | 修改商户状态   |
| PUT    | /api/merchants/{id}/vip-level    | 修改会员等级   |
| GET    | /api/merchants/{id}/gold-revenue | 获取金币分成记录 |
| GET    | /api/merchants/{id}/balance-log  | 获取余额变动记录 |

**POST /api/merchants** - 新增商户

```json
// Request
{
  "name": "商户A",
  "contactPerson": "张三",
  "phone": "13800138000",
  "email": "merchant@example.com",
  "vipLevel": "vip",
  "expireAt": "2024-02-15"
}
```

### 4.2 VIP 价格配置 (平台管理员)

| 方法     | 路径                   | 说明            |
| ------ | -------------------- | ------------- |
| GET    | /api/vip-prices      | 获取所有 VIP 价格配置 |
| POST   | /api/vip-prices      | 新增 VIP 价格配置   |
| PUT    | /api/vip-prices/{id} | 更新 VIP 价格配置   |
| DELETE | /api/vip-prices/{id} | 删除 VIP 价格配置   |

**POST /api/vip-prices** - 新增价格配置

```json
// Request
{
  "vipLevel": "vip",       // vip / svip
  "billingType": "monthly", // weekly / monthly / yearly / unlimited
  "price": 299.00,
  "durationDays": 30,
  "revenueShareRate": 0.30  // 仅 unlimited 类型需要
}
```

**响应示例：**

```json
// VIP 价格列表
[
  {"vipLevel": "vip", "billingType": "weekly", "price": 99.00, "durationDays": 7},
  {"vipLevel": "vip", "billingType": "monthly", "price": 299.00, "durationDays": 30},
  {"vipLevel": "vip", "billingType": "yearly", "price": 2999.00, "durationDays": 365},
  {"vipLevel": "vip", "billingType": "unlimited", "price": 199.00, "durationDays": 30, "revenueShareRate": 0.30},
  {"vipLevel": "svip", "billingType": "weekly", "price": 199.00, "durationDays": 7},
  {"vipLevel": "svip", "billingType": "monthly", "price": 599.00, "durationDays": 30},
  {"vipLevel": "svip", "billingType": "yearly", "price": 5999.00, "durationDays": 365},
  {"vipLevel": "svip", "billingType": "unlimited", "price": 399.00, "durationDays": 30, "revenueShareRate": 0.40}
]
```

### 4.3 点卡验证码管理 (平台管理员)

| 方法     | 路径                        | 说明        |
| ------ | ------------------------- | --------- |
| GET    | /api/merchants/{id}/codes | 获取商户的点卡列表 |
| POST   | /api/merchants/{id}/codes | 生成点卡验证码   |
| DELETE | /api/codes/{code}         | 删除验证码     |

### 4.4 串流账号管理 (商户)

| 方法     | 路径                         | 说明       |
| ------ | -------------------------- | -------- |
| GET    | /api/streaming             | 获取串流账号列表 |
| GET    | /api/streaming/{id}        | 获取单个账号详情 |
| POST   | /api/streaming             | 新增串流账号   |
| PUT    | /api/streaming/{id}        | 更新串流账号   |
| DELETE | /api/streaming/{id}        | 删除串流账号   |
| GET    | /api/streaming/{id}/status | 获取账号实时状态 |
| POST   | /api/streaming/{id}/start  | 启动自动化    |
| POST   | /api/streaming/{id}/pause  | 暂停自动化    |
| POST   | /api/streaming/{id}/resume | 恢复自动化    |
| POST   | /api/streaming/{id}/stop   | 停止自动化    |

### 4.5 游戏账号管理 (商户)

| 方法     | 路径                         | 说明       |
| ------ | -------------------------- | -------- |
| GET    | /api/streaming/{sid}/games | 获取游戏账号列表 |
| POST   | /api/streaming/{sid}/games | 新增游戏账号   |
| PUT    | /api/game/{id}             | 更新游戏账号   |
| DELETE | /api/game/{id}             | 删除游戏账号   |
| PUT    | /api/game/{id}/priority    | 设置优先级    |
| POST   | /api/game/{id}/set-primary | 设为主账号    |

### 4.6 Agent 管理

| 方法     | 路径                      | 说明          |
| ------ | ----------------------- | ----------- |
| GET    | /api/agents             | 获取 Agent 列表 |
| GET    | /api/agents/{id}        | 获取 Agent 详情 |
| PUT    | /api/agents/{id}/config | 更新 Agent 配置 |
| POST   | /api/agent/register     | Agent 注册    |
| POST   | /api/agent/heartbeat    | Agent 心跳    |
| DELETE | /api/agent/{id}         | 删除 Agent    |

### 4.7 硬件配置管理 (平台管理员)

| 方法     | 路径                         | 说明       |
| ------ | -------------------------- | -------- |
| GET    | /api/hardware-configs      | 获取所有硬件配置 |
| POST   | /api/hardware-configs      | 新增硬件配置   |
| PUT    | /api/hardware-configs/{id} | 更新硬件配置   |
| DELETE | /api/hardware-configs/{id} | 删除硬件配置   |

**POST /api/hardware-configs** - 新增硬件配置

```json
// Request
{
  "name": "高配版",
  "cpuCores": 16,
  "memoryGb": 32,
  "gpuModel": "RTX 3080",
  "gpuCount": 1,
  "maxConcurrentStreams": 8,
  "maxConcurrentTasks": 16
}
```

### 4.8 任务管理

| 方法  | 路径                        | 说明        |
| --- | ------------------------- | --------- |
| GET | /api/tasks                | 获取任务列表    |
| GET | /api/tasks/{id}           | 获取任务详情    |
| GET | /api/streaming/{id}/tasks | 获取账号的任务历史 |
| GET | /api/statistics           | 获取统计信息    |

### 4.9 智能任务分配

**任务分配策略：**

```
商户启动串流账号自动化
        ↓
┌───────────────────────────────────────────────────────────────┐
│                    后端任务分配服务                            │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  1. 获取该串流账号下所有游戏账号                                 │
│         ↓                                                      │
│  2. 检查每个游戏账号的今日完成次数                               │
│         ↓                                                      │
│  ┌────────────────────┴────────────────────┐                  │
│  │          所有账号都达到今日上限？          │                  │
│  └────────────────────┬────────────────────┘                  │
│                       │                                        │
│                    Yes │ No                                    │
│             ┌─────────┴─────────┐                             │
│             ↓                   ↓                              │
│         返回错误            过滤出可用账号                       │
│    "今日所有游戏账号已完成      ↓                               │
│     最大比赛次数，无法启动"    继续进行Agent分配                  │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

**游戏账号可用性检查：**

```
┌───────────────────────────────────────────────────────────────┐
│                   游戏账号每日次数检查                          │
├───────────────────────────────────────────────────────────────┤
│                                                                │
│  每个游戏账号有配置：                                           │
│  - daily_max_matches: 每日最大比赛次数                         │
│  - completed_today: 今日已完成次数（按商户时区重置）             │
│                                                                │
│  检查逻辑：                                                     │
│  if (completed_today >= daily_max_matches) {                  │
│      // 该账号今日不可用                                       │
│  } else {                                                     │
│      // 该账号今日可用                                         │
│  }                                                             │
│                                                                │
│  串流账号下所有游戏账号都不可用时：                              │
│  → 返回错误："今日所有游戏账号已完成最大比赛次数"                 │
│  → 该串流账号今日不能启动自动化                                  │
│                                                                │
└───────────────────────────────────────────────────────────────┘
```

**Agent 负载均衡分配 API：**

```java
// POST /api/streaming/{id}/start - 智能分配
@Service
public class TaskAllocationService {

    @Transactional
    public Task allocateTask(Long streamingAccountId) {
        StreamingAccount account = streamingAccountRepo.findById(streamingAccountId);
        Long merchantId = account.getMerchantId();

        // 1. 检查该串流账号下所有游戏账号的今日完成情况
        List<GameAccount> gameAccounts = gameAccountRepo.findByStreamingAccountId(streamingAccountId);
        if (gameAccounts.isEmpty()) {
            throw new BusinessException("该串流账号下没有绑定游戏账号");
        }

        // 2. 检查是否有可用账号（未达到每日上限）
        List<GameAccount> availableAccounts = gameAccounts.stream()
            .filter(ga -> ga.getCompletedToday() < ga.getDailyMaxMatches())
            .collect(Collectors.toList());

        if (availableAccounts.isEmpty()) {
            throw new BusinessException("今日所有游戏账号已完成最大比赛次数，无法启动自动化");
        }

        // 3. 获取商户下所有在线 Agent（按负载升序）
        List<AgentInstance> agents = agentRepo.findByMerchantIdAndStatusOrderByLoad(
            merchantId, "online");

        // 4. 遍历找到第一个未满载的 Agent
        for (AgentInstance agent : agents) {
            if (agent.getCurrentStreamingCount() < agent.getMaxStreamingAccounts()) {
                // 分配任务给该 Agent
                return createTask(account, agent);
            }
        }

        // 5. 所有 Agent 都满载
        throw new BusinessException("无可用 Agent，所有 Agent 均已达最大串流数量");
    }

    @Transactional
    public List<Task> allocateBatchTasks(List<Long> streamingAccountIds) {
        List<Task> tasks = new ArrayList<>();

        for (Long accountId : streamingAccountIds) {
            try {
                Task task = allocateTask(accountId);
                tasks.add(task);
            } catch (BusinessException e) {
                log.warn("账号 {} 分配失败: {}", accountId, e.getMessage());
            }
        }
        return tasks;
    }
}
```

**游戏账号可用性判断 API：**

| 方法  | 路径                                       | 说明           |
| --- | ---------------------------------------- | ------------ |
| GET | /api/streaming/{id}/game-accounts/status | 获取游戏账号今日完成状态 |

**GET /api/streaming/{id}/game-accounts/status** - 游戏账号今日状态

```json
// Response 200
{
  "streamingAccountId": 1,
  "streamingAccountName": "账号1",
  "gameAccounts": [
    {
      "gameAccountId": 1,
      "gameName": " 游戏A",
      "dailyMaxMatches": 20,
      "completedToday": 18,
      "remaining": 2,
      "status": "available"
    },
    {
      "gameAccountId": 2,
      "gameName": "游戏B",
      "dailyMaxMatches": 20,
      "completedToday": 20,
      "remaining": 0,
      "status": "exhausted"
    }
  ],
  "canStartToday": true,
  "message": "有1个游戏账号今日还可使用"
}
```

**Agent 使用监控 API：**

| 方法  | 路径                               | 说明                        |
| --- | -------------------------------- | ------------------------- |
| GET | /api/merchants/{id}/agents/usage | 获取商户下所有 Agent 使用情况        |
| GET | /api/agents/{id}/xbox-hosts      | 获取单个 Agent 下的所有 Xbox 主机状态 |
| GET | /api/agents/{id}/status          | 获取单个 Agent 详细状态           |

**GET /api/merchants/{id}/agents/usage** - 商户 Agent 使用情况

```json
// Response 200
{
  "merchantId": 1,
  "totalAgents": 2,
  "onlineAgents": 2,
  "totalXboxCount": 6,
  "activeStreamingCount": 4,
  "agents": [
    {
      "agentId": "agent-001",
      "name": "电脑A",
      "status": "online",
      "xboxCount": 4,
      "idleXboxCount": 1,
      "streamingXboxCount": 3,
      "xboxHosts": [
        {
          "xboxHostId": 1,
          "name": "Xbox-1",
          "ipAddress": "192.168.1.50",
          "windowIndex": 0,
          "status": "streaming",
          "streamingAccountId": 1,
          "streamingAccountName": "串流账号A",
          "currentGameAccount": "主账号A",
          "gamertag": "PlayerOne"
        },
        {
          "xboxHostId": 2,
          "name": "Xbox-2",
          "ipAddress": "192.168.1.51",
          "windowIndex": 1,
          "status": "streaming",
          "streamingAccountId": 2,
          "streamingAccountName": "串流账号B",
          "currentGameAccount": "主账号B",
          "gamertag": "PlayerTwo"
        },
        {
          "xboxHostId": 3,
          "name": "Xbox-3",
          "ipAddress": "192.168.1.52",
          "windowIndex": 2,
          "status": "idle",
          "streamingAccountId": null,
          "streamingAccountName": null,
          "currentGameAccount": null,
          "gamertag": null
        }
      ]
    },
    {
      "agentId": "agent-002",
      "name": "电脑B",
      "status": "online",
      "xboxCount": 2,
      "idleXboxCount": 0,
      "streamingXboxCount": 2,
      "xboxHosts": [
        {
          "xboxHostId": 4,
          "name": "Xbox-1",
          "ipAddress": "192.168.2.50",
          "windowIndex": 0,
          "status": "streaming",
          "streamingAccountId": 3,
          "streamingAccountName": "串流账号C",
          "currentGameAccount": "主账号C",
          "gamertag": "PlayerThree"
        },
        {
          "xboxHostId": 5,
          "name": "Xbox-2",
          "ipAddress": "192.168.2.51",
          "windowIndex": 1,
          "status": "streaming",
          "streamingAccountId": 4,
          "streamingAccountName": "串流账号D",
          "currentGameAccount": "主账号D",
          "gamertag": "PlayerFour"
        }
      ]
    }
  ]
}
```

**GET /api/agents/{id}/xbox-hosts** - Agent 下的 Xbox 主机列表

```json
// Response 200
{
  "agentId": "agent-001",
  "agentName": "电脑A",
  "status": "online",
  "xboxCount": 4,
  "xboxHosts": [
    {
      "xboxHostId": 1,
      "name": "Xbox-1",
      "ipAddress": "192.168.1.50",
      "macAddress": "AA:BB:CC:DD:EE:FF",
      "windowIndex": 0,
      "status": "streaming",
      "streamingAccountId": 1,
      "streamingAccountName": "串流账号A",
      "currentGameAccountName": "主账号A",
      "todayMatchCount": 15,
      "dailyMaxMatches": 20,
      "lastHeartbeat": "2024-01-15T10:30:00Z"
    },
    {
      "xboxHostId": 2,
      "name": "Xbox-2",
      "ipAddress": "192.168.1.51",
      "macAddress": "11:22:33:44:55:66",
      "windowIndex": 1,
      "status": "idle",
      "streamingAccountId": null,
      "streamingAccountName": null,
      "currentGameAccountName": null,
      "todayMatchCount": 0,
      "dailyMaxMatches": 20,
      "lastHeartbeat": "2024-01-15T10:30:00Z"
    }
  ]
}
```

**Agent 满载时的处理策略：**

| 策略       | 说明                         |
| -------- | -------------------------- |
| **立即拒绝** | 返回错误，让用户等待                 |
| **排队等待** | 将任务加入队列，等 Xbox 空闲时自动分配     |
| **推荐空闲** | 返回建议，告诉用户哪个 Agent 有空闲 Xbox |

**游戏账号耗尽时的提示信息：**

| 场景   | 错误信息                        | 说明               |
| ---- | --------------------------- | ---------------- |
| 全部耗尽 | "今日所有游戏账号已完成最大比赛次数，无法启动自动化" | 串流账号下所有游戏账号都达到上限 |
| 部分可用 | "有 X 个游戏账号今日还可使用"           | 允许启动，但只能使用部分账号   |
| 无账号  | "该串流账号下没有绑定游戏账号"            | 需要先绑定游戏账号        |

### 4.10 API 详细规范

#### 串流账号 API

**POST /api/streaming** - 新增串流账号

```json
// Request
{
  "name": "账号1",
  "email": "user@outlook.com",
  "password": "明文密码(前端加密后传输)",
  "authCode": "可选认证码"
}

// Response 201
{
  "id": 1,
  "name": "账号1",
  "email": "user@outlook.com",
  "status": "idle",
  "createdAt": "2024-01-15T10:30:00Z"
}
```

**POST /api/streaming/{id}/start** - 启动自动化

```json
// Request
{
  "gameAccountId": 1,       // 可选：指定游戏账号
  "agentId": "agent-001",   // 可选：指定 Agent
  "autoStream": true,
  "autoSwitchGame": false
}

// Response 200
{
  "taskId": 123,
  "status": "pending",
  "assignedAgent": "agent-001"
}
```

#### Agent API

**POST /api/agent/register** - Agent 注册（携带安装码）

```json
// Request - 首次注册需要安装码
{
  "installCode": "XST4-A7K2-M9N3-P5L8",
  "host": "192.168.1.100",
  "port": 9999,
  "macAddress": "AA:BB:CC:DD:EE:FF",
  "xboxConfigs": [
    {"windowIndex": 0, "ipAddress": "192.168.1.50", "name": "Xbox-1", "macAddress": "11:22:33:44:55:66"},
    {"windowIndex": 1, "ipAddress": "192.168.1.51", "name": "Xbox-2", "macAddress": "22:33:44:55:66:77"},
    {"windowIndex": 2, "ipAddress": "192.168.1.52", "name": "Xbox-3", "macAddress": "33:44:55:66:77:88"},
    {"windowIndex": 3, "ipAddress": "192.168.1.53", "name": "Xbox-4", "macAddress": "44:55:66:77:88:99"}
  ],
  "version": "1.0.0"
}

// Response 200
{
  "success": true,
  "agentId": "agent-001",
  "merchantId": 1,
  "config": {
    "heartbeatInterval": 30,
    "maxRestartCount": 3
  }
}

// Response 400 (安装码无效或已过期)
{
  "success": false,
  "error": "INSTALL_CODE_INVALID",
  "message": "安装码无效或已过期"
}
```

**POST /api/agent/register** - Agent 重连（已有 agentId）

```json
// Request - 重启后重连，携带已有的 agentId
{
  "agentId": "agent-001",
  "host": "192.168.1.100",
  "port": 9999,
  "macAddress": "AA:BB:CC:DD:EE:FF",
  "status": "online",
  "version": "1.0.0"
}

// Response 200
{
  "success": true,
  "agentId": "agent-001",
  "config": {}
}
```

**POST /api/agent/heartbeat** - Agent 心跳

```json
// Request
{
  "agentId": "agent-abc123",
  "status": "online",
  "windowCount": 2,
  "cpuUsage": 45.5,
  "memoryUsage": 62.3,
  "uptime": 3600,
  "macAddress": "AA:BB:CC:DD:EE:FF",
  "localIp": "192.168.1.100"
}

// Response 200
{
  "received": true,
  "serverTime": "2024-01-15T10:30:00Z",
  "pendingTasks": []  // 待执行的任务
}
```

**POST /api/agent/wol** - 唤醒 Agent（Wake-on-LAN）

```json
// Request
{
  "agentId": "agent-abc123"
}

// Response 200
{
  "success": true,
  "message": "唤醒数据包已发送到 MAC: AA:BB:CC:DD:EE:FF"
}

// Response 400 (Agent 未配置 WoL)
{
  "success": false,
  "message": "该 Agent 未配置 Wake-on-LAN 功能"
}
```

**POST /api/agents/wol/batch** - 批量唤醒 Agent

```json
// Request
{
  "agentIds": ["agent-001", "agent-002", "agent-003"]
}

// Response 200
{
  "results": [
    {"agentId": "agent-001", "success": true, "message": "已发送唤醒"},
    {"agentId": "agent-002", "success": true, "message": "已发送唤醒"},
    {"agentId": "agent-003", "success": false, "message": "Agent 不在线且未配置 WoL"}
  ]
}
```

#### 任务 API

**GET /api/tasks** - 获取任务列表

```json
// Query: ?status=running&agentId=agent-001&page=1&size=20

// Response 200
{
  "content": [
    {
      "id": 123,
      "streamingAccountId": 1,
      "streamingAccountName": "账号1",
      "gameAccountName": "主账号",
      "agentId": "agent-001",
      "taskType": "stream",
      "status": "running",
      "startedAt": "2024-01-15T10:00:00Z",
      "progress": 65
    }
  ],
  "totalElements": 50,
  "totalPages": 3,
  "currentPage": 1
}
```

***

## 五、WebSocket 实时通信

### 5.1 WebSocket 连接

```
连接地址: wss://{server}/ws/{clientType}
客户端类型: admin (管理后台) / agent (自动化Agent)

认证: 通过 URL 参数或首帧消息携带 token
```

### 5.2 消息格式

```json
{
  "type": "message_type",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": { }
}
```

### 5.3 消息类型定义

| type              | 方向             | 说明       |
| ----------------- | -------------- | -------- |
| `agent.register`  | Agent → Server | Agent 注册 |
| `agent.heartbeat` | Agent → Server | Agent 心跳 |
| `agent.status`    | Agent → Server | 实例状态上报   |
| `agent.log`       | Agent → Server | 日志推送     |
| `task.assigned`   | Server → Agent | 任务下发     |
| `task.cancelled`  | Server → Agent | 任务取消     |
| `admin.notify`    | Server → Admin | 通知推送     |
| `status.update`   | Server → Admin | 状态更新     |

### 5.4 状态更新消息 (Server → Admin)

```json
{
  "type": "status.update",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "entityType": "streaming_account",  // streaming_account | agent | task
    "entityId": 1,
    "status": "running",
    "progress": 45,
    "message": "正在连接Xbox...",
    "details": {
      "xboxIp": "192.168.1.50",
      "gameName": "Halo Infinite"
    }
  }
}
```

### 5.5 任务下发消息 (Server → Agent)

```json
{
  "type": "task.assigned",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "taskId": 123,
    "action": "start_stream",
    "streamingAccount": {
      "id": 1,
      "name": "账号1",
      "email": "user@outlook.com",
      "password": "encrypted_password"
    },
    "gameAccount": {
      "id": 1,
      "name": "主账号",
      "xboxLiveEmail": "game@live.com",
      "xboxLivePassword": "encrypted"
    },
    "automationConfig": {
      "autoLogin": true,
      "autoStream": true,
      "streamQuality": "1080p60"
    }
  }
}
```

### 5.6 日志推送消息 (Agent → Server → Admin)

```json
{
  "type": "agent.log",
  "timestamp": "2024-01-15T10:30:00Z",
  "data": {
    "agentId": "agent-001",
    "instanceId": "inst-001",
    "level": "INFO",  // DEBUG | INFO | WARN | ERROR
    "message": "模板匹配成功: guide_settings @ (0.45, 0.82)",
    "taskId": 123
  }
}
```

***

## 前端页面设计

### 5.1 主题风格：赛博朋克・霓虹电竞风

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           色彩系统                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【主色】                                                                  │
│  - 深黑底: #12121E                                                        │
│  - 次深色: #1A1A2E (卡片/侧边栏背景)                                       │
│  - 边框色: #2A2A3E (分隔线/边框)                                          │
│                                                                             │
│  【霓虹色】                                                                │
│  - 霓虹粉: #F50057 (主按钮/强调)                                          │
│  - 霓虹青: #00E5FF (次按钮/链接/图标)                                      │
│                                                                             │
│  【强调色】                                                                │
│  - 荧光紫: #9D00FF (特殊状态/标签)                                        │
│  - 电光黄: #FFEA00 (警告/金币相关)                                         │
│                                                                             │
│  【状态色】                                                                │
│  - 成功: #00FF88 (霓虹绿)                                                 │
│  - 失败: #FF3366 (霓虹红)                                                 │
│  - 警告: #FFEA00 (电光黄)                                                 │
│  - 信息: #00E5FF (霓虹青)                                                 │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**字体规范：**

- 标题字体: "Orbitron", "Montserrat Black", "Microsoft YaHei"
- 正文字体: "Inter", "Roboto", "Microsoft YaHei"
- 字号: H1=28px, H2=22px, H3=18px, 正文=14px, 小字=12px

**特效规范：**

- 霓虹发光: box-shadow: 0 0 20px rgba(245, 0, 87, 0.5)
- 故障风动效(Glitch): 用于大标题强调
- 科技感网格背景: linear-gradient + grid lines

### 5.2 页面结构

```
┌─────────────────────────────────────────────────────────────┐
│  XStreaming 管理平台                                          │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────┐                                                 │
│ │  Logo   │  串流账号  游戏账号  Agent管理  任务历史  统计   │
│ └─────────┘                                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐  │
│  │                                                      │  │
│  │                   主内容区域                          │  │
│  │                                                      │  │
│  │                                                      │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 页面功能

**串流账号管理**

- 账号列表（状态指示、最后心跳）
- 新增账号弹窗
- 编辑账号
- 删除确认
- 批量操作（启动/暂停/停止）

**游戏账号管理**

- 树形列表（串流账号 → 游戏账号）
- 主账号标记
- 游戏账号快速切换

**Agent 管理**

- 在线/离线状态
- 当前任务显示
- 心跳超时警告

**实时状态监控**

- WebSocket 实时推送
- 状态变化通知

### 5.3 页面详细设计

#### 5.3.1 串流账号列表页

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  串流账号管理                                           [+ 新增账号]        │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ 筛选: [全部状态 ▼]  [全部Agent ▼]              [🔍 搜索账号...]      │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ ☐ │ 账号名称  │ 邮箱              │ 状态      │ Agent    │ 操作     │  │
│  ├───┼───────────┼───────────────────┼───────────┼──────────┼─────────┤  │
│  │ ☐ │ 账号1    │ user1@outlook.com │ 🟢 运行中 │ Agent-01 │ ▶ ⏸ ✕  │  │
│  │ ☐ │ 账号2    │ user2@outlook.com │ 🟡 待启动 │ Agent-02 │ ▶ ⏸ ✕  │  │
│  │ ☐ │ 账号3    │ user3@outlook.com │ ⚫ 离线   │ --       │ ▶ ⏸ ✕  │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
│  [◀ 1 / 3 ▶]                                                    共 15 条  │
└─────────────────────────────────────────────────────────────────────────────┘
```

**账号操作按钮说明：**

| 按钮   | 图标 | 功能    | 状态限制                |
| ---- | -- | ----- | ------------------- |
| ▶ 启动 | 绿色 | 启动自动化 | 仅 idle/offline 状态   |
| ⏸ 暂停 | 黄色 | 暂停自动化 | 仅 running 状态        |
| ✕ 停止 | 红色 | 停止自动化 | 仅 running/paused 状态 |

#### 5.3.2 账号详情/编辑弹窗

```
┌─────────────────────────────────────────────────────────────────┐
│  编辑串流账号                                               [✕] │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  账号名称:  [账号1                                          ]   │
│                                                                  │
│  邮箱地址:  [user@outlook.com                                ]   │
│                                                                  │
│  密码:      [•••••••••••                                   ] 🔄 │
│                                                                  │
│  认证码:    [                                            ]   ?   │
│                                                                  │
│  关联游戏账号:                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ ☑ 主账号 - PlayerOne (xbox_live@live.com)              │   │
│  │ ☐ 副账号 - PlayerTwo (xbox_live2@live.com)              │   │
│  │ [+ 添加游戏账号]                                        │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                  │
│                              [取消]              [保存]           │
└─────────────────────────────────────────────────────────────────┘
```

#### 5.3.3 实时监控面板 (Dashboard)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  实时监控                                      [🔄 刷新] [📊 全屏]          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌─────────────┐  │
│  │   在线Agent   │  │   运行中任务   │  │   串流账号    │  │   今日错误   │  │
│  │               │  │               │  │               │  │             │  │
│  │     5/6      │  │     12        │  │    8/15       │  │     3       │  │
│  │   (83%)      │  │               │  │    (53%)      │  │             │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └─────────────┘  │
│                                                                             │
│  实时日志:                                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ [10:30:01] Agent-01 ▶ 账号1 开始串流 - 连接Xbox 192.168.1.50        │  │
│  │ [10:30:05] Agent-02 ▶ 账号2 模板匹配成功: login_button              │  │
│  │ [10:30:08] Agent-01 ⚠ 账号1 Xbox断开，准备重连...                   │  │
│  │ [10:30:12] Agent-03 ▶ 账号5 游戏账号切换: PlayerTwo                 │  │
│  │ [10:30:15] Agent-02 ✓ 账号2 串流成功，开始录制                        │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.3.4 Agent 管理页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  Agent 管理                                                                │
├─────────────────────────────────────────────────────────────────────────────┤
│  状态: [全部 ▼]  排序: [最后心跳 ▼]                    [+ 批量操作]         │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐  │
│  │ Agent ID      │ 主机地址       │ 状态    │ 负载  │ 最后心跳 │ 操作  │  │
│  ├───┼───────────┼────────────────┼─────────┼───────┼─────────┼───────┤  │
│  │ ● │ Agent-01 │ 192.168.1.101  │ 🟢 在线 │ 2/4   │ 10秒前  │详情 ✕ │  │
│  │ ● │ Agent-02 │ 192.168.1.102  │ 🟢 在线 │ 4/4   │ 5秒前   │详情 ✕ │  │
│  │ ○ │ Agent-03 │ 192.168.1.103  │ ⚫ 离线 │ --    │ 3分钟前 │详情 ✕ │  │
│  │ ● │ Agent-04 │ 192.168.1.104  │ 🟡 忙碌 │ 1/4   │ 30秒前  │详情 ✕ │  │
│  └─────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.3.5 串流账号页面（含控制台日志）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  串流账号管理                                                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  账号列表:                        控制台日志:                              │
│  ┌───────────────────────────┐   ┌─────────────────────────────────────┐  │
│  │ ☐ 账号1    🟢 运行中     │   │ [10:30:01] ▶ 开始自动化              │  │
│  │ ☐ 账号2    🟡 就绪中     │   │ [10:30:02] ▶ 正在连接 Xbox...        │  │
│  │ ☐ 账号3    ⚫ 空闲       │   │ [10:30:05] ▶ 微软登录成功              │  │
│  │ ☐ 账号4    🔴 异常       │   │ [10:30:08] ▶ 串流连接中...            │  │
│  └───────────────────────────┘   │ [10:30:12] ▶ 串流成功                │  │
│                                   │ [10:30:13] ▶ 进入 Xbox 主界面         │  │
│  操作:                            └─────────────────────────────────────┘  │
│  [▶ 启动] [⏸ 暂停] [⏹ 停止]                                               │
│                                                                             │
│  日志级别: [全部 ▼] [INFO ▼]    [🗑 清空] [📥 导出]                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**功能说明：**

1. **选择账号**：点击账号列表，该账号的日志显示在控制台
2. **实时推送**：选择启动自动化的账号后，日志实时显示
3. **日志级别**：支持 DEBUG/INFO/WARN/ERROR 筛选
4. **日志保存**：支持清空和导出

#### 5.3.6 浏览器监控窗口页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  窗口监控                                           [网格视图] [列表视图]  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │  │ ┌─────────┐ │     │
│  │ │  视频   │ │  │ │  视频   │ │  │ │  视频   │ │  │ │  视频   │ │     │
│  │ │  画面   │ │  │ │  画面   │ │  │ │  画面   │ │  │ │  画面   │ │     │
│  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │  │ └─────────┘ │     │
│  │ 账号1-就緒中 │  │ 账号2-运行中 │  │ 账号3-运行中 │  │ 账号4-空閒  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘     │
│                                                                             │
│  ┌─────────────────────────────┐                                            │
│  │                             │                                            │
│  │      视频画面放大展示       │  账号: 账号2                              │
│  │      (点击可全屏)          │  状态: 运行中                              │
│  │                             │  Agent: Agent-01                         │
│  │                             │  Xbox: 192.168.1.50                       │
│  │                             │  游戏: Halo Infinite                       │
│  │                             │  运行时长: 02:34:56                       │
│  │                             │                                            │
│  │                             │  [全屏] [关闭预览] [查看详情]              │
│  └─────────────────────────────┘                                            │
│                                                                             │
│  [📹 视频监控: ON ▼]   同时推送: [4 ▼] 路                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**功能说明：**

1. **缩略图网格**：所有运行中的窗口以小卡片展示
2. **点击放大**：点击任意窗口放大查看
3. **全屏模式**：支持浏览器全屏查看
4. **实时视频**：低延迟视频流推送
5. **控制不影响**：缩放/全屏只影响显示，不影响自动化运行
6. **手动开关**：用户可手动开启/关闭视频监控
7. **路数限制**：可设置同时推送的最大路数

### 5.3.7 低延迟视频监控方案

**技术选型：WebSocket + MJPEG（低延迟 \~100-200ms）**

| 方案                | 延迟        | 带宽占用 | 实现复杂度 | 推荐度   |
| ----------------- | --------- | ---- | ----- | ----- |
| WebSocket + MJPEG | 100-200ms | 中    | 低     | ⭐⭐⭐⭐⭐ |
| WebSocket + FLV   | 200-500ms | 低    | 中     | ⭐⭐⭐⭐  |
| WebRTC 点对点        | 50-100ms  | 低    | 高     | ⭐⭐⭐   |

**为什么选择 MJPEG？**

- 延迟比 FLV 低
- 实现比 WebRTC 简单
- 浏览器原生支持，无需额外解码库

**架构设计：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Agent 端                                       │
│                                                                             │
│  Electron 窗口                                                            │
│       │                                                                     │
│       ▼                                                                     │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐                   │
│  │ Frame       │     │ MJPEG       │     │ WebSocket   │                   │
│  │ Capture     │ ──► │ Encoder     │ ──► │ Server      │                   │
│  │ (60fps)     │     │ (30fps)     │     │ (:9999)     │                   │
│  └─────────────┘     └─────────────┘     └──────┬──────┘                   │
│                                                   │                         │
└───────────────────────────────────────────────────┼─────────────────────────┘
                                                    │
                                    ┌───────────────┼───────────────┐
                                    │               │               │
                                    ▼               ▼               ▼
                              ┌─────────┐     ┌─────────┐     ┌─────────┐
                              │ Browser │     │ Browser │     │ Browser │
                              │  客户端1 │     │  客户端2 │     │  客户端N │
                              └─────────┘     └─────────┘     └─────────┘
```

**实现代码：**

```python
# Agent 端 - MJPEG 视频流服务（带认证）
import asyncio
import io
import cv2
import websockets
import jwt
from typing import Set

class MJPEGStreamer:
    """MJPEG 视频流服务"""

    def __init__(self, port: int = 9999, jwt_secret: str = "your-secret"):
        self.port = port
        self.jwt_secret = jwt_secret
        self.clients: Set[websockets.WebSocketServerProtocol] = set()
        self.frame_cache = None
        self.quality = 30  # JPEG 质量 (0-100)
        self.max_clients = 8
        self._running = False

    async def start(self):
        """启动 MJPEG WebSocket 服务器"""
        self._running = True
        async with websockets.serve(self._handle_client, "0.0.0.0", self.port):
            logger.info(f"MJPEG 流服务器启动: ws://0.0.0.0:{self.port}")
            await asyncio.Future()  # 永久运行

    async def _handle_client(self, websocket):
        """处理客户端连接（带认证）"""
        # 1. 认证检查
        try:
            # 从 URL 参数获取 token
            # ws://host:port/stream/instanceId?token=xxx
            url = websocket.path
            params = self._parse_url_params(url)
            token = params.get('token', '')

            # 验证 JWT token
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])

            # 验证商户权限：该商户是否拥有该 streaming_account
            merchant_id = payload.get('merchant_id')
            streaming_account_id = params.get('instanceId')

            if not self._validate_merchant_access(merchant_id, streaming_account_id):
                logger.warning(f"商户 {merchant_id} 无权访问 {streaming_account_id}")
                await websocket.close(4001, "Unauthorized")
                return

            logger.info(f"商户 {merchant_id} 连接视频流: {streaming_account_id}")

        except jwt.ExpiredSignatureError:
            await websocket.close(4002, "Token expired")
            return
        except jwt.InvalidTokenError:
            await websocket.close(4003, "Invalid token")
            return
        except Exception as e:
            logger.error(f"认证错误: {e}")
            await websocket.close(4004, "Auth error")
            return

        # 2. 连接数检查
        if len(self.clients) >= self.max_clients:
            logger.warning("客户端数量已达上限，拒绝连接")
            await websocket.close(4005, "Max clients")
            return

        self.clients.add(websocket)
        logger.info(f"客户端连接: {len(self.clients)}/{self.max_clients}")

        try:
            # 发送 MIME 类型头
            await websocket.send("mjpeg")

            while self._running:
                if self.frame_cache is not None:
                    # 发送 JPEG 数据
                    await websocket.send(self.frame_cache)
                await asyncio.sleep(0.033)  # ~30fps

        except websockets.exceptions.ConnectionClosed:
            pass
        finally:
            self.clients.discard(websocket)
            logger.info(f"客户端断开: {len(self.clients)}/{self.max_clients}")

    def _parse_url_params(self, url: str) -> dict:
        """解析 URL 参数"""
        if '?' not in url:
            return {}
        query = url.split('?')[1]
        return {k: v for k, v in (p.split('=') for p in query.split('&'))}

    def _validate_merchant_access(self, merchant_id: int, streaming_account_id: str) -> bool:
        """验证商户是否有权访问该串流账号"""
        # 调用后端 API 验证
        # 或者通过共享的 JWT secret 验证 streaming_account 属于该商户
        return True  # TODO: 实现验证逻辑

    def update_frame(self, frame):
        """更新当前帧（由 Electron Bridge 调用）"""
        # 压缩为 JPEG
        encode_param = [int(cv2.IMWRITE_JPEG_QUALITY), self.quality]
        _, frame_bytes = cv2.imencode('.jpg', frame, encode_param)
        self.frame_cache = frame_bytes.tobytes()

    async def broadcast_frame(self, frame):
        """广播帧到所有客户端"""
        self.update_frame(frame)

# Electron Bridge 中捕获窗口画面
class ElectronBridge:
    def __init__(self, streamer: MJPEGStreamer):
        self.streamer = streamer

    async def capture_and_stream(self, window_id: str):
        """捕获窗口并推流"""
        while True:
            # 捕获窗口画面
            frame = await self.capture_window(window_id)

            # 发送到流服务器
            self.streamer.update_frame(frame)

            await asyncio.sleep(0.033)  # ~30fps
```

```javascript
// Electron 端 - 窗口画面捕获
const { desktopCapturer } = require('electron');

class WindowCapturer {
    constructor(streamer) {
        this.streamer = streamer;
    }

    async captureWindow(windowId) {
        const sources = await desktopCapturer.getSources({
            types: ['window'],
            thumbnailSize: { width: 640, height: 360 }
        });

        const source = sources.find(s => s.id === windowId);
        if (!source) return null;

        // 返回缩略图 (base64)
        return source.thumbnail.toDataURL();
    }

    startStreaming(windowId) {
        setInterval(async () => {
            const frame = await this.captureWindow(windowId);
            if (frame) {
                // 发送到 Agent
                fetch(`http://localhost:9999/stream/${windowId}`, {
                    method: 'POST',
                    body: frame
                });
            }
        }, 33); // ~30fps
    }
}
```

```vue
<!-- Vue 前端 - 视频显示组件 -->
<template>
  <div class="video-player">
    <img v-if="connected" :src="videoUrl" class="video-frame" />
    <div v-else class="video-placeholder">
      <span>视频未连接</span>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue';

const props = defineProps({
  instanceId: String,
  agentHost: String,
  agentPort: Number
});

const connected = ref(false);
const videoUrl = computed(() =>
  `ws://${props.agentHost}:${props.agentPort}/stream/${props.instanceId}`
);

let ws = null;

function connect() {
  ws = new WebSocket(videoUrl.value);

  ws.onopen = () => {
    connected.value = true;
    console.log('视频流连接成功');
  };

  ws.onmessage = (event) => {
    // 显示 JPEG 帧
    if (event.data !== 'mjpeg') {
      // 假设是二进制 JPEG 数据
      const blob = new Blob([event.data], { type: 'image/jpeg' });
      const url = URL.createObjectURL(blob);
      // 更新 img src
    }
  };

  ws.onclose = () => {
    connected.value = false;
    // 自动重连
    setTimeout(connect, 3000);
  };
}

onMounted(connect);
onUnmounted(() => ws?.close());
</script>
```

**带宽估算：**

| 分辨率       | FPS | JPEG 质量 | 单路带宽       |
| --------- | --- | ------- | ---------- |
| 640x360   | 30  | 30      | \~500 Kbps |
| 1280x720  | 30  | 30      | \~1.5 Mbps |
| 1920x1080 | 30  | 30      | \~3 Mbps   |

**推荐配置：**

- 分辨率：640x360（够用，带宽低）
- FPS：15-30
- JPEG 质量：20-30
- 最大同时推送：4-8 路

**手动控制：**

| 控制    | 说明                 |
| ----- | ------------------ |
| 开启/关闭 | 用户可手动开关视频监控        |
| 路数限制  | 可设置同时推送的最大路数（默认 4） |
| 按需推送  | 只推送当前选中的窗口，其他窗口暂停  |

#### 5.3.5 前端技术栈与组件

| 分类            | 技术                      | 说明          |
| ------------- | ----------------------- | ----------- |
| **框架**        | Vue 3 + Composition API | 响应式前端框架     |
| **UI 库**      | Element Plus            | PC 端 UI 组件库 |
| **状态管理**      | Pinia                   | Vue 3 状态管理  |
| **路由**        | Vue Router 4            | 页面路由        |
| **HTTP**      | Axios                   | API 请求      |
| **WebSocket** | socket.io-client        | 实时通信        |
| **图表**        | ECharts                 | 统计图表        |

#### 5.3.6 核心组件结构

```vue
src/
├── views/
│   ├── Dashboard.vue           # 监控仪表盘
│   ├── StreamingAccount.vue    # 串流账号管理
│   ├── GameAccount.vue         # 游戏账号管理
│   ├── Agent.vue               # Agent 管理
│   ├── TaskHistory.vue          # 任务历史
│   └── Statistics.vue          # 统计报表
│
├── components/
│   ├── StatusBadge.vue          # 状态徽章
│   ├── AccountCard.vue          # 账号卡片
│   ├── LogViewer.vue            # 日志查看器
│   ├── RealtimeChart.vue        # 实时图表
│   └── TaskProgress.vue         # 任务进度条
│
├── stores/
│   ├── account.js               # 账号状态
│   ├── agent.js                 # Agent 状态
│   └── websocket.js             # WebSocket 连接
│
└── api/
    ├── streaming.js             # 串流账号 API
    ├── game.js                  # 游戏账号 API
    ├── agent.js                 # Agent API
    └── websocket.js             # WebSocket 消息
```

***

## 七、Python Agent 架构

### 7.1 CentralManager 中央管理器

CentralManager 是 Python Agent 的核心组件，负责管理多个 StreamWindow 实例并与后端进行通信。

#### 类设计

```python
import asyncio
import logging
import uuid
from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
import socket
import websockets
import json

logger = logging.getLogger(__name__)


class AgentState(Enum):
    """Agent 状态枚举"""
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


@dataclass
class AccountConfig:
    """串流账号配置"""
    id: int
    name: str
    email: str
    password: str
    auth_code: str
    server_id: str
    merchant_id: int = 0


class CentralManager:
    """
    中央管理器 - 管理多个 StreamWindow 实例
    
    职责：
    - 管理多个 StreamWindow 实例
    - 分配唯一 Instance ID
    - 接收后端任务并分发
    - 汇总状态上报后端
    """

    def __init__(self, backend_url: str, agent_id: Optional[str] = None):
        self.backend_url = backend_url
        self.agent_id = agent_id or self._generate_agent_id()
        self.state = AgentState.STARTING
        self.windows: Dict[str, 'StreamWindow'] = {}
        self.running = True
        self.websocket = None
        self.heartbeat_task: Optional[asyncio.Task] = None
        self.listener_task: Optional[asyncio.Task] = None

    def _generate_agent_id(self) -> str:
        """生成唯一 Agent ID"""
        hostname = socket.gethostname()
        unique_id = str(uuid.uuid4())[:8]
        return f"agent_{hostname}_{unique_id}"

    async def start(self):
        """启动中央管理器"""
        logger.info(f"启动 CentralManager: {self.agent_id}")
        self.state = AgentState.RUNNING

        await self.register_to_backend()
        self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())
        self.listener_task = asyncio.create_task(self._listen_for_commands())

        logger.info(f"CentralManager 启动完成，当前管理 {len(self.windows)} 个窗口")

    async def stop(self):
        """停止中央管理器"""
        logger.info("停止 CentralManager")
        self.state = AgentState.STOPPING
        self.running = False

        for instance_id in list(self.windows.keys()):
            await self.stop_instance(instance_id)

        if self.heartbeat_task:
            self.heartbeat_task.cancel()
        if self.listener_task:
            self.listener_task.cancel()
        if self.websocket:
            await self.websocket.close()

        self.state = AgentState.STOPPED
        logger.info("CentralManager 已停止")

    async def register_to_backend(self):
        """向后端注册 Agent"""
        try:
            import requests
            response = requests.post(
                f"{self.backend_url}/api/agent/register",
                json={
                    "agentId": self.agent_id,
                    "host": socket.gethostname(),
                    "port": 8765,
                    "status": "online",
                    "capacity": 8
                },
                timeout=10
            )
            if response.status_code == 200:
                logger.info(f"Agent 注册成功: {response.json()}")
            else:
                logger.error(f"Agent 注册失败: {response.status_code}")
        except Exception as e:
            logger.error(f"Agent 注册异常: {e}")

    async def _heartbeat_loop(self):
        """心跳保活循环"""
        while self.running:
            try:
                await asyncio.sleep(30)
                await self._send_heartbeat()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"心跳发送异常: {e}")

    async def _send_heartbeat(self):
        """发送心跳"""
        try:
            import requests
            response = requests.post(
                f"{self.backend_url}/api/agent/heartbeat",
                json={
                    "agentId": self.agent_id,
                    "status": "online",
                    "windowCount": len(self.windows),
                    "windows": {
                        wid: {
                            "state": win.state.value if hasattr(win.state, 'value') else str(win.state),
                            "accountId": win.config.id if win.config else None
                        }
                        for wid, win in self.windows.items()
                    }
                },
                timeout=5
            )
        except Exception as e:
            logger.warning(f"心跳失败: {e}")

    async def _listen_for_commands(self):
        """监听后端命令"""
        while self.running:
            try:
                async with websockets.connect(
                    f"ws://{self.backend_url}/ws/agent/{self.agent_id}"
                ) as ws:
                    self.websocket = ws
                    logger.info("WebSocket 连接已建立")
                    
                    async for message in ws:
                        await self._handle_message(json.loads(message))
                        
            except websockets.exceptions.ConnectionClosed:
                logger.warning("WebSocket 连接断开，5秒后重连")
                await asyncio.sleep(5)
            except Exception as e:
                logger.error(f"WebSocket 异常: {e}")
                await asyncio.sleep(5)

    async def _handle_message(self, message: dict):
        """处理后端消息"""
        msg_type = message.get("type")
        data = message.get("data", {})

        if msg_type == "start_streaming":
            await self._handle_start_streaming(data)
        elif msg_type == "stop_streaming":
            await self._handle_stop_streaming(data)
        elif msg_type == "pause_streaming":
            await self._handle_pause_streaming(data)
        elif msg_type == "resume_streaming":
            await self._handle_resume_streaming(data)
        else:
            logger.warning(f"未知消息类型: {msg_type}")

    async def _handle_start_streaming(self, data: dict):
        """处理启动串流请求"""
        account_config = AccountConfig(**data["accountConfig"])
        instance_id = await self.start_streaming_account(account_config)
        
        await self._report_status(
            instance_id,
            "started",
            {"instanceId": instance_id}
        )

    async def _handle_stop_streaming(self, data: dict):
        """处理停止串流请求"""
        instance_id = data.get("instanceId")
        if instance_id:
            await self.stop_instance(instance_id)

    async def _handle_pause_streaming(self, data: dict):
        """处理暂停串流请求"""
        instance_id = data.get("instanceId")
        pause_type = data.get("pauseType", "idle")
        if instance_id and instance_id in self.windows:
            await self.windows[instance_id].pause(pause_type)

    async def _handle_resume_streaming(self, data: dict):
        """处理恢复串流请求"""
        instance_id = data.get("instanceId")
        if instance_id and instance_id in self.windows:
            await self.windows[instance_id].resume()

    async def start_streaming_account(self, account_config: AccountConfig) -> str:
        """
        为串流账号启动独立窗口
        返回 instance_id
        """
        instance_id = f"{self.agent_id}_{account_config.id}_{len(self.windows)}"

        from .stream_window import StreamWindow

        window = StreamWindow(
            instance_id=instance_id,
            config=account_config,
            on_state_change=lambda iid, state: self._on_window_state_change(iid, state)
        )

        await window.init()
        await window.start_streaming()

        self.windows[instance_id] = window

        asyncio.create_task(window.run_automation())

        return instance_id

    async def stop_instance(self, instance_id: str):
        """停止指定实例"""
        if instance_id in self.windows:
            await self.windows[instance_id].close()
            del self.windows[instance_id]
            logger.info(f"实例已停止: {instance_id}")

    async def _on_window_state_change(self, instance_id: str, state: Any):
        """窗口状态变更回调"""
        await self._report_status(instance_id, "state_changed", {"state": str(state)})

    async def _report_status(self, instance_id: str, event: str, data: dict):
        """上报状态到后端"""
        try:
            import requests
            requests.post(
                f"{self.backend_url}/api/agent/status",
                json={
                    "agentId": self.agent_id,
                    "instanceId": instance_id,
                    "event": event,
                    "data": data
                },
                timeout=5
            )
        except Exception as e:
            logger.warning(f"状态上报失败: {e}")
```

#### 与后端 WebSocket/REST 交互

```
┌─────────────────────────────────────────────────────────────────┐
│                     CentralManager                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────────┐         ┌──────────────────┐              │
│  │   REST Client   │         │  WebSocket Client │              │
│  │  (心跳/注册)    │         │   (命令监听)      │              │
│  └────────┬────────┘         └────────┬────────┘              │
│           │                           │                        │
│           ▼                           ▼                        │
│  ┌─────────────────────────────────────────────────┐          │
│  │              后端 Java Backend                    │          │
│  │   • /api/agent/register (注册)                    │          │
│  │   • /api/agent/heartbeat (心跳)                    │          │
│  │   • /api/agent/status (状态上报)                   │          │
│  │   • /ws/agent/{agentId} (WebSocket命令)            │          │
│  └─────────────────────────────────────────────────┘          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

#### 管理多个 StreamWindow 实例

```python
class CentralManager:
    def get_window(self, instance_id: str) -> Optional['StreamWindow']:
        """获取指定窗口实例"""
        return self.windows.get(instance_id)

    def get_all_windows(self) -> Dict[str, 'StreamWindow']:
        """获取所有窗口实例"""
        return self.windows.copy()

    def get_window_count(self) -> int:
        """获取当前窗口数量"""
        return len(self.windows)

    def is_window_running(self, instance_id: str) -> bool:
        """检查窗口是否正在运行"""
        window = self.windows.get(instance_id)
        return window is not None and window.is_running()
```

#### 数据流图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                            数据流                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  【后端 → Agent】                      【Agent → 后端】                   │
│                                                                          │
│  POST /api/agent/register              POST /api/agent/register          │
│  ────────────────────                 ───────────────────────          │
│  Response: {                          Request: {                         │
│    "agentId": "xxx",                     "agentId": "xxx",               │
│    "status": "registered"                "host": "hostname",             │
│  }                                        "port": 8765,                  │
│                                            "status": "online"            │
│                                            "capacity": 8                 │
│                                       }                                  │
│                                                                          │
│  WebSocket: ws://backend/ws/agent/{agentId}                              │
│  ─────────────────────────────────────────                              │
│  {                                                                   │
│    "type": "start_streaming",                                          │
│    "data": { "accountConfig": {...} }    ←── 后端下发启动任务             │
│  }                                                                   │
│                                                                          │
│  {                                                                   │
│    "type": "stop_streaming",                                           │
│    "data": { "instanceId": "xxx" }       ←── 后端下发停止任务             │
│  }                                                                   │
│                                                                          │
│                                       POST /api/agent/status             │
│                                       ────────────────────────          │
│                                       Request: {                        │
│                                         "agentId": "xxx",               │
│                                         "instanceId": "xxx",            │
│                                         "event": "state_changed",        │
│                                         "data": { "state": "running" }   │
│                                       }                            ───►│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.2 StreamWindow 串流窗口

StreamWindow 管理单个串流账号的独立 Electron 窗口，负责窗口生命周期管理和自动化执行。

#### 类设计

```python
import asyncio
import logging
import time
from typing import Optional, Callable, Any, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class WindowState(Enum):
    """窗口状态枚举"""
    INITIALIZING = "initializing"
    READY = "ready"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTOMATING = "automating"
    PAUSED = "paused"
    ERROR = "error"
    CLOSED = "closed"


@dataclass
class StreamConfig:
    """串流配置"""
    target_xbox: str
    stream_type: str = "home"
    quality: str = "1080p"
    fps: int = 30


class StreamWindow:
    """
    串流窗口 - 管理单个账号的独立窗口
    
    状态机：
    INITIALIZING → READY → CONNECTING → CONNECTED → AUTOMATING
                                                ↘
                                                 ERROR → CLOSED
    """

    def __init__(
        self,
        instance_id: str,
        config: 'AccountConfig',
        on_state_change: Callable[[str, WindowState], None]
    ):
        self.instance_id = instance_id
        self.config = config
        self.on_state_change = on_state_change

        self.state = WindowState.INITIALIZING
        self.stream_config: Optional[StreamConfig] = None
        self.session_id: Optional[str] = None

        self.xplayer: Optional[Any] = None
        self.frame_capture: Optional['VideoFrameCapture'] = None
        self.template_matcher: Optional['TemplateMatcher'] = None
        self.input_controller: Optional['InputController'] = None

        self.browser_window: Optional[Any] = None
        self.automation_task: Optional[asyncio.Task] = None

        self.restart_count = 0
        self.max_restart = 3
        self.is_paused = False
        self.pause_event = asyncio.Event()
        self.error_message: Optional[str] = None

    def is_running(self) -> bool:
        """检查窗口是否正在运行"""
        return self.state in [
            WindowState.CONNECTED,
            WindowState.AUTOMATING,
            WindowState.PAUSED
        ]

    async def init(self):
        """初始化组件"""
        self._set_state(WindowState.INITIALIZING)

        try:
            self.browser_window = await self._create_browser_window()
            
            await self._wait_for_page_ready()

            self.xplayer = await self._get_xplayer()

            video_element = await self._get_video_element()
            self.frame_capture = VideoFrameCapture(video_element)

            from .template_matcher import TemplateMatcher
            self.template_matcher = TemplateMatcher()
            await self.template_matcher.load_templates()

            self.input_controller = InputController(self.xplayer, self.frame_capture)

            self._set_state(WindowState.READY)
            logger.info(f"[{self.instance_id}] StreamWindow 初始化完成")

        except Exception as e:
            logger.error(f"[{self.instance_id}] 初始化失败: {e}")
            self._set_state(WindowState.ERROR)
            self.error_message = str(e)
            raise

    async def _create_browser_window(self) -> Any:
        """创建独立的 Electron 窗口"""
        from electron import BrowserWindow

        window = BrowserWindow({
            'width': 1280,
            'height': 720,
            'title': f"串流-{self.config.name}",
            'movable': True,
            'minimizable': True,
            'maximizable': False,
            'closable': True,
            'webPreferences': {
                'nodeIntegration': False,
                'contextIsolation': True,
                'preload': self._get_preload_path()
            }
        })

        window.loadURL(
            f"http://localhost:9999/stream.html?instance={self.instance_id}"
        )

        return window

    def _get_preload_path(self) -> str:
        """获取 preload 脚本路径"""
        import os
        return os.path.join(
            os.path.dirname(__file__),
            "..",
            "renderer",
            "preload.js"
        )

    async def _wait_for_page_ready(self, timeout: float = 30):
        """等待页面加载完成"""
        start = time.time()
        while time.time() - start < timeout:
            if await self._is_page_ready():
                return
            await asyncio.sleep(0.5)
        raise TimeoutError("页面加载超时")

    async def _is_page_ready(self) -> bool:
        """检查页面是否就绪"""
        try:
            result = await self.browser_window.evaluate(
                "window.streamClient && window.streamClient.isReady()"
            )
            return result is True
        except Exception:
            return False

    async def _get_xplayer(self) -> Any:
        """获取 xStreamingPlayer 实例"""
        return await self.browser_window.evaluate(
            "window.xStreamingPlayer"
        )

    async def _get_video_element(self) -> Any:
        """获取视频元素"""
        return await self.browser_window.evaluate(
            "document.querySelector('video')"
        )

    async def start_streaming(self):
        """启动串流"""
        self._set_state(WindowState.CONNECTING)

        try:
            session_id = await self._start_stream(
                target=self.config.server_id,
                stream_type="home"
            )

            self.session_id = session_id
            self._set_state(WindowState.CONNECTED)
            logger.info(f"[{self.instance_id}] 串流已连接: {session_id}")

        except Exception as e:
            logger.error(f"[{self.instance_id}] 启动串流失败: {e}")
            self._set_state(WindowState.ERROR)
            self.error_message = str(e)
            raise

    async def _start_stream(self, target: str, stream_type: str) -> str:
        """执行串流启动"""
        result = await self.browser_window.evaluate(
            f"window.streamClient.startStream('{target}', '{stream_type}')"
        )
        return result["sessionId"]

    async def run_automation(self):
        """执行自动化循环"""
        self._set_state(WindowState.AUTOMATING)

        self.automation_task = asyncio.current_task()

        while self.state == WindowState.AUTOMATING:
            try:
                if self.is_paused:
                    await self.pause_event.wait()
                    continue

                frame = self.frame_capture.capture_frame()

                await self._process_automation_cycle(frame)

            except Exception as e:
                logger.error(f"[{self.instance_id}] 自动化异常: {e}")
                await self._handle_automation_error(e)

            await asyncio.sleep(0.1)

    async def _process_automation_cycle(self, frame):
        """处理自动化周期"""
        match_result = self.template_matcher.match(frame, 'login_button')

        if match_result and match_result.found:
            await self._handle_login_button(match_result)
            return

        await self._check_and_handle_states(frame)

    async def _handle_login_button(self, match):
        """处理登录按钮点击"""
        self.input_controller.click_at_normalized(match.x, match.y)
        logger.info(f"[{self.instance_id}] 点击登录按钮")

    async def _check_and_handle_states(self, frame):
        """检查并处理其他状态"""
        pass

    async def _handle_automation_error(self, error: Exception):
        """处理自动化错误"""
        if self.restart_count < self.max_restart:
            self.restart_count += 1
            logger.warning(
                f"[{self.instance_id}] 自动恢复中 "
                f"({self.restart_count}/{self.max_restart})"
            )
            await self._recover_from_error()
        else:
            logger.error(f"[{self.instance_id}] 重试次数超限，标记为失败")
            self._set_state(WindowState.ERROR)

    async def _recover_from_error(self):
        """从错误中恢复"""
        await asyncio.sleep(3)
        try:
            await self.close()
            await self.init()
            await self.start_streaming()
        except Exception as e:
            logger.error(f"[{self.instance_id}] 恢复失败: {e}")

    async def pause(self, pause_type: str = "idle"):
        """暂停自动化"""
        if self.is_paused:
            return

        logger.info(f"[{self.instance_id}] 暂停自动化: {pause_type}")
        self.is_paused = True
        self.pause_event.set()
        self._set_state(WindowState.PAUSED)

    async def resume(self):
        """恢复自动化"""
        if not self.is_paused:
            return

        logger.info(f"[{self.instance_id}] 恢复自动化")
        self.is_paused = False
        self.pause_event.clear()
        self._set_state(WindowState.AUTOMATING)

    async def close(self):
        """关闭窗口"""
        logger.info(f"[{self.instance_id}] 关闭窗口")

        if self.automation_task:
            self.automation_task.cancel()

        try:
            if self.browser_window:
                await self.browser_window.close()
        except Exception as e:
            logger.warning(f"[{self.instance_id}] 关闭窗口异常: {e}")

        self._set_state(WindowState.CLOSED)

    def _set_state(self, new_state: WindowState):
        """设置状态并通知"""
        old_state = self.state
        self.state = new_state

        if old_state != new_state:
            logger.info(
                f"[{self.instance_id}] 状态变更: "
                f"{old_state.value} → {new_state.value}"
            )

            if self.on_state_change:
                self.on_state_change(self.instance_id, new_state)
```

#### 窗口状态机

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       StreamWindow 状态机                                │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│    ┌──────────────┐                                                      │
│    │ INITIALIZING │◄─────────────────────────────────┐                   │
│    └──────┬───────┘                                   │                   │
│           │ 初始化完成                                 │                   │
│           ▼                                            │                   │
│    ┌──────────────┐                                   │                   │
│    │    READY     │──────── 启动串流 ───────────────►│                   │
│    └──────────────┘                                   │                   │
│           │                                            │                   │
│           ▼                                            │                   │
│    ┌──────────────┐                                   │                   │
│    │  CONNECTING  │──────── 连接成功 ─────────────────►│                   │
│    └──────────────┘                                   │                   │
│           │                                            │                   │
│           ▼                                            │                   │
│    ┌──────────────┐                                   │                   │
│    │   CONNECTED  │──────── 开始自动化 ──────────────►│                   │
│    └──────────────┘                                   │                   │
│           │                                            │                   │
│           ▼                                            │                   │
│    ┌──────────────┐        ┌─────────┐               │                   │
│    │  AUTOMATING  │───────►│ PAUSED  │               │                   │
│    └──────┬───────┘ 暂停   └────┬────┘               │                   │
│           │                     │                    │                   │
│           │    ┌─────────────────┘                    │                   │
│           │    │ 恢复                                    │                   │
│           │    ▼                                        │                   │
│           │  (返回 AUTOMATING)                          │                   │
│           │                                             │                   │
│           ▼                                             │                   │
│    ┌──────────────┐                                   │                   │
│    │    ERROR     │───────── 重试成功 ─────────────────┘                   │
│    └──────┬───────┘       (返回 AUTOMATING)                             │
│           │                                                           │
│           │  重试次数超限                                               │
│           ▼                                                           │
│    ┌──────────────┐                                                  │
│    │    CLOSED    │                                                  │
│    └──────────────┘                                                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 与 xStreamingPlayer 交互

```python
class StreamWindow:
    async def _get_xplayer(self) -> Any:
        """获取 xStreamingPlayer 实例"""
        return await self.browser_window.evaluate(
            "window.xStreamingPlayer"
        )

    async def press_xbox_button(self, button: str):
        """按下 Xbox 按钮"""
        processor = self.xplayer.getChannelProcessor('input')
        processor.pressButtonStart(button)
        await asyncio.sleep(0.1)
        processor.pressButtonEnd(button)

    async def navigate_to(self, direction: str, times: int = 1):
        """导航（上下左右）"""
        processor = self.xplayer.getChannelProcessor('input')
        for _ in range(times):
            processor.pressButtonStart(direction)
            await asyncio.sleep(0.1)
            processor.pressButtonEnd(direction)
            await asyncio.sleep(0.3)
```

### 7.3 VideoFrameCapture 视频帧捕获

VideoFrameCapture 负责从视频流捕获帧，并处理坐标变换以支持归一化坐标。

#### 类设计

```python
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass


@dataclass
class CoordinateTransform:
    """坐标变换参数"""
    offset_x: float
    offset_y: float
    scale: float
    video_width: int
    video_height: int
    display_width: int
    display_height: int


class VideoFrameCapture:
    """
    视频帧捕获器
    
    职责：
    - 从视频元素捕获当前帧
    - 返回 BGR 格式的 numpy 数组
    - 计算坐标变换矩阵（处理 letterbox/pillarbox 黑边）
    """

    def __init__(self, video_element: Any):
        self.video = video_element
        self.canvas: Optional[Any] = None
        self.ctx: Optional[Any] = None
        self._cached_transform: Optional[CoordinateTransform] = None

    def _ensure_canvas(self):
        """确保 canvas 已创建"""
        if self.canvas is None:
            self.canvas = np.zeros(
                (self.video.videoHeight, self.video.videoWidth, 3),
                dtype=np.uint8
            )

    def capture_frame(self) -> np.ndarray:
        """
        捕获当前视频帧
        
        Returns:
            BGR 格式的 numpy 数组 (height, width, 3)
        """
        self._ensure_canvas()

        self.ctx.drawImage(
            self.video,
            0, 0,
            self.video.videoWidth,
            self.video.videoHeight
        )

        pixels = np.array(
            self.ctx.getImageData(
                0, 0,
                self.video.videoWidth,
                self.video.videoHeight
            ).data
        )

        frame = pixels.reshape(
            (self.video.videoHeight, self.video.videoWidth, 4)
        )
        frame = frame[:, :, :3][:, :, ::-1]

        return frame

    def get_coordinate_transform(self) -> CoordinateTransform:
        """
        获取坐标变换矩阵
        
        用于处理 letterbox/pillarbox 黑边
        当视频宽高比与显示区域不同时，会产生黑边
        
        Returns:
            CoordinateTransform 对象，包含偏移和缩放参数
        """
        video_w = self.video.videoWidth
        video_h = self.video.videoHeight
        client_w = self.video.clientWidth
        client_h = self.video.clientHeight

        video_aspect = video_w / video_h
        client_aspect = client_w / client_h

        if video_aspect > client_aspect:
            scale = client_w / video_w
            offset_y = (client_h - video_h * scale) / 2
            offset_x = 0
        else:
            scale = client_h / video_h
            offset_x = (client_w - video_w * scale) / 2
            offset_y = 0

        return CoordinateTransform(
            offset_x=offset_x,
            offset_y=offset_y,
            scale=scale,
            video_width=video_w,
            video_height=video_h,
            display_width=client_w,
            display_height=client_h
        )

    def normalized_to_display(
        self,
        norm_x: float,
        norm_y: float
    ) -> Tuple[int, int]:
        """
        将归一化坐标转换为显示坐标
        
        Args:
            norm_x: 归一化 X 坐标 (0-1)
            norm_y: 归一化 Y 坐标 (0-1)
            
        Returns:
            (display_x, display_y) 显示坐标（像素）
        """
        transform = self.get_coordinate_transform()

        video_x = norm_x * transform.video_width
        video_y = norm_y * transform.video_height

        display_x = int(video_x * transform.scale + transform.offset_x)
        display_y = int(video_y * transform.scale + transform.offset_y)

        return display_x, display_y

    def display_to_normalized(
        self,
        display_x: float,
        display_y: float
    ) -> Tuple[float, float]:
        """
        将显示坐标转换为归一化坐标
        
        Args:
            display_x: 显示 X 坐标（像素）
            display_y: 显示 Y 坐标（像素）
            
        Returns:
            (norm_x, norm_y) 归一化坐标 (0-1)
        """
        transform = self.get_coordinate_transform()

        video_x = (display_x - transform.offset_x) / transform.scale
        video_y = (display_y - transform.offset_y) / transform.scale

        norm_x = video_x / transform.video_width
        norm_y = video_y / transform.video_height

        return norm_x, norm_y
```

#### 坐标变换处理 letterbox/pillarbox 黑边

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      Letterbox (上下黑边)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────┐                                    │
│  │ ▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← offset_y > 0                       │
│  │▓┌─────────────────────────────┓│                                    │
│  │▓│                             │▓│                                    │
│  │▓│        视频画面              │▓│  video_aspect < client_aspect     │
│  │▓│                             │▓│  按高度填充，产生上下黑边            │
│  │▓│                             │▓│                                    │
│  │▓└─────────────────────────────┘▓│                                    │
│  │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓ │  ← offset_y                           │
│  └─────────────────────────────────┘                                    │
│                                                                          │
│  scale = client_height / video_height                                   │
│  offset_x = 0                                                           │
│  offset_y = (client_height - video_height * scale) / 2                  │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      Pillarbox (左右黑边)                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌───┬───────────────────────────────┬───┐                             │
│  │   │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│   │                             │
│  │   │▓                             ▓│   │                             │
│  │   │▓                             ▓│   │                             │
│  │   │▓        视频画面              ▓│   │ ← offset_x                 │
│  │   │▓                             ▓│   │                             │
│  │   │▓                             ▓│   │                             │
│  │   │▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓│   │                             │
│  └───┴───────────────────────────────┴───┘                             │
│                                                                          │
│  video_aspect > client_aspect                                           │
│  按宽度填充，产生左右黑边                                                 │
│                                                                          │
│  scale = client_width / video_width                                     │
│  offset_x = (client_width - video_width * scale) / 2                    │
│  offset_y = 0                                                           │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.4 InputController 输入控制器

InputController 负责将归一化坐标的点击操作转换为实际的 Xbox 手柄输入。

#### 类设计

```python
import time
from typing import Optional, Tuple


class InputController:
    """
    输入控制器
    
    职责：
    - 使用归一化坐标执行点击操作
    - 自动处理黑边偏移
    - 与 xStreamingPlayer ChannelProcessor 交互
    """

    def __init__(self, xplayer: Any, frame_capture: 'VideoFrameCapture'):
        self.xplayer = xplayer
        self.frame_capture = frame_capture
        self.channel_processor = None

    def _ensure_channel_processor(self):
        """确保 ChannelProcessor 已初始化"""
        if self.channel_processor is None:
            self.channel_processor = self.xplayer.getChannelProcessor('input')

    def click_at_normalized(self, norm_x: float, norm_y: float):
        """
        使用归一化坐标点击 (0-1)
        
        自动处理黑边偏移，将归一化坐标转换为显示坐标后执行点击
        
        Args:
            norm_x: 归一化 X 坐标 (0-1)
            norm_y: 归一化 Y 坐标 (0-1)
        """
        self._ensure_channel_processor()

        display_x, display_y = self.frame_capture.normalized_to_display(
            norm_x, norm_y
        )

        self._move_cursor(display_x, display_y)

        self._press_button('A')

    def _move_cursor(self, x: float, y: float):
        """
        移动光标到指定位置
        
        使用 Xbox UI 的导航机制移动光标到目标位置
        """
        self._ensure_channel_processor()

        current_pos = self._get_current_cursor_position()

        dx = int(x - current_pos[0])
        dy = int(y - current_pos[1])

        steps_x = abs(dx) // 10
        steps_y = abs(dy) // 10

        if dx > 0:
            for _ in range(steps_x):
                self.channel_processor.pressButtonStart('RIGHT')
                time.sleep(0.05)
                self.channel_processor.pressButtonEnd('RIGHT')
        else:
            for _ in range(steps_x):
                self.channel_processor.pressButtonStart('LEFT')
                time.sleep(0.05)
                self.channel_processor.pressButtonEnd('LEFT')

        if dy > 0:
            for _ in range(steps_y):
                self.channel_processor.pressButtonStart('DOWN')
                time.sleep(0.05)
                self.channel_processor.pressButtonEnd('DOWN')
        else:
            for _ in range(steps_y):
                self.channel_processor.pressButtonStart('UP')
                time.sleep(0.05)
                self.channel_processor.pressButtonEnd('UP')

    def _get_current_cursor_position(self) -> Tuple[int, int]:
        """获取当前光标位置"""
        try:
            result = self.channel_processor.getCursorPosition()
            return (result.get('x', 640), result.get('y', 360))
        except Exception:
            return (640, 360)

    def _press_button(self, button: str):
        """按下按钮"""
        self._ensure_channel_processor()

        self.channel_processor.pressButtonStart(button)
        time.sleep(0.1)
        self.channel_processor.pressButtonEnd(button)

    def press_button(self, button: str):
        """直接按下按钮（不等待）"""
        self._ensure_channel_processor()
        self.channel_processor.pressButtonStart(button)
        time.sleep(0.1)
        self.channel_processor.pressButtonEnd(button)

    def hold_button(self, button: str, duration: float):
        """按住按钮指定时间"""
        self._ensure_channel_processor()
        self.channel_processor.pressButtonStart(button)
        time.sleep(duration)
        self.channel_processor.pressButtonEnd(button)

    def input_text(self, text: str):
        """输入文本（通过剪贴板）"""
        self._ensure_channel_processor()

        self.xplayer.setClipboard(text)

        time.sleep(0.2)

        self.channel_processor.pressShortcut('ctrl', 'v')

        time.sleep(0.2)
```

### 7.5 窗口拖拽与最小化

Electron BrowserWindow 配置支持窗口拖拽和最小化操作。

#### Electron BrowserWindow 配置

```javascript
// 在 Electron 主进程中创建窗口
const { BrowserWindow } = require('electron');

function createStreamWindow(instanceId, accountName) {
    const window = new BrowserWindow({
        width: 1280,
        height: 720,
        title: `串流-${accountName}`,

        // 窗口拖拽支持
        movable: true,

        // 最小化支持
        minimizable: true,

        // 不支持最大化
        maximizable: false,

        // 关闭支持
        closable: true,

        // 窗口可调整大小
        resizable: true,

        // 窗口可位于顶层
        alwaysOnTop: false,

        // WebPreferences
        webPreferences: {
            nodeIntegration: false,
            contextIsolation: true,
            preload: path.join(__dirname, 'preload.js')
        }
    });

    // 加载串流页面
    window.loadURL(
        `http://localhost:9999/stream.html?instance=${instanceId}`
    );

    // 监听窗口事件
    window.on('minimize', () => {
        console.log(`窗口 ${instanceId} 已最小化`);
        notifyBackend('window_minimized', { instanceId });
    });

    window.on('close', () => {
        console.log(`窗口 ${instanceId} 正在关闭`);
        notifyBackend('window_closing', { instanceId });
    });

    return window;
}
```

#### 窗口控制方法

```python
class StreamWindow:
    async def minimize(self):
        """最小化窗口"""
        if self.browser_window:
            await self.browser_window.minimize()

    async def restore(self):
        """恢复窗口"""
        if self.browser_window:
            await self.browser_window.restore()

    async def set_always_on_top(self, flag: bool):
        """设置窗口置顶"""
        if self.browser_window:
            await self.browser_window.setAlwaysOnTop(flag)

    async def close(self):
        """关闭窗口"""
        if self.browser_window:
            await self.browser_window.close()
```

### 7.6 归一化坐标系统

归一化坐标系统是自动化操作的核心，确保坐标不受窗口位置和大小影响。

#### 原理说明

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        归一化坐标原理                                    │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  原始视频帧 (1920x1080):                                                  │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                                                                     │    │
│  │                      (0.5, 0.5) ←──── 视频中心                      │    │
│  │                            ●                                      │    │
│  │                                                                     │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  显示窗口 (1280x720) 带黑边:                                              │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│    │
│  │░┌─────────────────────────────────────────────────────────────┐░│    │
│  │░│                                                             │░│    │
│  │░│                         视频画面                             │░│    │
│  │░│                                                             │░│    │
│  │░│                      ● ← 中心点                              │░│    │
│  │░│                       (640, 360) 显示坐标                    │░│    │
│  │░│                                                             │░│    │
│  │░└─────────────────────────────────────────────────────────────┘░│    │
│  │░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░│    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  无论窗口如何移动/缩放，中心点的归一化坐标始终是 (0.5, 0.5)                 │
│  这使得模板匹配返回的坐标可以直接使用，不受窗口状态影响                       │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 坐标转换公式

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        坐标转换公式                                       │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  【归一化坐标 → 显示坐标】                                                │
│                                                                          │
│  display_x = norm_x * video_width * scale + offset_x                    │
│  display_y = norm_y * video_height * scale + offset_y                    │
│                                                                          │
│  其中:                                                                   │
│    video_width = 原始视频宽度                                             │
│    video_height = 原始视频高度                                            │
│    scale = min(client_width / video_width, client_height / video_height) │
│    offset_x = (client_width - video_width * scale) / 2  (或 0)          │
│    offset_y = (client_height - video_height * scale) / 2  (或 0)        │
│                                                                          │
│  【显示坐标 → 归一化坐标】                                                │
│                                                                          │
│  norm_x = (display_x - offset_x) / (video_width * scale)                │
│  norm_y = (display_y - offset_y) / (video_height * scale)               │
│                                                                          │
│  【示例计算】                                                            │
│                                                                          │
│  假设:                                                                   │
│    视频分辨率: 1920x1080                                                  │
│    显示窗口: 1280x720                                                     │
│    目标点: 归一化坐标 (0.5, 0.5)                                          │
│                                                                          │
│  1. 计算 scale:                                                          │
│     video_aspect = 1920/1080 = 1.778                                     │
│     client_aspect = 1280/720 = 1.778                                     │
│     video_aspect == client_aspect → 刚好填充，无黑边                       │
│     scale = 1280/1920 = 0.667                                            │
│                                                                          │
│  2. 计算显示坐标:                                                         │
│     display_x = 0.5 * 1920 * 0.667 + 0 = 640                            │
│     display_y = 0.5 * 1080 * 0.667 + 0 = 360                            │
│                                                                          │
│  【Python 实现】                                                          │
│                                                                          │
│  class VideoFrameCapture:                                                │
│      def normalized_to_display(self, norm_x, norm_y):                    │
│          transform = self.get_coordinate_transform()                    │
│          display_x = norm_x * transform.video_width * transform.scale  │
│                      + transform.offset_x                                │
│          display_y = norm_y * transform.video_height * transform.scale │
│                      + transform.offset_y                                │
│          return int(display_x), int(display_y)                          │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

### 7.7 异常恢复机制

异常恢复机制确保自动化任务在遇到错误时能够自动恢复，保证持续运行。

#### 心跳超时检测

```python
class CentralManager:
    """中央管理器 - 包含心跳超时检测"""

    def __init__(self, backend_url: str, agent_id: str):
        self.backend_url = backend_url
        self.agent_id = agent_id
        self.windows: Dict[str, StreamWindow] = {}
        self.last_heartbeat: Dict[str, float] = {}
        self.heartbeat_timeout = 60

    async def check_instance_heartbeat(self, instance_id: str) -> bool:
        """
        检查实例心跳是否超时
        
        Args:
            instance_id: 实例 ID
            
        Returns:
            True 如果心跳正常，False 如果超时
        """
        if instance_id not in self.last_heartbeat:
            return True

        elapsed = time.time() - self.last_heartbeat[instance_id]

        if elapsed > self.heartbeat_timeout:
            logger.warning(
                f"实例 {instance_id} 心跳超时 "
                f"({elapsed:.1f}秒 > {self.heartbeat_timeout}秒)"
            )
            await self._trigger_instance_recovery(instance_id)
            return False

        return True

    async def _trigger_instance_recovery(self, instance_id: str):
        """触发实例恢复流程"""
        window = self.windows.get(instance_id)
        if not window:
            return

        logger.info(f"触发实例 {instance_id} 自动恢复")

        window.restart_count += 1

        if window.restart_count > window.max_restart:
            logger.error(f"实例 {instance_id} 重启次数超限")
            await self._mark_instance_failed(instance_id)
            return

        await window._recover_from_error()

    async def _mark_instance_failed(self, instance_id: str):
        """标记实例为失败状态"""
        window = self.windows.get(instance_id)
        if window:
            window.state = WindowState.ERROR
            window.error_message = "重启次数超限"

        await self._report_status(
            instance_id,
            "failed",
            {"reason": "restart_count_exceeded"}
        )


class StreamWindow:
    """串流窗口 - 包含心跳管理"""

    def __init__(self, instance_id: str, config: AccountConfig,
                 on_state_change: Callable):
        self.instance_id = instance_id
        self.config = config
        self.on_state_change = on_state_change

        self.last_heartbeat = time.time()
        self.heartbeat_interval = 30

    async def send_heartbeat(self):
        """发送心跳"""
        self.last_heartbeat = time.time()

    def is_heartbeat_expired(self, timeout: float = 60) -> bool:
        """检查心跳是否过期"""
        return time.time() - self.last_heartbeat > timeout
```

#### 自动重启窗口实例

```python
class StreamWindow:
    """串流窗口 - 自动重启逻辑"""

    def __init__(self, instance_id: str, config: AccountConfig,
                 on_state_change: Callable):
        self.instance_id = instance_id
        self.config = config
        self.on_state_change = on_state_change

        self.restart_count = 0
        self.max_restart = 3
        self.recovery_delay = 5

    async def _recover_from_error(self):
        """从错误中自动恢复"""
        logger.info(
            f"[{self.instance_id}] 开始自动恢复 "
            f"({self.restart_count}/{self.max_restart})"
        )

        await asyncio.sleep(self.recovery_delay)

        try:
            await self.close()
        except Exception as e:
            logger.warning(f"关闭窗口失败: {e}")

        await asyncio.sleep(2)

        try:
            await self.init()
            await self.start_streaming()

            self.restart_count = 0
            logger.info(f"[{self.instance_id}] 自动恢复成功")

        except Exception as e:
            logger.error(f"[{self.instance_id}] 自动恢复失败: {e}")

            if self.restart_count < self.max_restart:
                await self._recover_from_error()
            else:
                await self._mark_as_failed(str(e))

    async def _mark_as_failed(self, reason: str):
        """标记为失败状态"""
        self.state = WindowState.ERROR
        self.error_message = reason

        logger.error(
            f"[{self.instance_id}] 自动化任务失败: {reason} "
            f"({self.restart_count}/{self.max_restart})"
        )

        if self.on_state_change:
            self.on_state_change(self.instance_id, WindowState.ERROR)
```

#### 崩溃恢复流程图

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         崩溃恢复流程                                      │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────┐                               │
│  │         检测到异常/崩溃              │                               │
│  └──────────────┬──────────────────────┘                               │
│                 │                                                     │
│                 ▼                                                     │
│  ┌─────────────────────────────────────┐                               │
│  │      restart_count++               │                               │
│  └──────────────┬──────────────────────┘                               │
│                 │                                                     │
│                 ▼                                                     │
│         ┌───────┴───────┐                                             │
│         │restart_count  │                                             │
│         │  > max_restart│                                             │
│         └───────┬───────┘                                             │
│          Yes    │    No                                               │
│         ┌───────┴───────┐                                             │
│         │               │                                             │
│         ▼               ▼                                             │
│  ┌─────────────┐  ┌─────────────────────┐                             │
│  │ 标记失败    │  │  执行自动恢复        │                             │
│  │ 上报后端    │  │  1. 关闭原窗口       │                             │
│  │ 记录日志    │  │  2. 等待 2 秒       │                             │
│  └──────┬──────┘  │  3. 重新初始化      │                             │
│         │         │  4. 重启串流        │                             │
│         │         │  5. 恢复自动化      │                             │
│         │         └──────────┬──────────┘                             │
│         │                    │                                        │
│         │                    ▼                                        │
│         │         ┌─────────────────────┐                             │
│         │         │     恢复成功？      │                             │
│         │         └──────────┬──────────┘                             │
│         │          Yes       │    No                                  │
│         │         ┌──────────┴──────┐                                │
│         │         │                 │                                │
│         │         ▼                 ▼                                │
│         │  ┌───────────┐    ┌───────────────┐                        │
│         │  │ 重置计数  │    │ 递归恢复      │                        │
│         │  │ 继续运行  │    │ (回到检测)    │                        │
│         │  └───────────┘    └───────────────┘                        │
│         │                                                         │
│         └─────────────────────────────────────────────────────────►│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

#### 异常类型与恢复策略

| 异常类型    | 检测方法                        | 恢复策略       |
| ------- | --------------------------- | ---------- |
| 窗口崩溃    | BrowserWindow isDestroyed() | 重新创建窗口     |
| Xbox 断开 | WebRTC 连接断开                 | 重连串流会话     |
| 账号掉线    | 模板匹配检测登出界面                  | 重新登录       |
| 游戏崩溃    | 检测游戏退出标志                    | 重启游戏或返回主界面 |
| 网络波动    | 心跳超时                        | 等待恢复后重连    |
| 模板匹配失败  | 连续多次匹配不上                    | 重试 + 导航尝试  |

***

## 五、微软登录与 Xbox 串流机制（融合升级版）

> ⚠️ **基于 XStreamingDesktop 开源项目源码分析更新**
>
> 本章节整合了 XStreaming 源码分析，修正了原有的登录串流设计，使其更加准确和可落地。

### 5.1 微软登录的真正目的

**微软登录的核心是获取 UserToken**，UserToken 是整个 Xbox 生态的身份基础。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    UserToken 的生命周期与作用                               │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│                          微软登录 (Device Code Flow)                        │
│                                 │                                           │
│                                 ▼                                           │
│                    UserToken (access_token + refresh_token)                  │
│                           │                                               │
│                           ├──► 刷新 ──► 新 UserToken（自动，无用户交互）   │
│                           │                                               │
│                           └──► 转换 ──► 各种专用 Token                      │
│                                      │                                     │
│                                      ├──► XstsToken ──► WebToken          │
│                                      │              │                      │
│                                      │              ├──► 发现 Xbox 主机    │
│                                      │              ├──► 获取用户信息       │
│                                      │              └──► 发送控制命令       │
│                                      │                                     │
│                                      └──► XstsToken ──► StreamingToken     │
│                                                     │                      │
│                                                     └──► 串流连接          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.2 Token 类型与用途

| Token 类型           | 用途              | 获取方式                     | 有效期                 |
| ------------------ | --------------- | ------------------------ | ------------------- |
| **UserToken**      | 身份基础凭证          | Device Code Flow（用户交互一次） | refresh\_token 长期有效 |
| **refresh\_token** | 自动刷新获取新Token    | 登录成功后获得                  | 长期（数月\~数年）          |
| **XstsToken**      | Xbox 服务通用Token  | 调用 XSTS API              | 约24小时               |
| **WebToken**       | Xbox Web API 调用 | XSTS 授权后获得               | 约24小时               |
| **StreamingToken** | 串流专用凭证          | XSTS 授权后获得               | 约24小时               |
| **DeviceToken**    | 设备绑定凭证          | 调用 Device Auth API       | 长期（应用密钥签名）          |

### 5.3 Device Code Flow 登录流程

XStreaming 使用 **Device Code Flow** 进行登录，这是一种用户友好但仍需一次用户交互的方式：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Device Code Flow 登录流程                             │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  【步骤1: 启动登录】                                                        │
│                                                                             │
│  Agent 发起登录请求 ──► 微软返回 device_code + user_code                   │
│                                                                             │
│  【步骤2: 用户授权】                                                        │
│                                                                             │
│  ┌───────────────────────────────────────────────┐                        │
│  │  请在 手机/其他设备 上访问:                    │                        │
│  │                                               │                        │
│  │         microsoft.com/devicelogin             │                        │
│  │                                               │                        │
│  │  并输入代码: XXXXXXXX                         │                        │
│  └───────────────────────────────────────────────┘                        │
│                                                                             │
│  【步骤3: 轮询等待】                                                        │
│                                                                             │
│  Agent 轮询检查用户是否完成授权                                             │
│  用户确认后 ──► 获取 UserToken (refresh_token)                             │
│                                                                             │
│  【步骤4: Token 存储】                                                      │
│                                                                             │
│  UserToken 存储到数据库，后续自动刷新使用                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.4 Xbox 主机识别机制（重要修正）

**关键发现**：Xbox 列表的获取**与用户账号有关**，而不是局域网广播发现。

#### 5.4.1 getConsolesList() 的真实行为

```typescript
// 调用 Xbox SmartGlass API 获取主机列表
this._application._webApi
    .getProvider('smartglass')
    .getConsolesList()  // ⭐ 不带任何参数，返回「与当前账号绑定的 Xbox」
```

**返回的列表只包含**：该账号**曾经在该 Xbox 上登录过**的主机。

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Xbox 列表与账号的关系                                      │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  【getConsolesList() 返回的列表】                                          │
│                                                                             │
│  账号 A 登录过的 Xbox：                                                     │
│  ├── Xbox-001 (客厅) ◄── ✅ 在列表中                                       │
│  ├── Xbox-002 (卧室) ◄── ✅ 在列表中                                       │
│  └── Xbox-003 (书房) ◄── ✅ 在列表中                                       │
│                                                                             │
│  账号 A 没登录过的 Xbox：                                                   │
│  └── Xbox-999 (邻居的 Xbox) ◄── ❌ 不在列表中                              │
│                                                                             │
│  【结论】                                                                   │
│                                                                             │
│  getConsolesList() 返回的是「我曾经登录过的 Xbox」，而非「局域网内所有 Xbox」│
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.4.2 一个账号 + 多台 Xbox

**一个微软账号可以在多个 Xbox 主机上登录**。这是 Xbox 的原生设计：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    一个账号绑定多台 Xbox                                      │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│                    账号 A (user@example.com)                                │
│                           │                                                │
│           ┌───────────────┼───────────────┐                                │
│           ▼               ▼               ▼                                │
│      ┌─────────┐     ┌─────────┐     ┌─────────┐                         │
│      │ Xbox-1  │     │ Xbox-2  │     │ Xbox-3  │                         │
│      │  客厅    │     │  卧室    │     │  书房    │                         │
│      └────┬────┘     └────┬────┘     └────┬────┘                         │
│           │               │               │                                │
│           └───────────────┴───────────────┘                                │
│                           │                                                │
│                      都在账号的「绑定列表」中                               │
│                                                                             │
│  【getConsolesList() 返回】                                                │
│                                                                             │
│  {                                                                       │
│    consoles: [                                                            │
│      { id: "Xbox-1", name: "客厅 Xbox Series X", powerState: "On" },     │
│      { id: "Xbox-2", name: "卧室 Xbox One", powerState: "Off" },         │
│      { id: "Xbox-3", name: "书房 Xbox Series S", powerState: "On" }      │
│    ]                                                                     │
│  }                                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.5 串流到 Xbox 的完整流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Xbox 串流认证与连接流程                                    │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  【前提条件】                                                               │
│                                                                             │
│  1. ✅ Xbox 主机已开机且在局域网内                                          │
│  2. ✅ 用户曾在该 Xbox 主机上登录过 Microsoft 账号（一次性设置）             │
│  3. ✅ 持有有效的 refresh_token（长期有效，自动刷新）                       │
│  4. ✅ 能成功刷新获取 StreamingToken（gsToken）                              │
│                                                                             │
│  【串流步骤】                                                               │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤1: Token 刷新（自动化，无用户交互）                               │   │
│  │                                                                     │   │
│  │ refresh_token ──► UserToken ──► XstsToken ──► StreamingToken         │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤2: 发现 Xbox（通过 WebToken 调用 SmartGlass API）               │   │
│  │                                                                     │   │
│  │ getConsolesList() ──► 返回账号绑定的 Xbox 列表                      │   │
│  │                            │                                        │   │
│  │                            ├──► Xbox-001 (powerState: On)  ◄── 可用│   │
│  │                            ├──► Xbox-002 (powerState: Off) ◄── 离线│   │
│  │                            └──► Xbox-003 (powerState: On)  ◄── 可用│   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤3: 发起串流请求                                                 │   │
│  │                                                                     │   │
│  │ sendCommand(consoleId, 'Launch', 'STREAM', [...])                   │   │
│  │                                                                     │   │
│  │ Xbox 收到请求后验证：                                               │   │
│  │ • 请求中的 userToken 对应的账号是否在本机登录过？                    │   │
│  │   ├── 是 ──► 允许串流                                             │   │
│  │   └── 否 ──► 拒绝请求                                             │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤4: 建立串流连接                                                 │   │
│  │                                                                     │   │
│  │ 使用 StreamingToken (gsToken) 建立 WebRTC 连接                     │   │
│  │ • 视频流: Xbox ──► PC                                              │   │
│  │ • 控制流: PC ──► Xbox (手柄输入)                                    │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.6 串流账号与 Xbox 的绑定关系设计

基于以上分析，设计以下数据模型：

```python
# 串流账号配置
class StreamingAccountConfig:
    """串流账号配置"""
    streaming_account_id: int           # 串流账号数据库ID
    email: str                          # 微软账号邮箱
    refresh_token: str                 # ⭐ 核心凭证，长期有效
    user_hash: str                     # 用户身份标识 (uhs)
    bound_xbox_ids: List[str]          # ⭐ 该账号绑定的 Xbox ID 列表
    status: str                         # 账号状态

# Xbox 主机配置
class XboxHostConfig:
    """Xbox 主机配置"""
    xbox_id: str                        # Xbox 唯一标识
    name: str                            # Xbox 名称（如：客厅 Xbox）
    ip_address: str                      # Xbox IP 地址
    bound_streaming_account_id: int     # 当前绑定的串流账号
    bound_gamertag: str                 # 在该 Xbox 上登录的 Gamertag
    power_state: str                    # 在线状态
```

### 5.7 自动串流方案设计

#### 5.7.1 串流账号分配算法

```python
class StreamingAccountSelector:
    """
    串流账号选择器
    根据 Xbox 列表自动选择可用的串流账号
    """

    def select_available_xbox(
        self,
        streaming_accounts: List[StreamingAccountConfig],
        xbox_list: List[dict]
    ) -> Optional[Tuple[StreamingAccountConfig, dict]]:
        """
        选择可用的串流账号和 Xbox 组合

        Returns:
            (串流账号, Xbox信息) 或 None
        """

        for account in streaming_accounts:
            # 1. 检查账号是否有效
            if not self._is_account_valid(account):
                continue

            # 2. 获取该账号绑定的 Xbox 列表
            bound_xbox_ids = account.bound_xbox_ids

            # 3. 在 Xbox 列表中筛选
            for xbox in xbox_list:
                # 3.1 检查是否在绑定列表中
                if xbox['id'] not in bound_xbox_ids:
                    continue

                # 3.2 检查 Xbox 是否在线
                if xbox.get('powerState') != 'On':
                    continue

                # 3.3 检查是否已被占用
                if xbox.get('bound_streaming_account_id') is not None:
                    continue

                # ✅ 找到可用的组合
                return (account, xbox)

        return None  # 没有可用的组合

    def _is_account_valid(self, account: StreamingAccountConfig) -> bool:
        """检查账号是否有效"""
        # 1. 检查 refresh_token 是否存在
        if not account.refresh_token:
            return False

        # 2. 检查是否有绑定的 Xbox
        if not account.bound_xbox_ids:
            return False

        # 3. 尝试刷新 token（内部自动处理过期）
        # 如果 refresh_token 过期，会返回失败
        return True
```

#### 5.7.2 Token 自动刷新机制

```python
class TokenRefreshService:
    """
    Token 自动刷新服务
    定期刷新 Token，确保串流账号始终可用
    """

    def __init__(self, streaming_account: StreamingAccountConfig):
        self.account = streaming_account
        self._xal = XalAuthenticator()  # 参考 XStreaming 的认证逻辑

    async def ensure_valid_tokens(self) -> bool:
        """
        确保拥有有效的 Token
        如果需要，自动刷新

        Returns:
            是否成功获取有效 Token
        """
        try:
            # 1. 尝试使用 refresh_token 获取新的 Token
            user_token = await self._xal.refreshUserToken(
                self.account.refresh_token
            )

            # 2. 获取 DeviceToken
            device_token = await self._xal.getDeviceToken()

            # 3. Sisu 授权
            sisu_token = await self._xal.doSisuAuthorization(
                user_token, device_token
            )

            # 4. XSTS 授权
            xsts_token = await self._xal.doXstsAuthorization(
                sisu_token, 'http://xboxlive.com'
            )

            # 5. 获取 WebToken（用于发现 Xbox）
            web_token = await self._xal.getWebToken(xsts_token)

            # 6. 获取 StreamingToken（用于串流）
            streaming_token = await self._xal.getStreamingToken(xsts_token)

            # ✅ 成功，更新存储的 Token
            self._update_stored_tokens(user_token, streaming_token)
            return True

        except TokenRefreshError as e:
            # refresh_token 过期，需要用户重新授权
            logger.error(f"Token 刷新失败，需要重新授权: {e}")
            await self._notify_merchant_reauth()
            return False

    async def _notify_merchant_reauth(self):
        """通知商户需要重新授权"""
        # 发送通知到管理平台
        # 商户扫描二维码重新授权
        pass
```

#### 5.7.3 Xbox 列表获取

```python
class XboxDiscoveryService:
    """
    Xbox 发现服务
    通过 Xbox SmartGlass API 获取账号绑定的 Xbox 列表
    """

    def __init__(self, web_token: WebToken):
        self._web_api = XboxWebApi(web_token)

    async def get_bound_consoles(self) -> List[dict]:
        """
        获取与当前账号绑定的 Xbox 列表

        Returns:
            Xbox 列表，每个包含 id, name, powerState 等
        """
        consoles = await self._web_api
            .getProvider('smartglass')
            .getConsolesList()

        return consoles.result

    def filter_online_consoles(self, consoles: List[dict]) -> List[dict]:
        """筛选出在线的 Xbox"""
        return [
            c for c in consoles
            if c.get('powerState') == 'On'
        ]
```

#### 5.7.4 分布式环境下 Xbox 竞争问题与锁机制

在多 Agent 环境下，多个 Agent 可能同时尝试串流到同一台 Xbox，需要分布式锁机制防止竞争。

**问题场景：**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    分布式 Xbox 竞争问题                                      │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  【多 Agent 环境】                                                         │
│                                                                             │
│     Agent-A (PC-A)                    Agent-B (PC-B)                       │
│         │                                │                                   │
│         │    ┌──────────────────────────┴────────────────────────┐          │
│         │    │                                                      │          │
│         ▼    ▼                                                      ▼          │
│     ┌─────────────┐                    ┌─────────────┐                      │
│     │ refresh_    │                    │ refresh_    │                      │
│     │ token_A     │                    │ token_B     │                      │
│     └──────┬──────┘                    └──────┬──────┘                      │
│            │                                  │                              │
│            ▼                                  ▼                              │
│     getConsolesList() ◄─────────────────► getConsolesList()              │
│            │                                  │                              │
│            │    返回相同的 Xbox 列表          │                              │
│            │    ┌────────────────────────────┘                              │
│            │    │                                                        │
│            ▼    ▼                                                        │
│     ┌─────────────────────────────────────────┐                            │
│     │              Xbox-001                    │                            │
│     │         powerState: On                  │                            │
│     │         bound_streaming: null           │                            │
│     └─────────────────────────────────────────┘                            │
│            ▲                        ▲                                       │
│            │                        │                                       │
│     Agent-A 发起串流          Agent-B 也发起串流                             │
│     ✅ 串流成功                ❌ 串流失败（已被占用）                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**解决方案：数据库分布式锁**

使用数据库的 `SELECT ... FOR UPDATE` 悲观锁机制，确保只有一个 Agent 能成功抢占 Xbox。

```python
class DistributedXboxLock:
    """
    分布式 Xbox 锁
    使用数据库行锁确保同一 Xbox 只能被一个串流账号占用
    """

    def __init__(self, db_pool):
        self.db_pool = db_pool

    async def try_acquire_xbox_lock(
        self,
        xbox_id: str,
        streaming_account_id: int,
        agent_id: int,
        lock_timeout: int = 300
    ) -> bool:
        """
        尝试获取 Xbox 锁

        Args:
            xbox_id: Xbox 主机 ID
            streaming_account_id: 串流账号 ID
            agent_id: Agent ID（用于标识谁持有锁）
            lock_timeout: 锁超时时间（秒）

        Returns:
            True 表示获取成功，False 表示 Xbox 已被其他账号占用
        """
        async with self.db_pool.acquire() as conn:
            async with conn.transaction():
                # 1. 查询 Xbox 当前状态（带行锁）
                row = await conn.fetchrow(
                    """
                    SELECT id, bound_streaming_account_id, status
                    FROM xbox_host
                    WHERE id = $1
                    FOR UPDATE
                    """,
                    xbox_id
                )

                if not row:
                    logger.warning(f"Xbox {xbox_id} 不存在")
                    return False

                # 2. 检查是否已被占用
                if row['bound_streaming_account_id'] is not None:
                    # Xbox 已被其他串流账号占用
                    logger.info(
                        f"Xbox {xbox_id} 已被串流账号 {row['bound_streaming_account_id']} 占用"
                    )
                    return False

                # 3. 尝试占用 Xbox
                await conn.execute(
                    """
                    UPDATE xbox_host
                    SET bound_streaming_account_id = $1,
                        status = 'streaming',
                        locked_by_agent_id = $2,
                        locked_at = NOW(),
                        lock_expires_at = NOW() + INTERVAL '1 second' * $3
                    WHERE id = $4
                    """,
                    streaming_account_id,
                    agent_id,
                    lock_timeout,
                    xbox_id
                )

                logger.info(
                    f"串流账号 {streaming_account_id} 成功占用 Xbox {xbox_id}"
                )
                return True

    async def release_xbox_lock(self, xbox_id: str) -> bool:
        """
        释放 Xbox 锁

        Args:
            xbox_id: Xbox 主机 ID

        Returns:
            是否释放成功
        """
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE xbox_host
                SET bound_streaming_account_id = NULL,
                    status = 'idle',
                    locked_by_agent_id = NULL,
                    locked_at = NULL,
                    lock_expires_at = NULL
                WHERE id = $1
                """,
                xbox_id
            )

            if result == "UPDATE 1":
                logger.info(f"Xbox {xbox_id} 锁已释放")
                return True
            return False

    async def extend_lock(self, xbox_id: str, extend_seconds: int = 300) -> bool:
        """
        延长锁持有时间（续约）

        Args:
            xbox_id: Xbox 主机 ID
            extend_seconds: 延长时间（秒）

        Returns:
            是否续约成功
        """
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE xbox_host
                SET lock_expires_at = NOW() + INTERVAL '1 second' * $1
                WHERE id = $2 AND lock_expires_at > NOW()
                """,
                extend_seconds,
                xbox_id
            )

            return result == "UPDATE 1"

    async def cleanup_expired_locks(self) -> int:
        """
        清理过期的锁（后台定时任务）

        Returns:
            清理的锁数量
        """
        async with self.db_pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE xbox_host
                SET bound_streaming_account_id = NULL,
                    status = 'idle',
                    locked_by_agent_id = NULL,
                    locked_at = NULL,
                    lock_expires_at = NULL
                WHERE lock_expires_at < NOW() AND bound_streaming_account_id IS NOT NULL
                """
            )

            count = result.split()[1] if result else "0"
            logger.info(f"清理了 {count} 个过期的 Xbox 锁")
            return int(count)
```

#### 5.7.5 改进的 Xbox 选择算法（带锁）

```python
class StreamingAccountSelector:
    """
    串流账号选择器（改进版）
    支持商户指定 Xbox + 自动选择 + 分布式锁
    """

    def __init__(
        self,
        db_pool,
        distributed_lock: DistributedXboxLock
    ):
        self.db_pool = db_pool
        self._distributed_lock = distributed_lock

    async def select_and_lock_xbox(
        self,
        streaming_account: StreamingAccountConfig,
        preferred_xbox_id: Optional[str] = None
    ) -> Optional[Tuple[StreamingAccountConfig, dict, str]]:
        """
        选择并锁定 Xbox

        Args:
            streaming_account: 串流账号
            preferred_xbox_id: 商户指定的 Xbox ID（可选）

        Returns:
            (串流账号, Xbox信息, xbox_id) 或 None
        """
        # 1. 如果商户指定了 Xbox，优先尝试
        if preferred_xbox_id:
            success = await self._distributed_lock.try_acquire_xbox_lock(
                xbox_id=preferred_xbox_id,
                streaming_account_id=streaming_account.streaming_account_id,
                agent_id=self.agent_id
            )

            if success:
                xbox_info = await self._get_xbox_info(preferred_xbox_id)
                return (streaming_account, xbox_info, preferred_xbox_id)
            else:
                logger.warning(
                    f"商户指定的 Xbox {preferred_xbox_id} 已被占用"
                )
                # 继续尝试自动选择其他 Xbox

        # 2. 自动选择：遍历绑定的 Xbox，尝试加锁
        bound_xbox_ids = streaming_account.bound_xbox_ids

        for xbox_id in bound_xbox_ids:
            # 跳过商户指定的（已尝试过）
            if xbox_id == preferred_xbox_id:
                continue

            success = await self._distributed_lock.try_acquire_xbox_lock(
                xbox_id=xbox_id,
                streaming_account_id=streaming_account.streaming_account_id,
                agent_id=self.agent_id
            )

            if success:
                xbox_info = await self._get_xbox_info(xbox_id)
                return (streaming_account, xbox_info, xbox_id)

        return None  # 没有可用的 Xbox

    async def _get_xbox_info(self, xbox_id: str) -> dict:
        """获取 Xbox 详细信息"""
        row = await self.db_pool.fetchrow(
            "SELECT * FROM xbox_host WHERE id = $1",
            xbox_id
        )
        return dict(row)
```

**Xbox 主机表需要增加的字段：**

```sql
ALTER TABLE xbox_host ADD COLUMN locked_by_agent_id BIGINT;
ALTER TABLE xbox_host ADD COLUMN locked_at TIMESTAMP;
ALTER TABLE xbox_host ADD COLUMN lock_expires_at TIMESTAMP;
```

### 5.8 完整串流执行流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    Python Agent 串流执行完整流程                               │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  【商户设置阶段】（一次性操作）                                              │
│                                                                             │
│  1. 商户在每台 Xbox 主机上登录 Microsoft 账号 ◄── ⚠️ 必须!                │
│  2. 在管理平台配置串流账号，录入 refresh_token                              │
│  3. 记录账号绑定的 Xbox（从 getConsolesList 获取）                          │
│                                                                             │
│  【日常运营阶段】（完全自动化）                                              │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤1: Token 确保（启动时或定期执行）                                 │   │
│  │                                                                     │   │
│  │ TokenRefreshService.ensure_valid_tokens()                           │   │
│  │     │                                                             │   │
│  │     ├── refresh_token 有效 ──► 直接使用                             │   │
│  │     │                                                             │   │
│  │     └── refresh_token 过期 ──► 通知商户重新授权 ──► 获取新token   │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤2: 发现 Xbox                                                     │   │
│  │                                                                     │   │
│  │ XboxDiscoveryService.get_bound_consoles()                           │   │
│  │     │                                                             │   │
│  │     └── 返回账号绑定的 Xbox 列表                                     │   │
│  │              │                                                      │   │
│  │              ├──► Xbox-001 (powerState: On)  ◄── 可用              │   │
│  │              ├──► Xbox-002 (powerState: Off) ◄── 离线              │   │
│  │              └──► Xbox-003 (powerState: On)  ◄── 可用              │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤3: 选择目标 Xbox                                                │   │
│  │                                                                     │   │
│  │ StreamingAccountSelector.select_available_xbox()                    │   │
│  │     │                                                             │   │
│  │     └── 筛选条件:                                                  │   │
│  │         • Xbox 在账号的绑定列表中                                    │   │
│  │         • Xbox 在线 (powerState: On)                               │   │
│  │         • Xbox 未被其他串流账号占用                                 │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤4: 发起串流                                                     │   │
│  │                                                                     │   │
│  │ StreamController.start_streaming(                                    │   │
│  │     consoleId=xbox_id,                                              │   │
│  │     streaming_token=streaming_token                                 │   │
│  │ )                                                                   │   │
│  │     │                                                             │   │
│  │     └── Xbox 验证 token ──► 账号已登录 ──► 允许串流               │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                        │
│                                    ▼                                        │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 步骤5: 建立串流连接                                                 │   │
│  │                                                                     │   │
│  │ • 使用 gsToken 建立 WebRTC 连接                                     │   │
│  │ • 视频流开始传输                                                    │   │
│  │ • Agent 可以开始自动化操作                                          │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 5.9 关键设计要点总结

| 要点              | 说明                                                   |
| --------------- | ---------------------------------------------------- |
| **微软登录目的**      | 获取 UserToken (含 refresh\_token)，这是所有操作的身份基础          |
| **Xbox 识别方式**   | 通过 Xbox SmartGlass API 返回「账号绑定的 Xbox 列表」，不是局域网广播发现   |
| **一个账号多台 Xbox** | 一个微软账号可以在多台 Xbox 上登录，都在绑定列表中                         |
| **串流前提**        | 账号必须在该 Xbox 上登录过（一次性设置）                              |
| **Token 刷新**    | 使用 refresh\_token 自动刷新，无需用户交互                        |
| **Token 过期处理**  | refresh\_token 过期后需要用户重新授权（通知商户）                     |
| **商户指定 Xbox**   | 可选：商户可在启动自动化时指定 Xbox，优先使用                            |
| **分布式锁机制**      | 使用数据库 `SELECT ... FOR UPDATE` 悲观锁，防止多 Agent 抢同一 Xbox |
| **锁续约**         | 串流期间定期续约锁，防止意外释放                                     |
| **锁超时释放**       | Agent 离线后，后台任务自动清理过期锁                                |

### 5.10 与原有设计的对比

| 项目           | 原设计              | 融合后设计                             |
| ------------ | ---------------- | --------------------------------- |
| **Xbox 发现**  | 局域网 UDP 广播发现     | Xbox SmartGlass API（账号绑定列表）       |
| **Xbox 绑定**  | 串流账号与 Xbox 一对一绑定 | 一个账号可绑定多台 Xbox                    |
| **登录目的**     | 直接获取串流凭证         | 先获取 refresh\_token，再转换为各种专用 Token |
| **Token 刷新** | 未考虑              | refresh\_token 长期有效，自动刷新专用 Token  |
| **Token 过期** | 未考虑              | 通知商户重新授权                          |

### 5.11 自动化失败状态与错误处理

#### 5.11.1 串流账号完整状态机

串流账号在整个生命周期中会经历多种状态，以下是完整的状态机设计：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        串流账号状态机                                         │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  ┌─────────┐                                                               │
│  │  idle   │ ◄─── 初始化                                                  │
│  └────┬────┘                                                               │
│       │ 启动自动化                                                           │
│       ▼                                                                    │
│  ┌─────────┐                                                               │
│  │  ready  │ ◄─── Token刷新成功 + Xbox锁定成功                           │
│  └────┬────┘                                                               │
│       │ 串流连接成功                                                        │
│       ▼                                                                    │
│  ┌─────────┐                                                               │
│  │ running │ ◄─── 自动化执行中                                             │
│  └────┬────┘                                                               │
│       │ 暂停 / 完成任务 / 失败                                              │
│       ▼                                                                    │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐                             │
│  │ paused  │     │stopping │     │  error  │                             │
│  └────┬────┘     └────┬────┘     └────┬────┘                             │
│       │                │                │                                │
│       │ 继续执行        │ 释放锁          │ 错误原因                        │
│       ▼                ▼                ▼                                │
│  ┌─────────┐     ┌─────────┐     ┌─────────┐                             │
│  │ running │     │  idle   │     │ error_  │                             │
│  └─────────┘     └─────────┘     │ reason  │                             │
│                                   └────┬────┘                             │
│                                        │                                   │
│                                        │ 解决后重试                        │
│                                        ▼                                   │
│                                   ┌─────────┐                             │
│                                   │  idle   │                             │
│                                   └─────────┘                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.11.2 串流账号状态详细定义

| 状态      | 英文       | 说明               | 触发条件               | 后续状态                      |
| ------- | -------- | ---------------- | ------------------ | ------------------------- |
| **空闲**  | idle     | 无任务执行            | 初始化、任务结束、用户终止、错误恢复 | ready                     |
| **就绪中** | ready    | Token刷新+Xbox锁定成功 | 等待串流连接             | running / error           |
| **运行中** | running  | 自动化执行中           | 串流连接成功             | paused / stopping / error |
| **暂停中** | paused   | 暂停执行             | 用户主动暂停             | running / stopping        |
| **停止中** | stopping | 正在停止             | 用户请求停止             | idle                      |
| **异常**  | error    | 执行失败             | 各种错误（见错误类型）        | idle（解决后重试）               |

#### 5.11.3 错误类型详细分类

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        错误类型分类                                          │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  【第一类：Token 相关错误】                                                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 错误码          | 错误描述                    | 严重程度 | 处理方式  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ E_TOKEN_001   | refresh_token 无效/过期    | 🔴 高   | 通知商户  │   │
│  │ E_TOKEN_002   | Token 刷新超时              | 🟡 中   | 重试3次   │   │
│  │ E_TOKEN_003   | refresh_token 被撤销        | 🔴 高   | 重新授权  │   │
│  │ E_TOKEN_004   | 账号被封禁                  | 🔴 高   | 通知商户  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  【第二类：Xbox 相关错误】                                                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 错误码          | 错误描述                    | 严重程度 | 处理方式  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ E_XBOX_001    | Xbox 不在账号绑定列表        | 🔴 高   | 重新绑定  │   │
│  │ E_XBOX_002    | Xbox 离线/未开机             | 🟡 中   | 等待或跳过 │   │
│  │ E_XBOX_003    | Xbox 已被其他账号占用        | 🟡 中   | 选择其他  │   │
│  │ E_XBOX_004    | Xbox 拒绝串流请求            | 🔴 高   | 检查Xbox设置│   │
│  │ E_XBOX_005    | Xbox 锁定获取失败（竞争）    | 🟢 低   | 自动重试   │   │
│  │ E_XBOX_006    | Xbox 账号未在主机登录        | 🔴 高   | 手动登录   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  【第三类：网络/连接错误】                                                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 错误码          | 错误描述                    | 严重程度 | 处理方式  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ E_NET_001     | WebSocket 连接断开          | 🟡 中   | 自动重连   │   │
│  │ E_NET_002     | 视频流中断                   | 🟡 中   | 重连串流   │   │
│  │ E_NET_003     | API 调用超时                 | 🟢 低   | 重试       │   │
│  │ E_NET_004     | 局域网不可达                 | 🔴 高   | 检查网络   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  【第四类：自动化执行错误】                                                 │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 错误码          | 错误描述                    | 严重程度 | 处理方式  │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ E_AUTO_001    | 模板匹配超时（连续5次）      | 🟡 中   | 导航重试   │   │
│  │ E_AUTO_002    | 登录失败（账号/密码错误）    | 🔴 高   | 检查账号   │   │
│  │ E_AUTO_003    | 游戏启动超时                 | 🟡 中   | 重启或跳过 │   │
│  │ E_AUTO_004    | 游戏崩溃检测                 | 🟡 中   | 重新启动   │   │
│  │ E_AUTO_005    | 手柄操作无响应               | 🟢 低   | 重置手柄   │   │
│  │ E_AUTO_006    | OCR 识别失败                 | 🟢 低   | 使用模板   │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.11.4 错误码与状态的映射

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class ErrorSeverity(Enum):
    HIGH = "high"      # 🔴 需要商户介入
    MEDIUM = "medium"  # 🟡 Agent自动重试
    LOW = "low"        # 🟢 自动处理

@dataclass
class AutomationError:
    """自动化错误"""
    error_code: str
    error_type: str
    error_message: str
    severity: ErrorSeverity
    retryable: bool           # 是否可重试
    max_retries: int          # 最大重试次数
    next_action: str          # 下一步动作

class ErrorToStatusMapper:
    """错误码到状态的映射"""

    ERROR_MAPPING = {
        # Token 相关错误
        "E_TOKEN_001": AutomationError(
            error_code="E_TOKEN_001",
            error_type="TOKEN_EXPIRED",
            error_message="refresh_token 无效或已过期",
            severity=ErrorSeverity.HIGH,
            retryable=False,
            max_retries=0,
            next_action="NOTIFY_MERCHANT_REAUTH"
        ),
        "E_TOKEN_003": AutomationError(
            error_code="E_TOKEN_003",
            error_type="TOKEN_REVOKED",
            error_message="refresh_token 已被撤销",
            severity=ErrorSeverity.HIGH,
            retryable=False,
            max_retries=0,
            next_action="NOTIFY_MERCHANT_REAUTH"
        ),

        # Xbox 相关错误
        "E_XBOX_001": AutomationError(
            error_code="E_XBOX_001",
            error_type="XBOX_NOT_IN_BINDING",
            error_message="Xbox 不在账号绑定列表中",
            severity=ErrorSeverity.HIGH,
            retryable=False,
            max_retries=0,
            next_action="REBIND_XBOX"
        ),
        "E_XBOX_002": AutomationError(
            error_code="E_XBOX_002",
            error_type="XBOX_OFFLINE",
            error_message="Xbox 离线或未开机",
            severity=ErrorSeverity.MEDIUM,
            retryable=True,
            max_retries=3,
            next_action="WAIT_AND_RETRY"
        ),
        "E_XBOX_003": AutomationError(
            error_code="E_XBOX_003",
            error_type="XBOX_OCCUPIED",
            error_message="Xbox 已被其他账号占用",
            severity=ErrorSeverity.MEDIUM,
            retryable=True,
            max_retries=5,
            next_action="SELECT_ANOTHER_XBOX"
        ),
        "E_XBOX_005": AutomationError(
            error_code="E_XBOX_005",
            error_type="XBOX_LOCK_FAILED",
            error_message="Xbox 锁定获取失败（竞争）",
            severity=ErrorSeverity.LOW,
            retryable=True,
            max_retries=10,
            next_action="RETRY_WITH_BACKOFF"
        ),
        "E_XBOX_006": AutomationError(
            error_code="E_XBOX_006",
            error_type="ACCOUNT_NOT_LOGGED_IN",
            error_message="账号未在该 Xbox 上登录",
            severity=ErrorSeverity.HIGH,
            retryable=False,
            max_retries=0,
            next_action="MANUAL_LOGIN_REQUIRED"
        ),

        # 网络相关错误
        "E_NET_001": AutomationError(
            error_code="E_NET_001",
            error_type="WEBSOCKET_DISCONNECTED",
            error_message="WebSocket 连接断开",
            severity=ErrorSeverity.MEDIUM,
            retryable=True,
            max_retries=5,
            next_action="RECONNECT"
        ),
        "E_NET_002": AutomationError(
            error_code="E_NET_002",
            error_type="STREAM_INTERRUPTED",
            error_message="视频流中断",
            severity=ErrorSeverity.MEDIUM,
            retryable=True,
            max_retries=3,
            next_action="RESTART_STREAM"
        ),

        # 自动化执行错误
        "E_AUTO_001": AutomationError(
            error_code="E_AUTO_001",
            error_type="TEMPLATE_MATCH_TIMEOUT",
            error_message="模板匹配超时（连续5次失败）",
            severity=ErrorSeverity.MEDIUM,
            retryable=True,
            max_retries=3,
            next_action="NAVIGATE_AND_RETRY"
        ),
        "E_AUTO_002": AutomationError(
            error_code="E_AUTO_002",
            error_type="LOGIN_FAILED",
            error_message="游戏账号登录失败",
            severity=ErrorSeverity.HIGH,
            retryable=False,
            max_retries=0,
            next_action="CHECK_ACCOUNT_CREDENTIALS"
        ),
    }

    @classmethod
    def get_error(cls, error_code: str) -> Optional[AutomationError]:
        """根据错误码获取错误信息"""
        return cls.ERROR_MAPPING.get(error_code)

    @classmethod
    def should_retry(cls, error_code: str) -> bool:
        """判断错误是否应该重试"""
        error = cls.get_error(error_code)
        return error.retryable if error else False

    @classmethod
    def get_next_action(cls, error_code: str) -> str:
        """获取错误的后续动作"""
        error = cls.get_error(error_code)
        return error.next_action if error else "UNKNOWN"
```

#### 5.11.5 管理平台错误状态展示

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        管理平台串流账号状态与错误展示                          │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  【串流账号列表 - 状态列】                                                │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 账号邮箱          │ Xbox       │ 状态    │ 错误信息      │ 操作     │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │ user1@xx.com     │ Xbox-001   │ 🟢运行中│ -             │ 暂停 停止│   │
│  │ user2@xx.com     │ Xbox-002   │ 🟡就绪中│ -             │ 查看 停止│   │
│  │ user3@xx.com     │ -          │ 🔴异常  │ E_TOKEN_001  │ 重新授权│   │
│  │ user4@xx.com     │ Xbox-003   │ 🔴异常  │ E_XBOX_006   │ 手动登录│   │
│  │ user5@xx.com     │ Xbox-004   │ 🟠暂停  │ -             │ 继续 停止│   │
│  │ user6@xx.com     │ -          │ ⚪空闲  │ -             │ 启动    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  【错误详情弹窗】                                                          │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 🔴 账号异常详情                                    [×]              │   │
│  ├─────────────────────────────────────────────────────────────────────┤   │
│  │                                                                     │   │
│  │  错误类型: Token 过期                                                │   │
│  │  错误码:   E_TOKEN_001                                               │   │
│  │  严重程度: 🔴 高（需要商户介入）                                     │   │
│  │  错误描述: refresh_token 无效或已过期                               │   │
│  │  发生时间: 2024-01-15 14:30:25                                      │   │
│  │  Xbox:     Xbox-003 (user3@xx.com)                                 │   │
│  │                                                                     │   │
│  │  建议操作:                                                          │   │
│  │  1. 点击下方「重新授权」按钮                                         │   │
│  │  2. 使用手机扫描二维码完成授权                                       │   │
│  │  3. 系统将自动更新 Token                                            │   │
│  │                                                                     │   │
│  │                              [重新授权]  [取消]                      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.11.6 数据库错误状态字段

```sql
-- 串流账号表增加错误相关字段
ALTER TABLE streaming_account ADD COLUMN last_error_code VARCHAR(20);
ALTER TABLE streaming_account ADD COLUMN last_error_message TEXT;
ALTER TABLE streaming_account ADD COLUMN last_error_at TIMESTAMP;
ALTER TABLE streaming_account ADD COLUMN error_retry_count INT DEFAULT 0;
ALTER TABLE streaming_account ADD COLUMN status VARCHAR(20) DEFAULT 'idle';

-- 错误历史记录表
CREATE TABLE streaming_error_log (
    id BIGSERIAL PRIMARY KEY,
    streaming_account_id BIGINT NOT NULL,
    xbox_host_id BIGINT,
    error_code VARCHAR(20) NOT NULL,
    error_message TEXT,
    error_trace TEXT,
    severity VARCHAR(10) NOT NULL,  -- HIGH, MEDIUM, LOW
    retry_count INT DEFAULT 0,
    resolved_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    FOREIGN KEY (streaming_account_id) REFERENCES streaming_account(id),
    FOREIGN KEY (xbox_host_id) REFERENCES xbox_host(id)
);

CREATE INDEX idx_error_log_account ON streaming_error_log(streaming_account_id);
CREATE INDEX idx_error_log_code ON streaming_error_log(error_code);
CREATE INDEX idx_error_log_created ON streaming_error_log(created_at);
```

#### 5.11.7 错误处理流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        错误处理流程                                          │
├─────────────────────────────────────────────────────────────────────────────┤
                                                                             │
│  【错误发生】                                                              │
│       │                                                                     │
│       ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 1. 记录错误到 error_log 表                                          │   │
│  │    - error_code, error_message, error_trace                         │   │
│  │    - streaming_account_id, xbox_host_id                            │   │
│  │    - created_at, severity                                           │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 2. 更新 streaming_account 错误字段                                  │   │
│  │    - last_error_code, last_error_message, last_error_at             │   │
│  │    - status = 'error'                                               │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 3. 判断错误严重程度                                                  │   │
│  │                                                                     │   │
│  │    ┌─────────────────────────────────────────────────────────────┐  │   │
│  │    │ 严重程度判断                                                   │  │   │
│  │    │                                                              │  │   │
│  │    │  🔴 HIGH (商户介入) ──► 通知商户，等待处理                    │  │   │
│  │    │                                                              │  │   │
│  │    │  🟡 MEDIUM (Agent重试) ──► 等待后重试或选择其他Xbox         │  │   │
│  │    │                                                              │  │   │
│  │    │  🟢 LOW (自动处理) ──► 立即重试，使用指数退避              │  │   │
│  │    └─────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 4. 释放 Xbox 锁（如果是 Xbox 相关错误）                              │   │
│  │    - DistributedXboxLock.release_xbox_lock(xbox_id)                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│       │                                                                     │
│       ▼                                                                    │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │ 5. 根据错误类型执行后续动作                                          │   │
│  │                                                                     │   │
│  │  NOTIFY_MERCHANT_REAUTH ──► 发送邮件/推送，商户重新授权            │   │
│  │  SELECT_ANOTHER_XBOX ──────► 尝试锁定其他 Xbox                    │   │
│  │  RESTART_STREAM ──────────► 重新建立串流连接                      │   │
│  │  MANUAL_LOGIN_REQUIRED ────► 通知商户手动登录 Xbox                │   │
│  │  WAIT_AND_RETRY ───────────► 等待后重试                           │   │
│  │                                                                     │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 5.11.8 WebSocket 错误推送

当串流账号发生错误时，Agent 通过 WebSocket 实时推送错误信息到管理平台：

```python
# Agent 端错误推送
class ErrorPusher:
    def __init__(self, websocket):
        self.ws = websocket

    async def push_error(
        self,
        streaming_account_id: int,
        xbox_host_id: Optional[int],
        error: AutomationError
    ):
        """推送错误到管理平台"""
        message = {
            "type": "STREAMING_ERROR",
            "data": {
                "streaming_account_id": streaming_account_id,
                "xbox_host_id": xbox_host_id,
                "error_code": error.error_code,
                "error_type": error.error_type,
                "error_message": error.error_message,
                "severity": error.severity.value,
                "timestamp": datetime.now().isoformat(),
                "suggested_action": error.next_action
            }
        }
        await self.ws.send_json(message)

    async def push_error_resolved(
        self,
        streaming_account_id: int,
        error_code: str
    ):
        """推送错误解决消息"""
        message = {
            "type": "STREAMING_ERROR_RESOLVED",
            "data": {
                "streaming_account_id": streaming_account_id,
                "error_code": error_code,
                "resolved_at": datetime.now().isoformat()
            }
        }
        await self.ws.send_json(message)
```

***

## 六、与自动化项目集成

### 6.1 Agent 安装与商户绑定流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Agent 安装激活流程                                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【商户操作】                                                                │
│                                                                             │
│  1. 商户在管理平台 → Agent 管理 → 批量生成安装码                              │
│     - 输入电脑数量（如：3台）                                                │
│     - 批量生成安装码（格式：XXXX-XXXX-XXXX-XXXX）                            │
│                                                                             │
│  2. 生成结果：                                                               │
│     - 批次ID: BATCH-2024-001                                                │
│     - 安装码1: XST4-A7K2-M9N3-P5L8 → 员工A                                │
│     - 安装码2: K9M2-B3N6-L8P1-Q4R7 → 员工B                                │
│     - 安装码3: P2N5-M8K9-R3Q6-W1J4 → 员工C                                │
│                                                                             │
│  【员工在电脑安装】                                                          │
│                                                                             │
│  3. 员工在电脑上运行 Agent 安装程序                                          │
│  4. 输入安装码                                                              │
│  5. 配置该电脑上的 Xbox 信息（IP、MAC等）                                    │
│  6. Agent 调用注册接口，携带安装码和 Xbox 配置                                │
│  7. Backend 验证安装码，绑定 Agent 到商户                                    │
│                                                                             │
│  【安装码特性】                                                              │
│                                                                             │
│  - 一次性使用：每个码只能用一次                                              │
│  - 24小时过期：超过24小时未使用则失效                                        │
│  - 唯一校验：HMAC-SHA256 校验码防止伪造                                      │
│  - 绑定商户：每个码绑定到对应商户                                            │
│  - Xbox 配置：Agent 安装时单独配置，不在安装码中                              │
│                                                                             │
│  【Agent 与商户关系】                                                        │
│                                                                             │
│  - 一个 Agent 只能绑定一个商户                                               │
│  - 一个商户可以有多个 Agent（多台电脑）                                       │
│  - Agent 安装时通过安装码绑定商户，安装后无法切换                              │
│  - 不同商户的 Agent 完全隔离，不能共享                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**安装码生成 API：**

| 方法   | 路径                        | 说明               |
| ---- | ------------------------- | ---------------- |
| POST | /api/agents/generate-code | 商户批量生成 Agent 安装码 |
| POST | /api/agent/register       | Agent 使用安装码注册    |

**POST /api/agents/generate-code** - 批量生成安装码（商户操作）

```json
// Request
{
  "count": 3              // 需要生成的安装码数量
}

// Response 200
{
  "success": true,
  "totalGenerated": 3,
  "installCodes": [
    {
      "code": "XST4-A7K2-M9N3-P5L8",
      "index": 1,
      "expireTime": "2024-01-16T10:00:00Z"
    },
    {
      "code": "K9M2-B3N6-L8P1-Q4R7",
      "index": 2,
      "expireTime": "2024-01-16T10:00:00Z"
    },
    {
      "code": "P2N5-M8K9-R3Q6-W1J4",
      "index": 3,
      "expireTime": "2024-01-16T10:00:00Z"
    }
  ]
}
```

**POST /api/agent/register** - Agent 注册（携带安装码）

```json
// Request - 注册时需要配置该电脑上的 Xbox 信息
{
  "installCode": "XST4-A7K2-M9N3-P5L8",
  "host": "192.168.1.100",
  "port": 9999,
  "macAddress": "AA:BB:CC:DD:EE:FF",
  "xboxConfigs": [
    {"windowIndex": 0, "ipAddress": "192.168.1.50", "name": "Xbox-1", "macAddress": "11:22:33:44:55:66"},
    {"windowIndex": 1, "ipAddress": "192.168.1.51", "name": "Xbox-2", "macAddress": "22:33:44:55:66:77"},
    {"windowIndex": 2, "ipAddress": "192.168.1.52", "name": "Xbox-3", "macAddress": "33:44:55:66:77:88"},
    {"windowIndex": 3, "ipAddress": "192.168.1.53", "name": "Xbox-4", "macAddress": "44:55:66:77:88:99"}
  ],
  "version": "1.0.0"
}

// Response 200
{
  "success": true,
  "agentId": "agent-001",
  "agentDbId": 1,
  "merchantId": 1,
  "config": {
    "heartbeatInterval": 30,
    "maxRestartCount": 3
  }
}

// Response 400 (安装码无效或已过期)
{
  "success": false,
  "error": "INSTALL_CODE_INVALID",
  "message": "安装码无效或已过期"
}
```

**数据库表：**

```sql
-- Agent 安装码表（用于绑定 Agent 到商户）
CREATE TABLE agent_install_code (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    code VARCHAR(19) NOT NULL UNIQUE COMMENT '安装码（格式：XXXX-XXXX-XXXX-XXXX）',
    code_index INT NOT NULL COMMENT '安装码序号（同一批次内的顺序）',
    batch_id VARCHAR(64) NOT NULL COMMENT '批次ID（同一批次生成的所有码）',
    status ENUM('pending', 'used', 'expired') DEFAULT 'pending' COMMENT '状态',
    used_at DATETIME COMMENT '使用时间',
    expire_at DATETIME NOT NULL COMMENT '过期时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_code (code),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_batch_id (batch_id),
    UNIQUE KEY uk_code (code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent安装码表';
```

**安装码格式与校验：**

```
格式: XXXX-XXXX-XXXX-XXXX（4段4位，共16位）
示例: XST4-A7K2-M9N3-P5L8

结构:
├── 前4位: 随机大写字母+数字
├── 中4位: 随机大写字母+数字
├── 中4位: 随机大写字母+数字
└── 后4位: 随机大写字母+数字

校验码计算:
- 使用 HMAC-SHA256 计算校验位
- 输入: 商户ID + 批次ID + 序号 + 密钥
- 确保每个码的唯一性和可验证性
```

**安装码工作原理：**

```
1. 商户在管理平台输入数量（如3台电脑）
         ↓
2. Backend 生成批次ID（UUID）
         ↓
3. 批量生成3个安装码，每个包含:
   - 唯一序号 (1, 2, 3)
   - 批次ID（相同）
   - 独立校验码
   - 24小时过期时间
         ↓
4. 安装码存储到数据库（状态=pending）
         ↓
5. 商户分发安装码给员工
         ↓
6. 员工在电脑上输入安装码安装
         ↓
7. Backend 验证安装码:
   - 码存在？
   - 未过期？
   - 未被使用？
   - 校验码正确？
         ↓
   ├─ 验证失败 → 返回错误
   │
   └─ 验证成功 → 绑定Agent到商户（状态=used）
         ↓
8. 返回 agent_id 给 Agent
```

**Agent 注册流程图：**

```
商户电脑 (Agent)                    云服务器                      管理平台
      │                              │                            │
      │  1. 输入安装码               │                            │
      │ ─────────────────────────────>│                            │
      │                              │                            │
      │                              │  2. 验证安装码              │
      │                              │ ──────────────────────────>│
      │                              │                            │
      │                              │  3. 绑定信息返回             │
      │                              │ <──────────────────────────│
      │                              │                            │
      │  4. 注册成功                  │                            │
      │ <────────────────────────────│                            │
      │                              │                            │
      │  5. 开始心跳                  │                            │
      │ ─────────────────────────────>│                            │
      │                              │  6. WebSocket 推送           │
      │                              │───────────────────────────>│
      │                              │                            │
      │                              │   商户在管理平台看到新 Agent  │
```

### 6.2 启动自动化流程

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│   Frontend  │    │   Backend   │    │   Agent     │    │  Automation │
│   (Vue)     │    │   (Java)    │    │  (Python)   │    │  (Python)   │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                 │                   │                   │
       │ POST /start     │                   │                   │
       │────────────────>│                   │                   │
       │                 │                   │                   │
       │                 │ POST /start       │                   │
       │                 │───────────────────>│                   │
       │                 │                   │                   │
       │                 │  {streaming,      │                   │
       │                 │   games[],         │                   │
       │                 │   agentId}         │                   │
       │                 │                   │                   │
       │                 │                   │  HTTP/gRPC        │
       │                 │                   │──────────────────>│
       │                 │                   │                   │
       │                 │                   │  启动自动化       │
       │                 │                   │                   │
       │                 │                   │  状态变化推送     │
       │                 │<──────────────────│                   │
       │                 │                   │                   │
       │  WebSocket      │                   │                   │
       │<────────────────│                   │                   │
       │                 │                   │                   │
```

### 6.3 自动化启动时接收的数据结构

```json
{
  "taskId": "12345",
  "streamingAccount": {
    "id": 1,
    "name": "账号1",
    "email": "user@outlook.com",
    "password": "encrypted_password",
    "authCode": "optional_code"
  },
  "gameAccounts": [
    {
      "id": 1,
      "name": "主游戏账号",
      "xboxGamertag": "PlayerOne",
      "isPrimary": true
    },
    {
      "id": 2,
      "name": "副游戏账号",
      "xboxGamertag": "PlayerTwo",
      "isPrimary": false
    }
  ],
  "automationConfig": {
    "autoLogin": true,
    "autoStream": true,
    "autoSwitchGame": true
  }
}
```

### 6.4 模板管理系统设计

**模板分类：**

| 类型         | 说明                 | 存储位置                 |
| ---------- | ------------------ | -------------------- |
| **共用模板**   | 通用界面（主菜单、设置、保存提示等） | `/templates/common/` |
| **游戏专用模板** | 特定游戏的界面            | `/templates/{game}/` |

**目录结构：**

```
templates/
├── common/                          # 共用模板
│   ├── main_menu.png                # 主菜单
│   ├── settings.png                  # 设置按钮
│   ├── confirm_button.png            # 确认按钮
│   └── ...
│
├── game_a/                         # 游戏A专用模板
│   ├── login_screen.png             # 登录界面
│   ├── match_start.png              # 比赛开始
│   └── ...
```

**Agent 本地模板缓存：**

```
~/.xstreaming/
├── templates/
│   ├── common/
│   ├── game_a/
│   └── templates_version.json
```

**模板匹配流程（SceneBasedMatcher）：**

```
截图当前界面
    │
    ├── 比赛场景 → OpenCV 模板匹配（速度快）
    └── 设置/登录场景 → Hybrid 混合匹配（模板+OCR）
```

### 6.5 Xbox 变动检测方案

**检测机制：**

| 触发条件      | 检测方式         |
| --------- | ------------ |
| Agent 启动时 | 全量扫描         |
| 定时检测      | 每5分钟扫描一次     |
| 商户手动触发    | 管理平台"重新扫描"按钮 |

**上报格式：**

```json
POST /api/agents/{id}/xbox-changes
{
  "changes": [
    {"type": "added", "xbox": {...}},
    {"type": "removed", "xboxId": 3},
    {"type": "updated", "xbox": {...}}
  ]
}
```

### 6.6 商户数据隔离方案

| 角色   | 可见范围            |
| ---- | --------------- |
| 管理员  | 所有商户、所有数据       |
| 商户   | 仅自己商户的数据        |
| 商户员工 | 仅自己商户的数据（受权限控制） |

**JWT Token 包含：**

```json
{
  "role": "merchant",
  "merchantId": 1
}
```

### 6.7 商户登录/激活完整方案

#### 6.7.1 整体流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        商户账号管理体系                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【管理员操作】- 管理员添加商户                                            │
│                                                                             │
│  1. 管理员在管理后台添加商户                                                │
│     - 输入手机号（必填）                                                    │
│  2. 系统根据手机号生成:                                                    │
│     - 邀请码（关联手机号）                                                 │
│  3. 管理员将邀请码发给商户                                                 │
│                                                                             │
│  【点卡验证码生成】                                                        │
│                                                                             │
│  1. 商户向管理员购买点卡                                                  │
│  2. 管理员选择类型（周卡/月卡/年卡）和数量                                 │
│  3. 系统生成点卡验证码（格式：XXXX-XXXX-XXXX）                            │
│  4. 管理员将点卡验证码发给商户                                             │
│                                                                             │
│  【商户激活】- 首次使用                                                    │
│                                                                             │
│  1. 打开激活页面                                                           │
│  2. 输入: 邀请码（手机号自动关联显示）                                      │
│  3. 输入: 点卡验证码                                                        │
│  4. 设置密码                                                                │
│  5. 完成激活                                                                │
│                                                                             │
│  【日常登录】                                                              │
│                                                                             │
│  1. 输入手机号 + 密码                                                      │
│  2. 正常登录                                                                │
│                                                                             │
│  【忘记密码】                                                              │
│                                                                             │
│  1. 点击"忘记密码"                                                          │
│  2. 输入手机号 → 收到短信验证码 → 重置密码                                  │
│                                                                             │
│  【账号过期续费】                                                          │
│                                                                             │
│  1. 登录时提示"账号已过期"                                                  │
│  2. 输入新的点卡验证码                                                      │
│  3. 续期后继续使用（无需重新设置密码）                                       │
│                                                                             │
│  【过期禁止登录】                                                          │
│                                                                             │
│  - 账号过期后不能登录                                                      │
│  - 必须先续费才能重新登录                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.7.2 激活页面设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            激活页面                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  手机号: [138****8000] ← 自动识别（通过邀请码关联）                      │
│                                                                             │
│  邀请码: [INV4-X7K2-M9N3] ← 输入后自动显示关联手机号                     │
│                                                                             │
│  点卡验证码: [____________] ← 购买点卡获得                                 │
│                                                                             │
│  设置密码: [____________]                                                   │
│                                                                             │
│  确认密码: [____________]                                                   │
│                                                                             │
│                              [激活账号]                                     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.7.3 登录页面设计

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            登录页面                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  手机号: [____________]                                                     │
│                                                                             │
│  密码:   [____________]                                                     │
│                                                                             │
│                              [登录]                                         │
│                                                                             │
│                    [忘记密码？]                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.7.4 账号过期续费页面

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          账号已过期                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│                    ⚠️ 您的账号已于 2024-01-15 到期                       │
│                                                                             │
│              点卡验证码: [____________]                                     │
│                                                                             │
│                         [续费并登录]                                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.7.5 忘记密码流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         忘记密码流程                                         │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 点击"忘记密码"                                                          │
│         │                                                                   │
│         ▼                                                                   │
│  2. 输入手机号                                                              │
│         │                                                                   │
│         ▼                                                                   │
│  3. 系统发送短信验证码                                                      │
│         │                                                                   │
│         ▼                                                                   │
│  4. 输入短信验证码 + 新密码                                                  │
│         │                                                                   │
│         ▼                                                                   │
│  5. 密码重置成功，用新密码登录                                              │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.7.6 首次激活 vs 续费 vs 过期禁止登录

| 场景         | 输入                | 操作          | 结果          |
| ---------- | ----------------- | ----------- | ----------- |
| **首次激活**   | 邀请码 + 验证码 + 密码    | 创建商户账号      | 新账号创建，可登录   |
| **正常登录**   | 手机号 + 密码          | 验证登录（检查未过期） | 进入管理平台      |
| **忘记密码**   | 手机号 + 短信验证码 + 新密码 | 重置密码        | 用新密码登录      |
| **账号过期续费** | 验证码               | 延长有效期       | 续费后可登录      |
| **过期未续费**  | 手机号 + 密码          | 检查过期        | ❌ 禁止登录，提示续费 |

#### 6.7.7 密码安全策略（AES 加密）

**密码加密方式**：

- 算法：AES-256-ECB
- 密钥：`bend-platform-secret-key`（生产环境应使用环境变量或配置中心管理）
- 存储格式：HEX(AES\_ENCRYPT(明文密码, 密钥))

**数据库存储**：

```sql
-- 存储时加密
UPDATE merchant_user
SET password_hash = HEX(AES_ENCRYPT('用户输入的密码', 'bend-platform-secret-key'))
WHERE id = ?;

-- 验证时解密比对
SELECT AES_DECRYPT(UNHEX(password_hash), 'bend-platform-secret-key') AS decrypted
FROM merchant_user
WHERE username = 'admin';
```

**应用层验证流程**：

```
1. 用户输入手机号 + 密码
2. 后端查询数据库获取加密的 password_hash
3. 使用 AES_DECRYPT(UNHEX(password_hash), '密钥') 解密
4. 比对解密后的密码与用户输入
5. 匹配成功则登录成功
```

**为什么用 AES 而不是哈希？**

- 商户密码需要可解密（用于 Xbox 账号密码等场景）
- 串流账号的 auth\_code 等也需要可解密使用
- 如果只需验证不需要明文，应使用 bcrypt/argon2

#### 6.7.8 数据库字段

```sql
-- 邀请码表
CREATE TABLE invite_code (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    code VARCHAR(19) NOT NULL UNIQUE COMMENT '邀请码（格式：INV4-XXXX-XXXX-XXXX）',
    phone VARCHAR(20) NOT NULL COMMENT '关联手机号',
    status ENUM('pending', 'used', 'expired') DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expired_at DATETIME NOT NULL COMMENT '过期时间（默认7天）',
    created_by BIGINT COMMENT '创建人（管理员ID）',
    INDEX idx_code (code),
    INDEX idx_phone (phone),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 点卡验证码表
CREATE TABLE activation_code (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    code VARCHAR(19) NOT NULL UNIQUE COMMENT '点卡验证码（格式：XXXX-XXXX-XXXX）',
    period_type ENUM('week', 'month', 'year') NOT NULL COMMENT '周期类型',
    period_count INT DEFAULT 1 COMMENT '周期数量',
    status ENUM('pending', 'used', 'expired') DEFAULT 'pending',
    used_at DATETIME COMMENT '使用时间',
    used_merchant_id BIGINT COMMENT '使用的商户ID',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    created_by BIGINT COMMENT '创建人（管理员ID）',
    INDEX idx_code (code),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 商户表
CREATE TABLE merchant (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    phone VARCHAR(20) NOT NULL UNIQUE COMMENT '手机号',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码',
    name VARCHAR(100) COMMENT '商户名称',
    status ENUM('active', 'expired', 'suspended') DEFAULT 'active',
    expire_time DATETIME COMMENT '账号过期时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_phone (phone),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

#### 6.7.10 商户过期与Agent限制机制

```

┌─────────────────────────────────────────────────────────────────────────────┐
│                        商户过期与Agent限制机制                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【商户过期检测】                                                            │
│                                                                             │
│  - 商户状态: active / expired / suspended                                  │
│  - expire\_time: 账号过期时间                                                │
│  - 心跳时校验: 每次心跳时检查商户状态                                        │
│                                                                             │
│  【商户过期后Agent行为】                                                    │
│                                                                             │
│  1. Agent 发送心跳到服务端                                                  │
│  2. 服务端检查商户状态:                                                     │
│     - status = 'active' → 返回正常心跳响应，继续工作                        │
│     - status = 'expired' → 返回限制指令，Agent 被限制                       │
│     - status = 'suspended' → 返回暂停指令，Agent 完全停止                    │
│                                                                             │
│  【限制级别】                                                                │
│                                                                             │
│  | 状态 | 心跳响应 | Agent 行为 | 能否启动新任务 | 能否观看视频 |           │
│  |------|-------------|-----------|----------------|----------------------|  │
│  | active | {"restricted": false} | 正常工作 | ✅ 可以 | ✅ 可以 |        │
│  | expired | {"restricted": true} | 仅可观看视频 | ❌ 禁止 | ✅ 可以 |      │
│  | suspended | {"restricted": true, "action": "stop"} | 完全停止 | ❌ | ❌ |  │
│                                                                             │
│  【防作弊机制】                                                              │
│                                                                             │
│  1. 商户状态校验:                                                           │
│     - 心跳时必须校验商户状态                                                 │
│     - 禁止在过期状态下启动新自动化任务                                       │
│                                                                             │
│  2. 任务启动双重校验:                                                       │
│     - 前端发送任务启动请求时服务端校验                                       │
│     - Agent 实际执行时再次校验                                               │
│     - 防止前端绕过校验                                                       │
│                                                                             │
│  3. Agent 无法自行解除限制:                                                 │
│     - 限制状态由服务端控制                                                   │
│     - Agent 不能通过修改本地配置绕过                                         │
│     - 心跳响应包含校验签名，防止伪造                                         │
│                                                                             │
│  4. 录像/日志强制上传:                                                      │
│     - 任务执行过程录像实时上传                                               │
│     - 日志实时同步到服务端                                                   │
│     - 服务端可审计所有任务                                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

````

**心跳响应（包含商户状态）：**

```json
// 商户正常
Response:
{
  "received": true,
  "agentId": "agent-001",
  "merchantStatus": "active",
  "restricted": false,
  "config": {
    "heartbeatInterval": 30,
    "maxRestartCount": 3
  }
}

// 商户已过期
Response:
{
  "received": true,
  "agentId": "agent-001",
  "merchantStatus": "expired",
  "restricted": true,
  "message": "商户账号已过期，请续费",
  "config": {
    "heartbeatInterval": 30,
    "allowNewTask": false,
    "allowVideoView": true
  }
}

// 商户被暂停
Response:
{
  "received": true,
  "agentId": "agent-001",
  "merchantStatus": "suspended",
  "restricted": true,
  "action": "stop",
  "message": "商户账号已被暂停",
  "config": {
    "allowNewTask": false,
    "allowVideoView": false
  }
}
````

**防作弊校验签名：**

```
心跳响应签名:
- 使用 HMAC-SHA256 签名
- 输入: merchantId + agentId + timestamp + 密钥
- Agent 验证签名后才执行指令
- 防止中间人篡改响应
```

#### 6.7.11 暂停超时机制

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        暂停超时机制                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【超时设置】                                                                │
│                                                                             │
│  - 暂停超时时间: 1小时（可配置）                                            │
│  - 超时后自动恢复任务                                                        │
│                                                                             │
│  【超时处理流程】                                                            │
│                                                                             │
│  1. 商户点击"暂停"                                                          │
│  2. Agent 发送暂停指令到 Xbox                                               │
│  3. Xbox 游戏暂停，但保持连接                                               │
│  4. 启动超时计时器（默认1小时）                                             │
│  5. 商户点击"恢复" → 取消计时器，正常恢复                                   │
│  6. 超时（1小时到）:                                                        │
│     - 自动触发恢复                                                           │
│     - Agent 发送恢复指令到 Xbox                                             │
│     - 任务从断点继续                                                        │
│     - 记录超时恢复日志                                                      │
│                                                                             │
│  【超时恢复日志】                                                            │
│                                                                             │
│  {                                                                           │
│    "event": "PAUSE_TIMEOUT_RECOVERY",                                      │
│    "taskId": 123,                                                          │
│    "pauseDuration": 3600,                                                  │
│    "recoveredAt": "2024-01-15T11:00:00Z"                                   │
│  }                                                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**暂停超时配置 API：**

```json
// GET /api/merchant/config - 获取商户配置
Response:
{
  "pauseTimeoutMinutes": 60,  // 暂停超时时间（分钟）
  "autoResumeEnabled": true
}

// PUT /api/merchant/config - 更新商户配置
Request:
{
  "pauseTimeoutMinutes": 120,  // 自定义超时时间
  "autoResumeEnabled": true
}
```

````

#### 6.7.8 邀请码和点卡验证码生成 API

```json
// POST /api/admin/invite-codes/generate - 管理员生成邀请码
Request:
{
  "phone": "13800138000",
  "expireDays": 7    // 有效期天数，默认7天
}

Response:
{
  "success": true,
  "inviteCode": {
    "code": "INV4-A7K2-M9N3-P5L8",
    "phone": "13800138000",
    "expireTime": "2024-01-22T10:00:00Z",
    "status": "pending"
  }
}

// GET /api/admin/invite-codes?phone=13800138000 - 查询邀请码列表
Response:
{
  "inviteCodes": [
    {
      "code": "INV4-A7K2-M9N3-P5L8",
      "phone": "13800138000",
      "status": "pending",
      "expireTime": "2024-01-22T10:00:00Z",
      "createdAt": "2024-01-15T10:00:00Z"
    },
    {
      "code": "INV4-B3N6-L8P1-Q4R7",
      "phone": "13800138000",
      "status": "expired",
      "expireTime": "2024-01-10T10:00:00Z",
      "createdAt": "2024-01-03T10:00:00Z"
    }
  ]
}

// POST /api/admin/activation-codes/generate - 管理员生成点卡验证码
Request:
{
  "periodType": "month",    // week/month/year
  "count": 5                // 生成数量
}

Response:
{
  "success": true,
  "totalGenerated": 5,
  "activationCodes": [
    {"code": "XST4-A7K2-M9N3-P5L8", "periodType": "month", "periodCount": 1},
    {"code": "K9M2-B3N6-L8P1-Q4R7", "periodType": "month", "periodCount": 1},
    {"code": "P2N5-M8K9-R3Q6-W1J4", "periodType": "month", "periodCount": 1},
    {"code": "W7T2-J5K8-N3P6-L9M4", "periodType": "month", "periodCount": 1},
    {"code": "Q4L6-R8N2-M5K9-J3W7", "periodType": "month", "periodCount": 1}
  ]
}

// POST /api/admin/activation-codes/batch - 批量生成不同周期
Request:
{
  "codes": [
    {"periodType": "week", "count": 3},
    {"periodType": "month", "count": 5},
    {"periodType": "year", "count": 1}
  ]
}
````

#### 6.7.9 邀请码过期处理

```
邀请码过期后:
    │
    ├── 状态自动变为 expired
    │
    ├── 商户无法使用该邀请码激活
    │
    └── 管理员可重新生成新的邀请码

管理员操作:
    1. 查询该手机号的邀请码
    2. 发现邀请码已过期
    3. 重新生成新的邀请码
    4. 将新邀请码发给商户
```

#### 6.7.8 API 设计

```json
// POST /api/auth/activate - 首次激活
{
  "inviteCode": "INV4-X7K2-M9N3-P5L8",
  "activationCode": "XST4-A7K2-M9N3-P5L8",
  "password": "newPassword123"
}
// 手机号通过邀请码自动识别

// POST /api/auth/login - 日常登录
{
  "phone": "13800138000",
  "password": "password123"
}

// POST /api/auth/forgot-password - 忘记密码
{
  "phone": "13800138000",
  "smsCode": "123456",
  "newPassword": "newPassword123"
}

// POST /api/auth/renew - 账号过期续费
{
  "phone": "13800138000",
  "password": "password123",
  "activationCode": "XST4-NEW1-M9N3-P5L8"
}

// POST /api/auth/check-expire - 检查账号状态
{
  "phone": "13800138000"
}
// Response
{
  "status": "active",        // active / expired
  "expireTime": "2024-02-15",
  "daysRemaining": 30
}
```

#### 6.7.9 登录响应（包含账号状态）

```json
// POST /api/auth/login - 正常登录响应
{
  "success": true,
  "token": "eyJhbGci...",
  "merchant": {
    "id": 1,
    "phone": "13800138000",
    "name": "商户A",
    "status": "active",
    "expireTime": "2024-02-15",
    "daysRemaining": 30
  }
}

// POST /api/auth/login - 账号过期响应
{
  "success": false,
  "error": "ACCOUNT_EXPIRED",
  "message": "账号已过期，请续费",
  "expireTime": "2024-01-15"
}

// POST /api/auth/renew - 续费响应
{
  "success": true,
  "expireTime": "2024-02-15",
  "daysRemaining": 30
}
```

#### 6.7.10 短信验证码

| 场景    | 发送方式 | 有效期 |
| ----- | ---- | --- |
| 忘记密码  | 短信   | 5分钟 |
| 更换手机号 | 短信   | 5分钟 |

#### 6.7.11 密码重置安全措施

| 措施          | 说明              |
| ----------- | --------------- |
| 短信验证码       | 必须输入正确验证码才能重置密码 |
| 验证码有效期      | 5分钟，过期需重新获取     |
| 错误次数限制      | 连续5次错误，锁定30分钟   |
| 新密码不能与旧密码相同 | 防止简单修改          |

### 6.8 模板更新机制

#### 6.8.1 模板版本管理（按商户维度）

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        模板更新流程（按商户维度）                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【模板归属】                                                              │
│                                                                             │
│  - 模板以商户为维度进行管理                                                │
│  - 商户A的模板更新，只通知商户A下的Agent                                   │
│  - 不同商户可以有不同版本的模板                                            │
│                                                                             │
│  【商户首次激活】                                                          │
│                                                                             │
│  1. 商户激活时，初始化模板版本                                            │
│  2. 商户获得当前平台默认模板版本                                            │
│                                                                             │
│  【模板更新流程】                                                          │
│                                                                             │
│  1. 平台管理员更新某商户的模板                                            │
│  2. 系统标记该商户的模板版本为"有更新"                                     │
│  3. 该商户下的所有Agent在下次心跳时收到更新通知                            │
│  4. Agent 按需下载最新模板                                                  │
│                                                                             │
│  【模板更新时机】                                                          │
│                                                                             │
│  - 如果 Agent 正在执行任务，模板不会立即更新                               │
│  - 等当前任务完成后，再下载更新模板                                         │
│  - 避免任务执行到一半被模板更新打断                                         │
│  - 下一轮任务开始时使用新模板                                               │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.8.2 Agent 获取模板

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Agent 获取模板流程                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【Agent 启动时】                                                          │
│                                                                             │
│  1. Agent 连接云服务器                                                     │
│  2. 发送心跳，上报:                                                        │
│     - agentId                                                              │
│     - merchantId                                                           │
│     - 本地模板版本                                                         │
│  3. 服务端返回该商户需要更新的模板列表                                      │
│  4. Agent 下载更新模板                                                      │
│                                                                             │
│  【模板版本同步】                                                          │
│                                                                             │
│  心跳时:                                                                  │
│  - Agent 上报: {"merchantId": 1, "templateVersions": {...}}              │
│  - 服务端返回: {"updates": [{"name": "...", "version": "..."}]}          │
│                                                                             │
│  【商户维度隔离】                                                          │
│                                                                             │
│  - 服务端根据 merchantId 返回该商户的模板                                  │
│  - 商户A看不到商户B的模板                                                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.8.3 模板版本同步 API

```json
// POST /api/agent/heartbeat - 心跳上报模板版本
Request:
{
  "agentId": "agent-001",
  "merchantId": 1,
  "templateVersions": {
    "common/main_menu": "1.0.0",
    "game_a/login_screen": "1.0.1"
  }
}

Response:
{
  "received": true,
  "templateUpdates": [
    {"name": "common/main_menu", "version": "1.0.1", "url": "/api/templates/1/common/main_menu"},
    {"name": "game_a/login_screen", "version": "1.0.2", "url": "/api/templates/1/game_a/login_screen"}
  ]
}

// GET /api/templates/{merchantId}/{category}/{name}?version=1.0.1 - 下载模板
```

#### 6.8.4 模板版本回滚

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        模板版本回滚                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【回滚场景】                                                              │
│                                                                             │
│  - 新版本模板有问题，需要退回旧版本                                        │
│                                                                             │
│  【回滚流程】                                                              │
│                                                                             │
│  1. 管理员在管理平台选择模板                                              │
│  2. 查看版本历史                                                          │
│  3. 选择要回滚到的版本                                                    │
│  4. 确认回滚                                                              │
│  5. 系统将该商户的模板版本标记为旧版本                                     │
│  6. Agent 下次心跳时收到回滚通知                                          │
│  7. Agent 下载旧版本模板                                                   │
│                                                                             │
│  【版本历史记录】                                                          │
│                                                                             │
│  模板版本历史:                                                             │
│  - v1.0.0 (2024-01-01) - 初始版本                                       │
│  - v1.0.1 (2024-01-15) - 更新了 xxx                                     │
│  - v1.0.2 (2024-01-20) - 更新了 yyy [当前版本]                         │
│                     [回滚到 v1.0.1]                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**模板版本回滚 API：**

```json
// GET /api/templates/{merchantId}/{category}/{name}/versions - 获取版本历史
Response:
{
  "versions": [
    {"version": "1.0.0", "createdAt": "2024-01-01T00:00:00Z", "changelog": "初始版本"},
    {"version": "1.0.1", "createdAt": "2024-01-15T00:00:00Z", "changelog": "优化了匹配算法"},
    {"version": "1.0.2", "createdAt": "2024-01-20T00:00:00Z", "changelog": "修复了bug", "isCurrent": true}
  ]
}

// POST /api/templates/{merchantId}/{category}/{name}/rollback - 回滚到指定版本
Request:
{
  "targetVersion": "1.0.1"
}

Response:
{
  "success": true,
  "message": "已回滚到 v1.0.1",
  "newVersion": "1.0.1"
}
```

#### 6.8.5 模板本地缓存

```
~/.xstreaming/
├── templates/
│   ├── common/
│   │   ├── main_menu.png
│   │   └── main_menu.json      # 包含版本号
│   ├── game_a/
│   │   └── login_screen.png
│   └── templates_version.json   # 本地所有模板版本清单
└── config.yaml
```

### 6.9 游戏账号切换机制

#### 6.9.1 游戏账号优先级

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        游戏账号优先级机制                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【优先级设置】                                                              │
│                                                                             │
│  - 游戏账号有 priority 字段（INT 类型，默认0）                              │
│  - 数字越小优先级越高                                                        │
│  - priority = 0 表示不设置优先级，按列表顺序执行                            │
│                                                                             │
│  【执行顺序规则】                                                            │
│                                                                             │
│  1. 有设置优先级的账号:                                                      │
│     - 按 priority 从小到大排序                                                │
│     - priority 相同则按创建时间排序                                          │
│                                                                             │
│  2. 未设置优先级的账号（priority = 0）:                                     │
│     - 按列表顺序（created_at）执行                                          │
│     - 排在设置优先级的账号之后                                               │
│                                                                             │
│  【示例】                                                                    │
│                                                                             │
│  游戏账号列表:                                                               │
│  | 账号名 | Priority | 说明 |                                              │
│  |------|---------|----------------------------------------------|          │
│  | 账号A | 1 | 最高优先级 |                                              │
│  | 账号B | 2 | 第二优先级 |                                              │
│  | 账号C | 0 | 未设置，按列表顺序 |                                        │
│  | 账号D | 0 | 未设置，按列表顺序 |                                        │
│  | 账号E | 5 | 最低优先级 |                                              │
│                                                                             │
│  执行顺序: 账号A → 账号B → 账号C → 账号D → 账号E                           │
│                                                                             │
│  【设置优先级】                                                              │
│                                                                             │
│  商户可在游戏账号管理页面设置优先级:                                         │
│  - 拖拽排序                                                                 │
│  - 或手动输入优先级数字                                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**优先级设置 API：**

```json
// PUT /api/game/{id}/priority - 设置单个账号优先级
Request:
{
  "priority": 1
}

// PUT /api/game/batch-priority - 批量设置优先级
Request:
{
  "priorities": [
    {"gameAccountId": 1, "priority": 1},
    {"gameAccountId": 2, "priority": 2},
    {"gameAccountId": 3, "priority": 0},
    {"gameAccountId": 4, "priority": 0}
  ]
}

// GET /api/streaming/{id}/game-accounts?sort=priority - 获取按优先级排序的游戏账号
```

#### 6.9.2 游戏账号切换规则

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        游戏账号切换机制                                       │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【在同一个 Xbox 上切换】                                                  │
│                                                                             │
│  - 不需要解绑                                                               │
│  - 直接在 Xbox 上切换游戏账号                                                │
│  - 适用于：主账号登录后，切换到副账号                                        │
│                                                                             │
│  【在不同 Xbox 上登录相同游戏账号】                                          │
│                                                                             │
│  - Xbox 会提示："该游戏账号已在其他Xbox登录，是否解绑？"                     │
│  - 选择"是" → 自动解绑其他 Xbox 上的该游戏账号                               │
│  - 选择"否" → 保持原有绑定                                                  │
│                                                                             │
│  【游戏账号锁定规则】                                                        │
│                                                                             │
│  - 同一时间，一个游戏账号只能在一台 Xbox 上登录                              │
│  - 锁定基于 game_account.id，而非 Xbox                                      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.9.2 游戏账号冲突处理

```
场景: 游戏账号 "主账号A" 已在 Xbox-1 上登录，现在要在 Xbox-2 上登录

Xbox-2 界面提示:
┌─────────────────────────────────────────────────────────────────────────────┐
│                         ⚠️ 游戏账号冲突                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│     该游戏账号已在 Xbox-1 (192.168.1.50) 上登录                            │
│                                                                             │
│     [解绑并登录]  [取消]                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

选择"解绑并登录":
    → Xbox-1 上的 game_account 解锁
    → Xbox-2 上的 game_account 锁定
```

### 6.10 暂停恢复机制

#### 6.10.1 暂停类型

| 类型         | 触发      | Xbox 状态 | 游戏账号次数 | 恢复方式  |
| ---------- | ------- | ------- | ------ | ----- |
| **比赛中暂停**  | 比赛过程中暂停 | 不释放     | 不计数    | 从断点继续 |
| **比赛结束暂停** | 比赛完成后暂停 | 需检查     | 已统计    | 重新开始  |

#### 6.10.2 暂停恢复流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        暂停恢复流程                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【比赛中暂停】                                                            │
│                                                                             │
│  1. 商户点击"暂停"                                                          │
│  2. Agent 发送暂停指令到 Xbox                                               │
│  3. Xbox 游戏暂停，但保持连接                                               │
│  4. Xbox 状态: streaming (暂停中)                                          │
│  5. 游戏账号今日次数: 不变                                                  │
│  6. 商户点击"恢复"                                                          │
│  7. Agent 发送恢复指令                                                      │
│  8. 游戏从断点继续                                                          │
│                                                                             │
│  【比赛结束暂停】                                                          │
│                                                                             │
│  1. 比赛完成                                                                │
│  2. Agent 上报比赛结果 → 今日次数 +1                                       │
│  3. 检查该串流账号下所有游戏账号:                                           │
│     - 是否都已完成今日最大比赛次数？                                         │
│     │                                                                      │
│     ├── 全部完成 → Xbox 状态变为 idle，释放Xbox                           │
│     │                                                                      │
│     └── 未全部完成 → Xbox 状态保持 streaming，等待下一个游戏账号            │
│                                                                             │
│  【检查逻辑伪代码】                                                        │
│                                                                             │
│  for each game_account in streaming_account.game_accounts:                │
│      if game_account.completed_today < game_account.daily_max_matches:     │
│          return "CONTINUE"  // 还有游戏账号没打完                           │
│  return "RELEASE"  // 所有游戏账号都打完了，释放Xbox                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 6.11 视频流方案

#### 6.11.1 视频流架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        视频流方案                                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【视频流传输】                                                            │
│                                                                             │
│  - 加密: 使用 TLS/WSS 加密传输                                             │
│  - 协议: MJPEG over WebSocket                                              │
│  - 延迟: ~100-200ms                                                        │
│                                                                             │
│  【实时观看】                                                              │
│                                                                             │
│  - 商户可通过管理平台实时观看视频流                                         │
│  - 不存储录像，仅实时观看                                                  │
│                                                                             │
│  【无本地存储】                                                            │
│                                                                             │
│  - 不在 Agent 本地存储录像                                                 │
│  - 节省硬盘空间                                                             │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.11.2 视频流 API

```json
// GET /api/streaming/{id}/live - 获取实时视频流
Response:
{
  "streamUrl": "wss://api.xstreaming.com/live/{streamingId}",
  "encryption": "tls"
}
```

### 6.12 串流账号与 Xbox 绑定方案

#### 6.12.1 绑定关系

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        串流账号与 Xbox 绑定                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【绑定方式】支持手动选择和自动分配                                        │
│                                                                             │
│  方式1: 商户手动选择 Xbox                                                  │
│  - 商户在串流账号管理页面选择 Xbox                                         │
│  - 点击绑定到指定的 Xbox                                                    │
│                                                                             │
│  方式2: 系统自动分配                                                        │
│  - 商户点击"自动分配"                                                      │
│  - 系统自动分配到空闲的 Xbox                                                │
│                                                                             │
│  【绑定基础】                                                              │
│                                                                             │
│  - 绑定基于 Xbox MAC 地址（唯一标识）                                       │
│  - IP 地址可能变化，不作为绑定依据                                          │
│                                                                             │
│  【绑定流程】                                                              │
│                                                                             │
│  1. Agent 启动时自动发现 Xbox（通过 MAC 识别）                              │
│  2. Agent 上报 Xbox 信息到管理平台                                         │
│  3. 商户选择串流账号                                                       │
│     - 方式A: 手动选择 Xbox → 绑定到指定的 Xbox                              │
│     - 方式B: 点击"自动分配" → 系统分配到空闲 Xbox                           │
│  4. 串流账号的 xbox_host_id 关联到 Xbox                                    │
│                                                                             │
│  【Xbox 变化处理】                                                        │
│                                                                             │
│  - 新增 Xbox → Agent 自动发现，上报，标记为"待分配"                        │
│  - Xbox 离线 → 自动解绑串流账号，Xbox 标记为"离线"                          │
│  - Xbox IP 变化 → MAC 不变，自动更新 IP                                     │
│                                                                             │
│  【永久绑定 vs 临时绑定】                                                  │
│                                                                             │
│  - 串流账号通常是主账号，提前登录到 Xbox                                    │
│  - 绑定关系相对固定，但可手动解绑重新分配                                   │
│  - 支持临时解绑（如 Xbox 维护时）                                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

#### 6.12.4 Xbox 临时解绑机制

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Xbox 临时解绑机制                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【临时解绑场景】                                                            │
│                                                                             │
│  - Xbox 需要维护或检修                                                       │
│  - Xbox 网络调整                                                             │
│  - 临时借用 Xbox 给其他用途                                                  │
│                                                                             │
│  【临时解绑流程】                                                            │
│                                                                             │
│  1. 商户点击"临时解绑"                                                      │
│  2. 选择解绑原因（维护/网络调整/其他）                                       │
│  3. 选择解绑时长（1小时/4小时/8小时/24小时/自定义）                         │
│  4. 确认临时解绑                                                            │
│  5. 串流账号与 Xbox 解绑                                                    │
│  6. Xbox 状态标记为"维护中"                                                │
│  7. 到达解绑时长后，自动恢复绑定                                            │
│                                                                             │
│  【临时解绑 vs 永久解绑】                                                   │
│                                                                             │
│  | 类型 | 操作 | Xbox 状态 | 到期后 |                                      │
│  |------|------|-------------|----------------------------------------------|  │
│  | 临时解绑 | 商户主动 | 标记为"维护中" | 自动恢复绑定 |                    │
│  | 永久解绑 | 商户主动 | 变为"idle" | 需要重新绑定 |                        │
│  | Xbox离线 | 系统自动 | 变为"offline" | 保持解绑状态 |                    │
│                                                                             │
│  【自动恢复绑定】                                                            │
│                                                                             │
│  - 到达解绑时长后，系统自动恢复绑定                                          │
│  - 如果 Xbox 仍在线，重新绑定到原串流账号                                   │
│  - 如果 Xbox 离线，保持解绑状态，等 Xbox 恢复后重新绑定                       │
│  - 自动恢复记录到操作日志                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**临时解绑 API：**

```json
// POST /api/streaming/{id}/temporary-unbind - 临时解绑
Request:
{
  "reason": "maintenance",  // maintenance / network / other
  "durationHours": 4       // 解绑时长（小时）
}

// Response
{
  "success": true,
  "message": "已临时解绑，将于 4 小时后自动恢复",
  "restoreAt": "2024-01-15T14:30:00Z"
}

// POST /api/streaming/{id}/cancel-temporary-unbind - 取消临时解绑，恢复绑定
Response:
{
  "success": true,
  "message": "已取消临时解绑，Xbox 已恢复绑定"
}

// GET /api/streaming/{id}/unbind-status - 查看解绑状态
Response:
{
  "streamingAccountId": 1,
  "unbindType": "temporary",  // none / temporary / permanent / offline
  "unbindedAt": "2024-01-15T10:30:00Z",
  "restoreAt": "2024-01-15T14:30:00Z",
  "reason": "maintenance"
}
```

#### 6.12.2 Xbox 表结构（补充 MAC）

```sql
-- Xbox 主机表
CREATE TABLE xbox_host (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    agent_id BIGINT NOT NULL,
    mac_address VARCHAR(17) NOT NULL UNIQUE COMMENT 'MAC地址（唯一标识）',
    ip_address VARCHAR(45) COMMENT '当前IP地址（可能变化）',
    name VARCHAR(100) COMMENT 'Xbox名称',
    status ENUM('idle', 'online', 'streaming', 'error', 'offline', 'maintenance') DEFAULT 'idle' COMMENT '状态（idle=空闲, online=在线, streaming=串流中, error=异常, offline=离线, maintenance=维护中）',
    temporary_unbind_at DATETIME COMMENT '临时解绑时间',
    temporary_unbind_restore_at DATETIME COMMENT '临时解绑恢复时间',
    temporary_unbind_reason VARCHAR(50) COMMENT '临时解绑原因',
    last_seen_at DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_mac_address (mac_address),
    INDEX idx_agent_id (agent_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

#### 6.12.3 绑定 API

```json
// POST /api/streaming/{id}/bind - 手动绑定到指定 Xbox
Request:
{
  "xboxHostId": 1
}

Response:
{
  "success": true,
  "xboxHost": {
    "id": 1,
    "name": "Xbox-1",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "status": "idle"
  }
}

// POST /api/streaming/{id}/auto-bind - 自动分配到空闲 Xbox
Response:
{
  "success": true,
  "xboxHost": {
    "id": 1,
    "name": "Xbox-1",
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "status": "idle"
  }
}

// POST /api/streaming/{id}/unbind - 解绑
Response:
{
  "success": true,
  "message": "已解绑"
}

// GET /api/streaming/{id}/bind-status - 查看绑定状态
Response:
{
  "streamingAccountId": 1,
  "bound": true,
  "xboxHost": {
    "id": 1,
    "macAddress": "AA:BB:CC:DD:EE:FF",
    "name": "Xbox-1",
    "agentName": "电脑A",
    "status": "streaming"
  }
}
```

***

## 6.x 登录自动化补充

### 6.x.1 登录流程状态机

#### 状态定义

```python
class LoginState(Enum):
    IDLE = "idle"                    # 初始状态
    WAIT_AUTH = "wait_auth"         # 等待 auth window 打开
    INPUT_EMAIL = "input_email"      # 输入邮箱阶段
    INPUT_PASSWORD = "input_password"  # 输入密码阶段
    WAIT_HOME = "wait_home"          # 等待登录完成到家主页
    SUCCESS = "success"              # 登录成功
    FAILED = "failed"                # 登录失败
```

#### 状态转换图

```
┌─────────┐
│  IDLE   │
└────┬────┘
     │ start_login()
     ▼
┌─────────────┐
│  WAIT_AUTH  │◄─────────────┐
└──────┬──────┘              │
       │ auth_window_opened │ retry
       ▼                    │
┌─────────────┐              │
│ INPUT_EMAIL │              │
└──────┬──────┘              │
       │ email_entered       │
       ▼                    │
┌─────────────────┐          │
│ INPUT_PASSWORD  │──────────┘ retry
└──────┬──────────┘
       │ password_entered
       ▼
┌─────────────┐
│  WAIT_HOME  │
└──────┬──────┘
       │ home_page_detected
       ▼
┌─────────┐
│ SUCCESS │
└─────────┘

任何关键步骤失败 ───────────► FAILED
```

#### 状态转换条件

| 当前状态            | 事件                       | 下一状态            | 动作     |
| --------------- | ------------------------ | --------------- | ------ |
| IDLE            | start\_login()           | WAIT\_AUTH      | 启动登录流程 |
| WAIT\_AUTH      | auth\_window\_opened     | INPUT\_EMAIL    | 进入邮箱输入 |
| WAIT\_AUTH      | timeout + retry\_fail    | FAILED          | 终止流程   |
| INPUT\_EMAIL    | email\_submitted         | INPUT\_PASSWORD | 进入密码输入 |
| INPUT\_EMAIL    | timeout/retry\_exhausted | FAILED          | 终止流程   |
| INPUT\_PASSWORD | password\_submitted      | WAIT\_HOME      | 进入等待主页 |
| INPUT\_PASSWORD | timeout/retry\_exhausted | FAILED          | 终止流程   |
| WAIT\_HOME      | home\_detected           | SUCCESS         | 登录完成   |
| WAIT\_HOME      | timeout                  | FAILED          | 终止流程   |
| \*              | critical\_error          | FAILED          | 终止流程   |

***

### 6.x.2 错误处理与重试机制

#### auth window 等待超时配置

| 参数     | 原值  | 新值  | 说明                 |
| ------ | --- | --- | ------------------ |
| 首次等待超时 | 15s | 30s | auth window 最大等待时间 |
| 重试等待时间 | -   | 5s  | 首次超时后额外等待          |
| 重试超时   | -   | 20s | 重试时的超时时间           |
| 最大重试次数 | -   | 1   | 最大重试次数             |

#### 关键步骤失败终止机制

以下关键步骤失败时，登录流程必须终止，而不是继续执行：

| 步骤             | 失败后果   | 处理方式         |
| -------------- | ------ | ------------ |
| auth window 等待 | 后续全部失败 | 超时后重试，仍失败则终止 |
| 账户输入框检测        | 无法输入账号 | 重试3次，仍失败则终止  |
| 密码输入框检测        | 无法输入密码 | 重试3次，仍失败则终止  |
| JS 注入 + 模板匹配   | 无法操作元素 | 备用方案失败则终止    |

#### 重试机制参数配置

```python
class LoginRetryConfig:
    AUTH_WINDOW_FIRST_TIMEOUT = 30    # auth window 首次等待30s
    AUTH_WINDOW_RETRY_WAIT = 5         # 首次超时后等待5s
    AUTH_WINDOW_RETRY_TIMEOUT = 20    # 重试时等待20s
    AUTH_WINDOW_MAX_RETRIES = 1        # 最大重试1次

    TEMPLATE_WAIT_TIMEOUT = 30         # 模板等待超时30s
    TEMPLATE_MAX_RETRIES = 3           # 最大重试3次

    JS_OPERATION_TIMEOUT = 5           # JS 操作超时5s
    HYBRID_CLICK_TIMEOUT = 10          # 混合点击超时10s
```

***

### 6.x.3 关键代码示例

#### auth window 等待逻辑（带重试）

```python
def _wait_auth_window_with_retry(self) -> bool:
    logger.info("等待 Microsoft 登录弹框...")
    if self._electron.wait_for_auth_window(timeout=30):
        logger.info("Microsoft 登录弹框已打开，等待页面加载...")
        time.sleep(3)
        return True

    logger.warning("等待 auth window 超时，尝试重新等待...")
    time.sleep(5)
    if self._electron.wait_for_auth_window(timeout=20):
        logger.info("重试成功，auth window 已打开")
        time.sleep(3)
        return True

    logger.error("等待 auth window 失败，终止登录流程")
    self.terminate("auth window 打开失败")
    return False
```

#### JS 注入 + 模板匹配备用方案

```python
def _js_set_input_with_fallback(self, selector: str, value: str, template_name: str) -> bool:
    logger.info(f"[JS注入] 设置值: {selector} = {value}")
    if self._js_set_input(selector, value):
        return True

    logger.warning("JS 设置失败，尝试点击输入框后重试...")
    if not self._hybrid_click(selector, template_name):
        logger.error("无法点击目标元素，终止操作")
        self.terminate(f"无法操作 {template_name}")
        return False

    time.sleep(0.5)
    if self._js_set_input(selector, value):
        return True

    logger.error("JS 设置失败，终止操作")
    self.terminate(f"无法设置 {selector}")
    return False


def _js_click_with_fallback(self, selector: str, template_name: str) -> bool:
    logger.info(f"[JS注入] 点击: {selector}")
    if self._js_click(selector):
        return True

    logger.warning("JS 点击失败，使用模板匹配...")
    if self._hybrid_click(selector, template_name):
        return True

    logger.error("点击失败，终止操作")
    self.terminate(f"无法点击 {template_name}")
    return False
```

#### 账户输入框等待与操作

```python
def _input_email_with_retry(self) -> bool:
    logger.info("等待账户输入框模板...")

    if not self._wait_for_template("login_user_account", timeout=30, retry_count=3):
        logger.error("未找到账户输入框，终止登录流程")
        self.terminate("账户输入框未出现")
        return False

    email = self.account.get('email', '')
    logger.info(f"[JS注入] 设置账户: {email}")

    if not self._js_set_input_with_fallback(self.MS_ACCOUNT_INPUT, email, "login_user_account"):
        return False

    logger.info("[JS注入] 点击下一步...")
    return self._js_click_with_fallback(self.MS_NEXT_BUTTON, "login_next_button")
```

#### 密码输入框等待与操作

```python
def _input_password_with_retry(self) -> bool:
    logger.info("等待密码输入框...")

    if not self._wait_for_template("login_password", timeout=30, retry_count=3):
        logger.error("未找到密码输入框，终止登录流程")
        self.terminate("密码输入框未出现")
        return False

    password = self.account.get('password', '')
    logger.info("[JS注入] 设置密码...")

    if not self._js_set_input_with_fallback(self.MS_PASSWORD_INPUT, password, "login_password"):
        return False

    time.sleep(1)

    logger.info("[JS注入] 点击登录...")
    return self._js_click_with_fallback(self.MS_SIGNIN_BUTTON, "login_account_button")
```

#### 登录结果验证

```python
def _verify_login_result(self) -> bool:
    logger.info("验证登录结果...")

    if self._wait_for_template("login_home", timeout=30, fail_on_timeout=False):
        logger.info("检测到登录完成标志，登录成功")
        return True

    if self._wait_for_template("login_error", timeout=5, fail_on_timeout=False):
        logger.error("检测到登录错误标志")
        return False

    logger.error("[登录结果] 未检测到登录完成标志，登录可能失败")
    return False
```

#### 完整登录流程调用

```python
def _do_login(self) -> bool:
    if not self._wait_auth_window_with_retry():
        return False

    if not self._input_email_with_retry():
        return False

    if not self._input_password_with_retry():
        return False

    if not self._wait_for_template("login_home", timeout=60, fail_on_timeout=False):
        logger.error("等待主页超时，登录可能失败")
        self.terminate("登录超时")
        return False

    logger.info("登录流程完成")
    return True
```

***

### 6.x.4 修复要点总结

| 问题                     | 根因                              | 修复方案                     |
| ---------------------- | ------------------------------- | ------------------------ |
| 等待 auth window 超时后继续执行 | timeout=15s 太短，超时后直接继续          | 增加超时到30s，超时后重试20s，仍失败则终止 |
| 关键步骤失败后继续执行            | 使用 fail\_on\_timeout=False 忽略超时 | 关键步骤超时时重试3次，仍失败则明确终止     |
| JS 注入失败后未确保操作成功        | 备用方案失败也继续                       | 备用方案必须同步成功才能继续，否则终止      |
| 登录结果判断不准确              | 未检测到完成标志时返回 True                | 未检测到完成标志时返回 False        |

### 6.x.5 与原有流程对比

| 项目             | 修复前                     | 修复后                      |
| -------------- | ----------------------- | ------------------------ |
| auth window 等待 | 15s 超时后继续               | 30s + 5s等待 + 20s重试，仍失败终止 |
| 账户输入框检测        | fail\_on\_timeout=False | 重试3次，仍失败终止               |
| 密码输入框检测        | fail\_on\_timeout=False | 重试3次，仍失败终止               |
| JS 操作失败处理      | 备用方案可选                  | 备用方案必须成功，否则终止            |
| 登录结果判断         | 未检测到也返回 True            | 未检测到返回 False             |

***

## 八、错误码规范

### 8.1 错误码结构

```
错误码格式: ERR_{MODULE}_{CODE}
示例: ERR_AUTH_001, ERR_AGENT_002

结构:
├── ERR: 前缀
├── MODULE: 模块名（4位）
└── CODE: 错误码（3位数字）
```

### 7.2 错误码分类

| 模块        | 前缀              | 说明      |
| --------- | --------------- | ------- |
| AUTH      | ERR\_AUTH\_\*   | 认证模块    |
| AGENT     | ERR\_AGENT\_\*  | Agent管理 |
| STREAMING | ERR\_STREAM\_\* | 串流账号    |
| GAME      | ERR\_GAME\_\*   | 游戏账号    |
| XBOX      | ERR\_XBOX\_\*   | Xbox主机  |
| TEMPLATE  | ERR\_TPL\_\*    | 模板管理    |
| MERCHANT  | ERR\_MCHT\_\*   | 商户管理    |
| SYSTEM    | ERR\_SYS\_\*    | 系统错误    |

### 8.3 错误码详细定义

```json
{
  "ERR_AUTH_001": {"message": "邀请码无效或已过期", "httpStatus": 400},
  "ERR_AUTH_002": {"message": "激活码无效或已使用", "httpStatus": 400},
  "ERR_AUTH_003": {"message": "手机号或密码错误", "httpStatus": 401},
  "ERR_AUTH_004": {"message": "账号已过期，请续费", "httpStatus": 403},
  "ERR_AUTH_005": {"message": "短信验证码错误或已过期", "httpStatus": 400},
  "ERR_AUTH_006": {"message": "新密码不能与旧密码相同", "httpStatus": 400},

  "ERR_AGENT_001": {"message": "安装码无效或已过期", "httpStatus": 400},
  "ERR_AGENT_002": {"message": "安装码已被使用", "httpStatus": 400},
  "ERR_AGENT_003": {"message": "Agent不在线", "httpStatus": 503},
  "ERR_AGENT_004": {"message": "Agent心跳超时", "httpStatus": 503},

  "ERR_STREAM_001": {"message": "串流账号不存在", "httpStatus": 404},
  "ERR_STREAM_002": {"message": "串流账号未绑定Xbox", "httpStatus": 400},
  "ERR_STREAM_003": {"message": "Xbox已被其他串流账号占用", "httpStatus": 409},
  "ERR_STREAM_004": {"message": "今日游戏账号已完成最大比赛次数", "httpStatus": 400},
  "ERR_STREAM_005": {"message": "无可用Xbox主机", "httpStatus": 503},

  "ERR_GAME_001": {"message": "游戏账号不存在", "httpStatus": 404},
  "ERR_GAME_002": {"message": "游戏账号已在其他串流账号下使用", "httpStatus": 409},
  "ERR_GAME_003": {"message": "游戏账号邮箱已被使用", "httpStatus": 409},

  "ERR_XBOX_001": {"message": "Xbox主机不存在", "httpStatus": 404},
  "ERR_XBOX_002": {"message": "Xbox主机不在线", "httpStatus": 503},
  "ERR_XBOX_003": {"message": "Xbox主机离线", "httpStatus": 503},

  "ERR_TPL_001": {"message": "模板不存在", "httpStatus": 404},
  "ERR_TPL_002": {"message": "模板版本不存在", "httpStatus": 404},

  "ERR_MCHT_001": {"message": "商户不存在", "httpStatus": 404},
  "ERR_MCHT_002": {"message": "商户账号已过期", "httpStatus": 403},

  "ERR_SYS_001": {"message": "系统内部错误", "httpStatus": 500},
  "ERR_SYS_002": {"message": "数据库连接失败", "httpStatus": 503},
  "ERR_SYS_003": {"message": "Redis连接失败", "httpStatus": 503}
}
```

***

## 九、日志规范

### 8.1 日志级别

| 级别    | 使用场景            |
| ----- | --------------- |
| ERROR | 错误日志：异常、失败、崩溃   |
| WARN  | 警告日志：重试、超时、异常恢复 |
| INFO  | 信息日志：登录、登出、关键操作 |
| DEBUG | 调试日志：详细流程、参数    |

### 9.2 日志格式

```json
{
  "timestamp": "2024-01-15T10:30:00.000Z",
  "level": "INFO",
  "module": "AUTH",
  "traceId": "uuid-xxx-xxx",
  "merchantId": 1,
  "agentId": "agent-001",
  "message": "商户登录成功",
  "data": {
    "phone": "138****8000",
    "ip": "192.168.1.100"
  }
}
```

### 8.3 关键日志记录

| 操作      | 级别    | 必须包含字段                                        |
| ------- | ----- | --------------------------------------------- |
| 商户登录    | INFO  | merchantId, phone, ip                         |
| 商户激活    | INFO  | merchantId, inviteCode                        |
| 续费      | INFO  | merchantId, activationCode                    |
| Agent注册 | INFO  | agentId, merchantId                           |
| Agent心跳 | DEBUG | agentId, status                               |
| 启动自动化   | INFO  | streamingAccountId, xboxHostId, agentId       |
| 停止自动化   | INFO  | streamingAccountId, reason                    |
| 比赛完成    | INFO  | streamingAccountId, gameAccountId, matchCount |
| 错误/异常   | ERROR | errorCode, stackTrace                         |

### 9.4 Agent 日志上报

```json
// POST /api/agent/logs - Agent 日志上报
Request:
{
  "agentId": "agent-001",
  "logs": [
    {"timestamp": "...", "level": "INFO", "message": "Agent启动"},
    {"timestamp": "...", "level": "DEBUG", "message": "扫描Xbox..."},
    {"timestamp": "...", "level": "ERROR", "message": "Xbox连接失败", "error": "..."}
  ]
}
```

***

## 十、监控告警机制

### 10.1 告警类型

| 类型       | 触发条件         | 告警方式  | 严重程度 |
| -------- | ------------ | ----- | ---- |
| Agent离线  | 心跳超时120秒     | 邮件/短信 | 高    |
| Xbox离线   | 检测不到Xbox     | 邮件    | 中    |
| 商户账号过期   | expire\_time | 邮件    | 高    |
| 游戏账号次数异常 | 完成次数>限制      | 邮件    | 中    |
| 系统错误     | 500错误率>1%    | 短信    | 紧急   |
| 视频流中断    | 断流>30秒       | 邮件    | 中    |

### 9.2 告警流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           告警流程                                          │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. 系统监控检测到异常                                                    │
│         │                                                                   │
│         ▼                                                                   │
│  2. 判断告警类型和严重程度                                                │
│         │                                                                   │
│         ├── 紧急 → 短信 + 邮件 + 电话                                    │
│         ├── 高 → 邮件 + 短信                                              │
│         └── 中 → 邮件                                                      │
│                                                                             │
│  3. 发送告警通知                                                          │
│         │                                                                   │
│         ▼                                                                   │
│  4. 记录告警日志                                                          │
│         │                                                                   │
│         ▼                                                                   │
│  5. 等待确认或自动处理                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 9.3 告警 API

```json
// POST /api/alerts - 内部告警记录
Request:
{
  "type": "AGENT_OFFLINE",
  "severity": "HIGH",
  "targetId": "agent-001",
  "merchantId": 1,
  "message": "Agent agent-001 心跳超时",
  "timestamp": "2024-01-15T10:30:00Z"
}

// GET /api/alerts?merchantId=1&status=pending - 获取告警列表
Response:
{
  "alerts": [
    {
      "id": 1,
      "type": "AGENT_OFFLINE",
      "severity": "HIGH",
      "message": "Agent agent-001 心跳超时",
      "status": "pending",
      "createdAt": "2024-01-15T10:30:00Z"
    }
  ]
}

// POST /api/alerts/{id}/acknowledge - 确认告警
```

### 10.4 监控指标

| 指标       | 说明               | 阈值         |
| -------- | ---------------- | ---------- |
| Agent在线率 | 在线Agent数/总Agent数 | < 80% 告警   |
| Xbox利用率  | 使用中Xbox/总Xbox    | > 95% 告警   |
| API响应时间  | 平均响应时间           | > 500ms 告警 |
| 错误率      | 错误请求/总请求         | > 1% 告警    |
| 心跳超时数    | 心跳超时的Agent数      | > 0 告警     |

***

## 十二、完整项目结构

### 7.1 Java 后端

```
xstreaming-manager/
├── src/main/java/com/xstreaming/manager/
│   ├── XStreamingManagerApplication.java
│   │
│   ├── config/
│   │   ├── WebSocketConfig.java
│   │   ├── CorsConfig.java
│   │   └── SecurityConfig.java
│   │
│   ├── controller/
│   │   ├── StreamingAccountController.java
│   │   ├── GameAccountController.java
│   │   ├── AgentController.java
│   │   └── TaskController.java
│   │
│   ├── service/
│   │   ├── StreamingAccountService.java
│   │   ├── GameAccountService.java
│   │   ├── AgentService.java
│   │   ├── TaskService.java
│   │   └── impl/
│   │
│   ├── entity/
│   │   ├── StreamingAccount.java
│   │   ├── GameAccount.java
│   │   ├── AgentInstance.java
│   │   ├── AutomationTask.java
│   │   └── TaskStatistics.java
│   │
│   ├── repository/
│   │   ├── StreamingAccountRepository.java
│   │   ├── GameAccountRepository.java
│   │   ├── AgentRepository.java
│   │   └── TaskRepository.java
│   │
│   ├── dto/
│   │   ├── StreamingAccountDTO.java
│   │   ├── GameAccountDTO.java
│   │   ├── StartAutomationRequest.java
│   │   └── TaskDTO.java
│   │
│   ├── websocket/
│   │   └── StatusWebSocketHandler.java
│   │
│   └── util/
│       └── EncryptionUtil.java
│
├── src/main/resources/
│   ├── application.yml
│   └── schema.sql
│
└── pom.xml
```

### 7.1.1 application.yml 配置示例

```yaml
# Spring Boot 配置文件
spring:
  application:
    name: xstreaming-manager

  # MySQL 数据库配置
  datasource:
    url: jdbc:mysql://localhost:3306/xstreaming_manager?useUnicode=true&characterEncoding=utf8&useSSL=false&serverTimezone=${APP_TIMEZONE:Asia/Shanghai}&allowPublicKeyRetrieval=true
    username: xstreaming_app
    password: ${DB_PASSWORD:XStr3@m$2024!DB#Sec}
    driver-class-name: com.mysql.cj.jdbc.Driver
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5
      idle-timeout: 300000
      connection-timeout: 20000
      max-lifetime: 1200000

  # Redis 配置
  redis:
    host: ${REDIS_HOST:localhost}
    port: ${REDIS_PORT:6379}
    password: ${REDIS_PASSWORD:}
    database: 0
    timeout: 5000ms
    lettuce:
      pool:
        max-active: 20
        max-idle: 10
        min-idle: 5

  # JWT 配置
  jwt:
    secret: ${JWT_SECRET:}  # 必须设置至少256位的密钥
    expiration: 86400000  # 24小时

  # 文件上传配置
  servlet:
    multipart:
      max-file-size: 10MB
      max-request-size: 10MB

server:
  port: ${SERVER_PORT:8080}
  servlet:
    context-path: /api

# 日志配置
logging:
  level:
    root: INFO
    com.xstreaming: DEBUG
  pattern:
    console: "%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level %logger{36} - %msg%n"

# 自定义配置
xstreaming:
  # 激活码配置
  activation-code:
    format: "XXXX-XXXX-XXXX"
    redis-prefix: "activation_code:"
    redis-ttl: 86400  # 24小时

  # Agent 配置
  agent:
    heartbeat-timeout: 120  # 秒，超过此时间未收到心跳视为离线
    max-retry: 3

  # 商户时区配置
  timezone:
    default: "Asia/Shanghai"
```

**⚠️ 安全提醒：**

- 数据库密码 `XStr3@m$2024!DB#Sec` 仅为示例，请根据实际情况修改
- 生产环境务必通过环境变量 `${DB_PASSWORD}` 注入密码，切勿将真实密码硬编码在配置文件中
- JWT Secret 必须使用至少256位的随机字符串
- Redis 密码根据实际情况决定是否设置（内网环境可省略）

### 7.2 Python Agent

```
agent/
├── main.py                    # Agent 主入口
├── config.py                  # 配置
├── api/
│   ├── __init__.py
│   ├── client.py              # 与后端通信
│   └── models.py             # 数据模型
│
├── automation/                # 自动化模块
│   ├── __init__.py
│   ├── login_service.py      # 登录服务
│   ├── stream_service.py     # 串流服务
│   └── game_switch_service.py # 游戏切换服务
│
├── core/
│   ├── electron_bridge.py
│   ├── video_capture.py      # 视频帧捕获
│   └── template_matcher.py  # 模板匹配
│
└── templates/               # 模板图片
```

### 7.2.1 Python Agent 详细代码结构

```python
# main.py - Agent 主入口
import asyncio
import logging
from api.client import BackendClient
from core.central_manager import CentralManager
from automation.login_service import LoginService
from automation.stream_service import StreamService
from automation.account_switch_service import AccountSwitchService

logger = logging.getLogger(__name__)

class Agent:
    def __init__(self, config: dict):
        self.config = config
        self.backend_url = config['backend_url']
        self.agent_id = config['agent_id']
        
        # 初始化客户端
        self.client = BackendClient(self.backend_url)
        
        # 初始化管理器
        self.central_manager = CentralManager()
        
        # 初始化服务
        self.login_service = LoginService(self.central_manager)
        self.stream_service = StreamService(self.central_manager)
        self.account_switch_service = AccountSwitchService(self.stream_service)
        
        # WebSocket 连接
        self.ws = None
        
    async def start(self):
        """启动 Agent"""
        # 注册到后端
        await self.register()
        
        # 启动 WebSocket 监听
        await self.websocket_listener()
        
    async def register(self):
        """注册到后端"""
        response = await self.client.post('/api/agent/register', {
            'agentId': self.agent_id,
            'host': self.config['host'],
            'port': self.config['port'],
            'capacity': self.config['capacity']
        })
        logger.info(f"Agent 注册成功: {response}")
        
    async def websocket_listener(self):
        """WebSocket 消息监听"""
        async for message in self.client.websocket_connect():
            await self.handle_message(message)
            
    async def handle_message(self, message: dict):
        """处理 WebSocket 消息"""
        msg_type = message.get('type')
        
        if msg_type == 'task.assigned':
            await self.handle_task_assigned(message['data'])
        elif msg_type == 'task.cancelled':
            await self.handle_task_cancelled(message['data'])
        elif msg_type == 'admin.notify':
            await self.handle_admin_notify(message['data'])
            
    async def handle_task_assigned(self, data: dict):
        """处理任务下发"""
        task_id = data['task_id']
        action = data['action']
        
        logger.info(f"收到任务: {task_id}, action: {action}")
        
        if action == 'start_stream':
            # 启动串流
            instance = await self.central_manager.create_instance(
                task_id=task_id,
                streaming_account=data['streaming_account'],
                game_account=data.get('game_account'),
                config=data.get('automation_config', {})
            )
            await instance.start()
            
        elif action == 'stop':
            # 停止任务
            instance = self.central_manager.get_instance(task_id)
            if instance:
                await instance.stop()
                
        elif action == 'switch_account':
            # 切换账号
            await self.account_switch_service.switch_to_account(
                data['game_account']
            )
            
    async def report_status(self, task_id: int, status: dict):
        """上报状态到后端"""
        await self.client.post('/api/agent/status', {
            'taskId': task_id,
            **status
        })
        
    async def send_log(self, level: str, message: str, task_id: int = None):
        """发送日志到后端"""
        await self.client.websocket_send({
            'type': 'agent.log',
            'data': {
                'agentId': self.agent_id,
                'level': level,
                'message': message,
                'taskId': task_id,
                'timestamp': datetime.now().isoformat()
            }
        })
```

```python
# api/client.py - 与后端通信客户端
import asyncio
import websockets
import json
import aiohttp
from typing import AsyncIterator

class BackendClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.ws_url = base_url.replace('http', 'ws') + '/ws/agent'
        self.session = None
        self.ws = None
        
    async def ensure_session(self):
        """确保 HTTP session 存在"""
        if self.session is None:
            self.session = aiohttp.ClientSession()
            
    async def post(self, path: str, data: dict) -> dict:
        """POST 请求"""
        await self.ensure_session()
        url = f"{self.base_url}{path}"
        async with self.session.post(url, json=data) as response:
            return await response.json()
            
    async def get(self, path: str, params: dict = None) -> dict:
        """GET 请求"""
        await self.ensure_session()
        url = f"{self.base_url}{path}"
        async with self.session.get(url, params=params) as response:
            return await response.json()
            
    async def websocket_connect(self) -> AsyncIterator[dict]:
        """建立 WebSocket 连接并接收消息"""
        self.ws = await websockets.connect(self.ws_url)
        
        async for message in self.ws:
            data = json.loads(message)
            yield data
            
    async def websocket_send(self, data: dict):
        """通过 WebSocket 发送消息"""
        if self.ws:
            await self.ws.send(json.dumps(data))
```

```python
# core/central_manager.py - 中央管理器
class CentralManager:
    def __init__(self):
        self.instances = {}  # task_id -> StreamInstance
        
    async def create_instance(self, task_id: int, streaming_account: dict, 
                              game_account: dict, config: dict) -> 'StreamInstance':
        """创建串流实例"""
        instance = StreamInstance(
            task_id=task_id,
            streaming_account=streaming_account,
            game_account=game_account,
            config=config
        )
        self.instances[task_id] = instance
        return instance
        
    def get_instance(self, task_id: int) -> 'StreamInstance':
        """获取串流实例"""
        return self.instances.get(task_id)
        
    async def remove_instance(self, task_id: int):
        """移除串流实例"""
        if task_id in self.instances:
            await self.instances[task_id].cleanup()
            del self.instances[task_id]
```

```python
# automation/login_service.py - 登录服务
class LoginService:
    Status = Enum('Status', ['IDLE', 'WAITING_AUTH', 'AUTH_OPENED', 
                             'LOGGING_IN', 'SUBMITTED', 'SUCCESS', 'FAILED'])
    
    def __init__(self, central_manager: CentralManager):
        self.central_manager = central_manager
        self.status = self.Status.IDLE
        self.callbacks = {}
        
    def set_callbacks(self, on_status_change=None, on_error=None):
        """设置回调函数"""
        self.callbacks['on_status_change'] = on_status_change
        self.callbacks['on_error'] = on_error
        
    async def start(self, account: dict):
        """启动登录流程"""
        self.status = self.Status.WAITING_AUTH
        self._notify_status_change()
        
        # 通过 Electron Bridge 执行登录
        bridge = self.central_manager.get_electron_bridge()
        result = await bridge.direct_login(
            account['email'],
            account['password']
        )
        
        if result['success']:
            self.status = self.Status.SUCCESS
        else:
            self.status = self.Status.FAILED
            self.callbacks['on_error']?.(result['error'])
            
    async def run_loop(self):
        """登录循环 - 持续监控登录状态"""
        while True:
            if self.status == self.Status.SUCCESS:
                break
                
            if self.status == self.Status.FAILED:
                # 重试逻辑
                await self._retry()
                
            await asyncio.sleep(1)
```

```python
# automation/stream_service.py - 串流服务
class StreamService:
    Status = Enum('Status', ['IDLE', 'WAITING_CONSOLE', 'CONSOLE_READY',
                             'STARTING_STREAM', 'STREAMING', 'SUCCESS', 'FAILED'])
    
    def __init__(self, central_manager: CentralManager):
        self.central_manager = central_manager
        self.status = self.Status.IDLE
        self.xplayer = None
        
    async def start_stream(self, streaming_account: dict):
        """启动串流"""
        self.status = self.Status.WAITING_CONSOLE
        
        # 1. 等待 Xbox 控制台就绪
        await self._wait_for_console()
        
        # 2. 启动串流
        self.status = self.Status.STARTING_STREAM
        await self._try_start_stream()
        
    async def _wait_for_console(self) -> bool:
        """等待 Xbox 控制台就绪"""
        for _ in range(60):  # 最多等待 60 秒
            if await self._check_console_ready():
                self.status = self.Status.CONSOLE_READY
                return True
            await asyncio.sleep(1)
            
        self.status = self.Status.FAILED
        return False
        
    async def reconnect(self):
        """重连串流"""
        logger.info("尝试重连串流...")
        self.status = self.Status.WAITING_CONSOLE
        await self._wait_for_console()
        await self._try_start_stream()
```

```python
# automation/account_switch_service.py - 账号切换服务
class AccountSwitchService:
    def __init__(self, stream_service: StreamService):
        self.stream_service = stream_service
        self.current_account = None
        
    async def switch_to_account(self, target_account: dict):
        """切换到目标游戏账号"""
        logger.info(f"开始切换账号: {target_account['name']}")
        
        # 1. 确保在 Xbox 主界面
        await self._ensure_home_screen()
        
        # 2. 打开 Guide
        self.stream_service.xplayer.pressButton('Xbox')
        await asyncio.sleep(1)
        
        # 3. 导航到设置 -> 账号
        await self._navigate_to_account_management()
        
        # 4. 登出当前账号
        await self._sign_out_current()
        
        # 5. 使用目标账号登录
        await self._sign_in_with_account(target_account)
        
        # 6. 验证登录
        if await self._verify_login():
            self.current_account = target_account
            logger.info(f"账号切换成功: {target_account['name']}")
        else:
            raise AutomationError("账号切换验证失败")
```

### 7.2.2 Agent 配置文件

```yaml
# agent/config.yaml
agent:
  agent_id: "agent-${HOSTNAME}-${PORT}"
  host: "192.168.1.100"  # 本机 IP
  port: 9999

backend:
  url: "https://api.xstreaming.com"
  ws_url: "wss://api.xstreaming.com/ws/agent"
  heartbeat_interval: 30  # 秒
  reconnect_delay: 5  # 秒

automation:
  max_retry: 3
  template_timeout: 30
  stream_timeout: 60

xbox:
  # Xbox 配置（在安装时配置）
  hosts:
    - window_index: 0
      ip_address: "192.168.1.50"
      name: "Xbox-1"
      mac_address: "AA:BB:CC:DD:EE:FF"
    - window_index: 1
      ip_address: "192.168.1.51"
      name: "Xbox-2"
      mac_address: "11:22:33:44:55:66"

electron:
  app_path: "C:/path/to/XStreamingDesktop.exe"
  preload_path: "C:/path/to/preload.js"
```

### 7.2.3 Agent 安装脚本

```powershell
# install_agent.ps1 - Windows Agent 安装脚本
param(
    [string]$BackendUrl = "https://api.xstreaming.com",
    [switch]$AutoStart
)

$ErrorActionPreference = "Stop"

# 欢迎信息
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   XStreaming Agent 安装向导" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 检查 Python
if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "错误: Python 未安装" -ForegroundColor Red
    Write-Host "请先安装 Python 3.8 或更高版本" -ForegroundColor Yellow
    exit 1
}

# 获取本机信息
$localIp = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.InterfaceAlias -notlike "*Loopback*" } | Select-Object -First 1).IPAddress
$macAddress = (Get-NetAdapter | Where-Object { $_.Status -eq "Up" } | Select-Object -First 1).MacAddress

Write-Host "检测到本机信息:" -ForegroundColor Green
Write-Host "  IP 地址: $localIp"
Write-Host "  MAC 地址: $macAddress"
Write-Host ""

# 输入安装码
$installCode = ""
while ($installCode -notmatch "^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$") {
    $installCode = Read-Host "请输入安装码（格式：XXXX-XXXX-XXXX-XXXX）"
    if ($installCode -notmatch "^[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}-[A-Z0-9]{4}$") {
        Write-Host "安装码格式不正确，请重新输入" -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "正在验证安装码..." -ForegroundColor Cyan

# =============================================
# 配置 Xbox 信息
# =============================================
Write-Host "请配置该电脑上的 Xbox 数量:" -ForegroundColor Yellow
Write-Host ""

$xboxCount = 0
while ($xboxCount -lt 1 -or $xboxCount -gt 8) {
    $input = Read-Host "Xbox 数量 (1-8，默认4）"
    if ($input -eq "") { $xboxCount = 4 }
    else {
        $xboxCount = [int]$input
        if ($xboxCount -lt 1 -or $xboxCount -gt 8) {
            Write-Host "Xbox 数量必须在 1-8 之间" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "请配置每台 Xbox 的信息:" -ForegroundColor Yellow
Write-Host ""

$xboxConfigs = @()
for ($i = 0; $i -lt $xboxCount; $i++) {
    Write-Host "--- Xbox $($i + 1) ---" -ForegroundColor Cyan

    $windowIndex = $i

    $ipAddress = ""
    while ($ipAddress -notmatch "^(\d{1,3}\.){3}\d{1,3}$") {
        $ipAddress = Read-Host "  IP 地址（如：192.168.1.$($i+50)）"
        if ($ipAddress -notmatch "^(\d{1,3}\.){3}\d{1,3}$") {
            Write-Host "  IP 地址格式不正确" -ForegroundColor Yellow
        }
    }

    $name = Read-Host "  名称（可选，如：Xbox-$($i+1)）"
    if ($name -eq "") { $name = "Xbox-$($i+1)" }

    $macAddress = ""
    while ($macAddress -notmatch "^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") {
        $macAddress = Read-Host "  MAC 地址（如：AA:BB:CC:DD:EE:$($i+50)）"
        if ($macAddress -notmatch "^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$") {
            Write-Host "  MAC 地址格式不正确（如：AA:BB:CC:DD:EE:FF）" -ForegroundColor Yellow
        }
    }

    $xboxConfigs += @{
        windowIndex = $windowIndex
        ipAddress = $ipAddress
        name = $name
        macAddress = $macAddress.ToUpper()
    }

    Write-Host ""
}

# 调用注册接口
$registerUrl = "$BackendUrl/api/agent/register"
$registerBody = @{
    installCode = $installCode
    host = $localIp
    port = 9999
    macAddress = $macAddress
    xboxConfigs = $xboxConfigs
    version = "1.0.0"
} | ConvertTo-Json

try {
    $response = Invoke-RestMethod -Uri $registerUrl -Method Post -Body $registerBody -ContentType "application/json" -TimeoutSec 30
} catch {
    Write-Host "错误: 无法连接到服务器" -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

if (-not $response.success) {
    Write-Host "错误: $($response.message)" -ForegroundColor Red
    exit 1
}

Write-Host "安装码验证成功!" -ForegroundColor Green
Write-Host "  Agent ID: $($response.agentId)"
Write-Host "  商户 ID: $($response.merchantId)"
Write-Host ""

# 保存配置
$config = @{
    agent = @{
        agent_id = $response.agentId
        host = $localIp
        port = 9999
        mac_address = $macAddress
    }
    backend = @{
        url = $BackendUrl
        ws_url = $BackendUrl.Replace("http", "ws") + "/ws/agent"
        heartbeat_interval = $response.config.heartbeatInterval
        reconnect_delay = 5
    }
    automation = @{
        max_retry = 3
        template_timeout = 30
        stream_timeout = 60
    }
}

$configPath = Join-Path $PSScriptRoot "config.yaml"
$config | ConvertTo-Yaml -OutFile $configPath

# 配置开机自启动
if ($AutoStart) {
    $taskName = "XStreamingAgent"
    $action = New-ScheduledTaskAction -Execute "python" -Argument "-m agent.main --config `"$configPath`""
    $trigger = New-ScheduledTaskTrigger -AtStartup
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries

    Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "XStreaming Agent 自动启动任务" -Force
    Write-Host "已配置开机自启动" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   安装完成!" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "现在可以启动 Agent:" -ForegroundColor Green
Write-Host "  python -m agent.main --config $configPath"
Write-Host ""

# 询问是否立即启动
$startNow = Read-Host "是否立即启动 Agent？(Y/N)"
if ($startNow -eq "Y" -or $startNow -eq "y") {
    python -m agent.main --config $configPath
}
```

### 7.2.4 Wake-on-LAN 服务端实现

```java
// WolService.java - Wake-on-LAN 服务
@Service
public class WolService {

    @Value("${wol.broadcast-interface:255.255.255.255}")
    private String broadcastAddress;

    public boolean wakeAgent(AgentInstance agent) {
        if (!agent.getWolEnabled()) {
            throw new BusinessException("该 Agent 未配置 Wake-on-LAN");
        }

        String macAddress = agent.getMacAddress();
        String broadcast = agent.getWolBroadcastAddress() != null
            ? agent.getWolBroadcastAddress()
            : broadcastAddress;

        return sendMagicPacket(macAddress, broadcast);
    }

    private boolean sendMagicPacket(String macAddress, String broadcastAddress) {
        try {
            byte[] mac = parseMacAddress(macAddress);
            byte[] packet = new byte[102];

            // 魔术包格式：6字节 0xFF + 16次 MAC 地址
            Arrays.fill(packet, 0, 6, (byte) 0xFF);
            for (int i = 0; i < 16; i++) {
                System.arraycopy(mac, 0, packet, 6 + i * 6, 6);
            }

            InetAddress address = InetAddress.getByName(broadcastAddress);
            DatagramPacket datagram = new DatagramPacket(packet, packet.length, address, 9);
            DatagramSocket socket = new DatagramSocket();
            socket.send(datagram);
            socket.close();

            logger.info("已发送 Wake-on-LAN 魔术包到 {}", macAddress);
            return true;
        } catch (Exception e) {
            logger.error("发送 Wake-on-LAN 失败", e);
            return false;
        }
    }
}
```

### 十三、场景智能匹配系统

场景智能匹配系统是 Python Agent 的核心组件，负责在各种 Xbox UI 场景下快速、准确地识别界面元素并执行相应操作。系统采用混合匹配策略，结合模板匹配的高速度和 OCR 文字识别的高准确性，根据不同场景自动选择最优匹配方式。

### 13.1 SceneBasedMatcher 场景匹配器

### 13.1.1 场景枚举定义

系统定义了 8 种自动化场景，每种场景对应不同的匹配策略：

```python
from enum import Enum
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from collections import namedtuple
import time
import asyncio
import logging

logger = logging.getLogger(__name__)


class Scene(Enum):
    COMPETITION = "competition"
    GAMING = "gaming"
    LOGIN = "login"
    MENU = "menu"
    SETTINGS = "settings"
    ACCOUNT = "account"
    STREAMING = "streaming"
    GENERAL = "general"

    @classmethod
    def from_string(cls, value: str) -> "Scene":
        try:
            return cls(value.lower())
        except ValueError:
            return cls.GENERAL


MatchResult = namedtuple(
    "MatchResult",
    ["found", "method", "data", "norm_coords", "elapsed_ms"]
)


@dataclass
class MatcherConfig:
    preferred_method: str = "auto"
    allow_ocr: bool = True
    allow_template: bool = True
    ocr_timeout_ms: int = 100
    template_timeout_ms: int = 50
    confidence_threshold: float = 0.8
```

### 8.1.2 SceneBasedMatcher 类设计

```python
class SceneBasedMatcher:
    SCENE_CONFIGS: Dict[Scene, MatcherConfig] = {
        Scene.COMPETITION: MatcherConfig(
            preferred_method="template",
            allow_ocr=False,
            allow_template=True,
            template_timeout_ms=20
        ),
        Scene.GAMING: MatcherConfig(
            preferred_method="template",
            allow_ocr=False,
            allow_template=True,
            template_timeout_ms=20
        ),
        Scene.LOGIN: MatcherConfig(
            preferred_method="template",
            allow_ocr=True,
            allow_template=True,
            template_timeout_ms=50,
            ocr_timeout_ms=100
        ),
        Scene.MENU: MatcherConfig(
            preferred_method="template",
            allow_ocr=True,
            allow_template=True,
            template_timeout_ms=50,
            ocr_timeout_ms=100
        ),
        Scene.SETTINGS: MatcherConfig(
            preferred_method="ocr",
            allow_ocr=True,
            allow_template=True,
            ocr_timeout_ms=100
        ),
        Scene.ACCOUNT: MatcherConfig(
            preferred_method="ocr",
            allow_ocr=True,
            allow_template=True,
            ocr_timeout_ms=100
        ),
        Scene.STREAMING: MatcherConfig(
            preferred_method="template",
            allow_ocr=True,
            allow_template=True,
            template_timeout_ms=50,
            ocr_timeout_ms=100
        ),
        Scene.GENERAL: MatcherConfig(
            preferred_method="template",
            allow_ocr=True,
            allow_template=True,
            template_timeout_ms=50,
            ocr_timeout_ms=100
        ),
    }

    TARGET_SCENE_MAP: Dict[str, Scene] = {
        "a_button": Scene.GAMING,
        "b_button": Scene.GAMING,
        "x_button": Scene.GAMING,
        "y_button": Scene.GAMING,
        "home_btn": Scene.GENERAL,
        "guide_icon": Scene.GENERAL,
        "back_btn": Scene.GENERAL,
        "menu_btn": Scene.MENU,
        "login_button": Scene.LOGIN,
        "sign_in_btn": Scene.LOGIN,
        "continue_btn": Scene.GENERAL,
        "settings_icon": Scene.SETTINGS,
        "account_icon": Scene.ACCOUNT,
        "Sign in": Scene.LOGIN,
        "Sign out": Scene.ACCOUNT,
        "Settings": Scene.SETTINGS,
        "Home": Scene.GENERAL,
        "Account": Scene.ACCOUNT,
        "My games": Scene.MENU,
        "Guide": Scene.GENERAL,
        "OK": Scene.GENERAL,
        "Cancel": Scene.GENERAL,
        "Confirm": Scene.GENERAL,
        "Back": Scene.GENERAL,
        "下一步": Scene.GENERAL,
        "取消": Scene.GENERAL,
        "确定": Scene.GENERAL,
    }

    def __init__(
        self,
        template_matcher: "TemplateMatcher",
        ocr_matcher: "OCRTextMatcher"
    ):
        self.template_matcher = template_matcher
        self.ocr_matcher = ocr_matcher
        self.current_scene = Scene.GENERAL
        self._result_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl = 0.5
        self._frame_count = 0

    def set_scene(self, scene: Scene) -> None:
        if not isinstance(scene, Scene):
            scene = Scene.from_string(scene)
        if self.current_scene != scene:
            logger.info(f"场景切换: {self.current_scene.value} -> {scene.value}")
            self.current_scene = scene
            self._result_cache.clear()

    def match(
        self,
        frame: "np.ndarray",
        target: str,
        force_method: Optional[str] = None
    ) -> Optional[MatchResult]:
        cache_key = f"{target}:{self.current_scene.value}"
        if cache_key in self._result_cache:
            cached = self._result_cache[cache_key]
            if time.time() - cached["time"] < self._cache_ttl:
                return cached["result"]

        config = self.SCENE_CONFIGS[self.current_scene]
        method = force_method or self._decide_method(target, config)

        result = None
        elapsed = 0.0

        if method == "template" and config.allow_template:
            result, elapsed = self._try_template_match(frame, target, config)

        if result is None and config.allow_ocr:
            if method == "ocr" or (method == "template" and result is None):
                result, elapsed = self._try_ocr_match(frame, target, config)

        if result is not None:
            self._result_cache[cache_key] = {
                "result": result,
                "time": time.time()
            }

        return result

    def _decide_method(self, target: str, config: MatcherConfig) -> str:
        if config.preferred_method != "auto":
            return config.preferred_method

        if target in self.TARGET_SCENE_MAP:
            recommended_scene = self.TARGET_SCENE_MAP[target]
            if recommended_scene in [Scene.GAMING, Scene.COMPETITION]:
                return "template"

        is_text_target = (
            " " in target
            or any("\u4e00" <= c <= "\u9fff" for c in target)
            or target in ["Sign in", "Sign out", "Settings", "Home"]
        )

        if is_text_target:
            if self.current_scene in [Scene.GAMING, Scene.COMPETITION]:
                return "template"
            return "ocr"

        return "template"

    def _try_template_match(
        self,
        frame: "np.ndarray",
        target: str,
        config: MatcherConfig
    ) -> tuple:
        start_time = time.time()
        try:
            result = self.template_matcher.match(frame, target)
            elapsed_ms = (time.time() - start_time) * 1000

            if result.found:
                logger.debug(
                    f"模板匹配 '{target}': {elapsed_ms:.1f}ms, "
                    f"coords=({result.x:.3f}, {result.y:.3f})"
                )
                return (
                    MatchResult(
                        found=True,
                        method="template",
                        data=result,
                        norm_coords=(result.x, result.y),
                        elapsed_ms=elapsed_ms
                    ),
                    elapsed_ms
                )
        except Exception as e:
            logger.warning(f"模板匹配异常 '{target}': {e}")

        return None, 0.0

    def _try_ocr_match(
        self,
        frame: "np.ndarray",
        target: str,
        config: MatcherConfig
    ) -> tuple:
        start_time = time.time()
        try:
            result = self.ocr_matcher.find_text(
                frame,
                target,
                match_type="contains"
            )
            elapsed_ms = (time.time() - start_time) * 1000

            if result is not None:
                logger.debug(
                    f"OCR 匹配 '{target}': {elapsed_ms:.1f}ms, "
                    f"text='{result.get('text', '')}'"
                )
                return (
                    MatchResult(
                        found=True,
                        method="ocr",
                        data=result,
                        norm_coords=result.get("norm_center"),
                        elapsed_ms=elapsed_ms
                    ),
                    elapsed_ms
                )
        except Exception as e:
            logger.warning(f"OCR 匹配异常 '{target}': {e}")

        return None, 0.0

    async def wait_for_match(
        self,
        frame_getter: callable,
        target: str,
        timeout: float = 30.0,
        scene: Optional[Scene] = None
    ) -> Optional[MatchResult]:
        if scene is not None:
            self.set_scene(scene)

        start_time = time.time()
        interval = (
            0.05
            if self.current_scene in [Scene.GAMING, Scene.COMPETITION]
            else 0.2
        )

        while time.time() - start_time < timeout:
            frame = frame_getter()
            result = self.match(frame, target)

            if result is not None and result.found:
                result = MatchResult(
                    found=result.found,
                    method=result.method,
                    data=result.data,
                    norm_coords=result.norm_coords,
                    elapsed_ms=(time.time() - start_time) * 1000
                )
                return result

            await asyncio.sleep(interval)

        logger.warning(
            f"等待匹配超时: target='{target}', "
            f"scene={self.current_scene.value}, timeout={timeout}s"
        )
        return None

    def match_any(
        self,
        frame: "np.ndarray",
        targets: List[str]
    ) -> Optional[MatchResult]:
        for target in targets:
            result = self.match(frame, target)
            if result is not None and result.found:
                return result
        return None

    def clear_cache(self) -> None:
        self._result_cache.clear()

    @property
    def frame_count(self) -> int:
        return self._frame_count

    def inc_frame_count(self) -> None:
        self._frame_count += 1
```

### 13.1.3 各场景配置表

| 场景              | preferred\_method | allow\_ocr | allow\_template | template\_timeout\_ms | ocr\_timeout\_ms | 说明              |
| --------------- | ----------------- | ---------- | --------------- | --------------------- | ---------------- | --------------- |
| **COMPETITION** | template          | False      | True            | 20                    | -                | 比赛模式，只用模板，<20ms |
| **GAMING**      | template          | False      | True            | 20                    | -                | 游戏模式，只用模板，<20ms |
| **LOGIN**       | template          | True       | True            | 50                    | 100              | 登录场景，模板优先+OCR   |
| **MENU**        | template          | True       | True            | 50                    | 100              | 菜单场景，模板优先+OCR   |
| **SETTINGS**    | ocr               | True       | True            | 50                    | 100              | 设置场景，OCR优先      |
| **ACCOUNT**     | ocr               | True       | True            | 50                    | 100              | 账号场景，OCR优先      |
| **STREAMING**   | template          | True       | True            | 50                    | 100              | 串流场景，模板优先+OCR   |
| **GENERAL**     | template          | True       | True            | 50                    | 100              | 通用场景，默认配置       |

## 8.2 HybridMatcher 综合匹配器

### 13.2.1 类设计

```python
class HybridMatcher:
    def __init__(self):
        self.template_matcher: Optional[TemplateMatcher] = None
        self.ocr_matcher: Optional[OCRTextMatcher] = None
        self._initialized = False

    async def initialize(
        self,
        template_dir: str,
        use_gpu: bool = True
    ) -> None:
        from .template_matcher import TemplateMatcher
        from .ocr_text_matcher import OCRTextMatcher

        self.template_matcher = TemplateMatcher()
        await self.template_matcher.load_templates(template_dir)

        self.ocr_matcher = OCRTextMatcher()
        await self.ocr_matcher.initialize(use_gpu=use_gpu)

        self._initialized = True
        logger.info("HybridMatcher 初始化完成")

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    def match(
        self,
        frame: "np.ndarray",
        target: str
    ) -> Optional[MatchResult]:
        if not self._initialized:
            raise RuntimeError("HybridMatcher 未初始化")

        start_time = time.time()

        template_result = self.template_matcher.match(frame, target)
        if template_result.found:
            elapsed_ms = (time.time() - start_time) * 1000
            return MatchResult(
                found=True,
                method="template",
                data=template_result,
                norm_coords=(template_result.x, template_result.y),
                elapsed_ms=elapsed_ms
            )

        ocr_result = self.ocr_matcher.find_text(
            frame,
            target,
            match_type="contains"
        )
        if ocr_result is not None:
            elapsed_ms = (time.time() - start_time) * 1000
            return MatchResult(
                found=True,
                method="ocr",
                data=ocr_result,
                norm_coords=ocr_result.get("norm_center"),
                elapsed_ms=elapsed_ms
            )

        return None

    def match_with_fallback(
        self,
        frame: "np.ndarray",
        target: str,
        fallback_targets: List[str]
    ) -> Optional[MatchResult]:
        result = self.match(frame, target)
        if result is not None and result.found:
            return result

        for fallback_target in fallback_targets:
            result = self.match(frame, fallback_target)
            if result is not None and result.found:
                logger.debug(
                    f"主目标 '{target}' 未匹配，"
                    f"fallback '{fallback_target}' 匹配成功"
                )
                return result

        return None

    def match_multiple(
        self,
        frame: "np.ndarray",
        targets: List[str]
    ) -> List[MatchResult]:
        results = []
        for target in targets:
            result = self.match(frame, target)
            if result is not None and result.found:
                results.append(result)
        return results

    async def wait_for_match(
        self,
        frame_getter: callable,
        target: str,
        timeout: float = 30.0
    ) -> Optional[MatchResult]:
        start_time = time.time()
        interval = 0.2

        while time.time() - start_time < timeout:
            frame = frame_getter()
            result = self.match(frame, target)

            if result is not None and result.found:
                return result

            await asyncio.sleep(interval)

        return None
```

## 8.3 OCRTextMatcher 文字识别匹配器

### 8.3.1 类设计

```python
class OCRTextMatcher:
    def __init__(self):
        self.reader = None
        self._engine = None
        self.text_cache: Dict[str, List[Dict]] = {}
        self._cache_enabled = True
        self._predefined_rois: Dict[str, tuple] = {
            "Sign in": (0.3, 0.4, 0.7, 0.6),
            "Sign out": (0.3, 0.4, 0.7, 0.6),
            "OK": (0.3, 0.5, 0.7, 0.8),
            "Cancel": (0.3, 0.5, 0.7, 0.8),
            "Confirm": (0.3, 0.5, 0.7, 0.8),
            "Settings": (0.0, 0.0, 0.4, 0.4),
            "Account": (0.0, 0.0, 0.4, 0.4),
            "Home": (0.0, 0.0, 0.2, 0.2),
            "Back": (0.0, 0.7, 0.3, 1.0),
            "Menu": (0.7, 0.7, 1.0, 1.0),
            "下一步": (0.5, 0.7, 0.9, 0.9),
            "取消": (0.3, 0.5, 0.7, 0.8),
            "确定": (0.3, 0.5, 0.7, 0.8),
        }

    async def initialize(self, use_gpu: bool = True) -> None:
        try:
            import easyocr
            self.reader = easyocr.Reader(
                ["ch_sim", "en"],
                gpu=use_gpu,
                verbose=False
            )
            self._engine = "easyocr"
            logger.info("OCR 引擎: EasyOCR")
        except ImportError:
            try:
                from paddleocr import PaddleOCR
                self.reader = PaddleOCR(
                    use_angle_cls=True,
                    lang="ch",
                    use_gpu=use_gpu,
                    show_log=False
                )
                self._engine = "paddleocr"
                logger.info("OCR 引擎: PaddleOCR")
            except ImportError:
                raise RuntimeError(
                    "请安装 easyocr 或 paddleocr: "
                    "pip install easyocr  # 或 pip install paddleocr"
                )

    @property
    def engine(self) -> str:
        return self._engine or "unknown"

    def recognize_text(
        self,
        frame: "np.ndarray",
        roi: Optional[tuple] = None
    ) -> List[Dict[str, Any]]:
        if self.reader is None:
            raise RuntimeError("OCR 引擎未初始化，请先调用 initialize()")

        cache_key = f"{id(frame)}:{roi}"
        if self._cache_enabled and cache_key in self.text_cache:
            return self.text_cache[cache_key]

        frame_rgb = frame[:, :, ::-1]
        h, w = frame.shape[:2]

        roi_frame = frame_rgb
        roi_offset = (0, 0)
        if roi is not None:
            x1 = int(roi[0] * w)
            y1 = int(roi[1] * h)
            x2 = int(roi[2] * w)
            y2 = int(roi[3] * h)
            roi_frame = frame_rgb[y1:y2, x1:x2]
            roi_offset = (x1, y1)

        if self._engine == "easyocr":
            results = self.reader.readtext(roi_frame)
        elif self._engine == "paddleocr":
            ocr_results = self.reader.ocr(roi_frame, cls=True)
            results = []
            if ocr_results and ocr_results[0]:
                for line in ocr_results[0]:
                    if line:
                        results.append(line)
        else:
            raise RuntimeError(f"不支持的 OCR 引擎: {self._engine}")

        text_items = []
        for item in results:
            if self._engine == "easyocr":
                bbox = item[0]
                text = item[1]
                confidence = item[2]
            else:
                if not item or len(item) < 2:
                    continue
                bbox = item[0]
                text = item[1]
                confidence = (
                    item[2][0]
                    if isinstance(item[2], list)
                    else item[2]
                )

            x1 = min(p[0] for p in bbox)
            y1 = min(p[1] for p in bbox)
            x2 = max(p[0] for p in bbox)
            y2 = max(p[1] for p in bbox)

            center_x = (x1 + x2) / 2 + roi_offset[0]
            center_y = (y1 + y2) / 2 + roi_offset[1]

            text_items.append({
                "text": text.strip(),
                "bbox": (x1 + roi_offset[0], y1 + roi_offset[1],
                         x2 + roi_offset[0], y2 + roi_offset[1]),
                "center": (center_x, center_y),
                "norm_center": (center_x / w, center_y / h),
                "confidence": float(confidence)
            })

        if self._cache_enabled:
            self.text_cache[cache_key] = text_items

        return text_items

    def find_text(
        self,
        frame: "np.ndarray",
        target: str,
        match_type: str = "contains",
        roi: Optional[tuple] = None
    ) -> Optional[Dict[str, Any]]:
        effective_roi = roi or self._predefined_rois.get(target)

        text_items = self.recognize_text(frame, roi=effective_roi)

        target_lower = target.lower()

        for item in text_items:
            text_lower = item["text"].lower()

            if match_type == "exact" and text_lower == target_lower:
                return item

            if match_type == "contains" and target_lower in text_lower:
                return item

            if match_type == "fuzzy":
                if self._fuzzy_match(target_lower, text_lower):
                    return item

        return None

    def _fuzzy_match(
        self,
        s1: str,
        s2: str,
        threshold: float = 0.8
    ) -> bool:
        from difflib import SequenceMatcher
        ratio = SequenceMatcher(None, s1, s2).ratio()
        return ratio >= threshold

    def find_all_text(
        self,
        frame: "np.ndarray",
        targets: List[str],
        match_type: str = "contains"
    ) -> List[Dict[str, Any]]:
        results = []
        for target in targets:
            result = self.find_text(frame, target, match_type)
            if result is not None:
                results.append(result)
        return results

    def wait_for_text(
        self,
        frame_getter: callable,
        target: str,
        timeout: float = 30,
        match_type: str = "contains"
    ) -> Optional[Dict[str, Any]]:
        start_time = time.time()

        while time.time() - start_time < timeout:
            frame = frame_getter()
            result = self.find_text(frame, target, match_type)
            if result is not None:
                return result
            time.sleep(0.5)

        return None

    def clear_cache(self) -> None:
        self.text_cache.clear()
```

## 8.4 场景配置与性能对比

### 13.4.1 场景配置表

| 场景          | 英文 | 首选方法     | 允许模板 | 允许OCR | 超时策略        | 适用场景描述       |
| ----------- | -- | -------- | ---- | ----- | ----------- | ------------ |
| COMPETITION | 比赛 | template | ✅    | ❌     | <20ms       | 电竞比赛，要求最低延迟  |
| GAMING      | 游戏 | template | ✅    | ❌     | <20ms       | 游戏过程中，实时性要求高 |
| LOGIN       | 登录 | template | ✅    | ✅     | <50ms+100ms | 微软账号登录，文字输入  |
| MENU        | 菜单 | template | ✅    | ✅     | <50ms+100ms | 导航菜单，偶尔有文字   |
| SETTINGS    | 设置 | ocr      | ✅    | ✅     | 100ms       | 系统设置，文字密集    |
| ACCOUNT     | 账号 | ocr      | ✅    | ✅     | 100ms       | 账号管理，文字密集    |
| STREAMING   | 串流 | template | ✅    | ✅     | <50ms+100ms | 串流控制，兼顾速度和文字 |
| GENERAL     | 通用 | template | ✅    | ✅     | <50ms+100ms | 默认配置，混合场景    |

### 8.4.2 性能对比表

| 匹配方式      | 单次延迟       | 适用场景          | 优缺点                 |
| --------- | ---------- | ------------- | ------------------- |
| **模板匹配**  | \~10-20ms  | 固定UI元素（按钮、图标） | ✅ 速度快，❌ 需准备模板图片     |
| **OCR识别** | \~50-150ms | 文字元素（登录、设置）   | ✅ 无需模板，❌ 速度慢、可能有误识别 |
| **混合匹配**  | \~20-100ms | 通用场景          | ✅ 取长补短，❌ 实现复杂度高     |

### 8.4.3 延迟分析

```
┌─────────────────────────────────────────────────────────────────┐
│                      匹配延迟分布                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  模板匹配 (COMPETITION/GAMING):                                 │
│  ┌──────────────┐                                               │
│  │ [Capture]   │  ~2ms                                          │
│  │ [Match]     │  ~8ms                                          │
│  │ [Total]     │  ~10ms                                         │
│  └──────────────┘                                               │
│                                                                 │
│  模板+OCR混合 (LOGIN/MENU):                                      │
│  ┌──────────────┐                                               │
│  │ [Capture]   │  ~2ms                                          │
│  │ [Template]  │  ~10ms                                         │
│  │ [OCR]       │  ~50-100ms (if template fails)               │
│  │ [Total]     │  ~10-100ms                                     │
│  └──────────────┘                                               │
│                                                                 │
│  OCR优先 (SETTINGS/ACCOUNT):                                     │
│  ┌──────────────┐                                               │
│  │ [Capture]   │  ~2ms                                          │
│  │ [OCR]       │  ~50-150ms                                     │
│  │ [Total]     │  ~50-150ms                                     │
│  └──────────────┘                                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## 8.5 Xbox UI 常用文字目标

### 8.5.1 文字识别目标表

| Xbox UI 元素 | 英文文字            | 推荐场景     | 匹配方式  | 模板/OCR说明   |
| ---------- | --------------- | -------- | ----- | ---------- |
| 主屏幕        | Home            | GENERAL  | 模板优先  | 可用模板或OCR   |
| 设置         | Settings        | SETTINGS | OCR优先 | 文字密集，建议OCR |
| 我的游戏和应用    | My games & apps | MENU     | 模板优先  | 可用模板       |
| 指南         | Guide           | GENERAL  | 模板优先  | 图标可用模板     |
| 登录         | Sign in         | LOGIN    | 模板优先  | 按钮可模板      |
| 登出         | Sign out        | ACCOUNT  | OCR优先 | 文字界面建议OCR  |
| 账号         | Account         | ACCOUNT  | OCR优先 | 文字界面建议OCR  |
| 确定         | OK              | GENERAL  | 模板优先  | 通用按钮       |
| 取消         | Cancel          | GENERAL  | 模板优先  | 通用按钮       |
| 返回         | Back            | GENERAL  | 模板优先  | 通用按钮       |
| 下一步        | 下一步             | LOGIN    | 模板优先  | 中文可OCR     |
| 取消         | 取消              | GENERAL  | 模板优先  | 中文可OCR     |
| 确定         | 确定              | GENERAL  | 模板优先  | 中文可OCR     |
| 添加账号       | Add new         | LOGIN    | 模板优先  | 可用模板       |
| 记住我        | Remember me     | LOGIN    | OCR   | 复选框文字      |
| 移除账号       | Remove account  | ACCOUNT  | OCR   | 文字菜单       |

### 8.5.2 匹配方式选择决策树

```
                    ┌─────────────────────┐
                    │   开始匹配目标       │
                    └──────────┬──────────┘
                               │
                               ▼
                    ┌─────────────────────┐
                    │ 是否是固定UI元素？   │
                    │ (按钮、图标、符号)   │
                    └──────────┬──────────┘
                              Yes│No
                    ┌──────────┴──────────┐
                    ▼                     ▼
         ┌──────────────────┐  ┌──────────────────┐
         │ 使用模板匹配      │  │ 是否包含中文/空格？ │
         │ (~10ms)          │  └──────────┬──────────┘
         └──────────────────┘      Yes   │   No
                                         ▼
                              ┌──────────────────┐
                              │ 使用OCR匹配      │
                              │ (~50-150ms)      │
                              └──────────────────┘
```

### 13.5.3 ROI 预定义区域

```python
REGION_OF_INTEREST_MAP = {
    "Sign in": {
        "roi": (0.3, 0.4, 0.7, 0.6),
        "description": "登录按钮区域，屏幕中央偏下"
    },
    "Sign out": {
        "roi": (0.3, 0.4, 0.7, 0.6),
        "description": "登出按钮区域，屏幕中央偏下"
    },
    "Settings": {
        "roi": (0.0, 0.0, 0.4, 0.4),
        "description": "设置入口，左上角"
    },
    "Account": {
        "roi": (0.0, 0.0, 0.4, 0.4),
        "description": "账号入口，左上角"
    },
    "Home": {
        "roi": (0.0, 0.0, 0.2, 0.2),
        "description": "主页入口，左上角"
    },
    "OK": {
        "roi": (0.3, 0.5, 0.7, 0.8),
        "description": "确认按钮，屏幕中央偏下"
    },
    "Cancel": {
        "roi": (0.3, 0.5, 0.7, 0.8),
        "description": "取消按钮，屏幕中央偏下"
    },
    "Back": {
        "roi": (0.0, 0.7, 0.3, 1.0),
        "description": "返回按钮，左下角"
    },
    "Menu": {
        "roi": (0.7, 0.7, 1.0, 1.0),
        "description": "菜单按钮，右下角"
    },
    "下一步": {
        "roi": (0.5, 0.7, 0.9, 0.9),
        "description": "下一步按钮，屏幕右下方"
    },
    "确定": {
        "roi": (0.3, 0.5, 0.7, 0.8),
        "description": "确定按钮，屏幕中央偏下"
    },
    "取消": {
        "roi": (0.3, 0.5, 0.7, 0.8),
        "description": "取消按钮，屏幕中央偏下"
    },
}
```

## 13.6 使用示例

```python
import asyncio
import numpy as np


async def main():
    from core.template_matcher import TemplateMatcher
    from core.ocr_text_matcher import OCRTextMatcher
    from core.scene_matcher import SceneBasedMatcher, Scene

    template_matcher = TemplateMatcher()
    await template_matcher.load_templates("./templates/xbox")

    ocr_matcher = OCRTextMatcher()
    await ocr_matcher.initialize(use_gpu=True)

    matcher = SceneBasedMatcher(template_matcher, ocr_matcher)

    def capture_frame():
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    matcher.set_scene(Scene.GAMING)
    result = matcher.match(capture_frame(), "a_button")
    print(f"GAMING 场景匹配 'a_button': {result}")

    matcher.set_scene(Scene.LOGIN)
    result = matcher.match(capture_frame(), "Sign in")
    print(f"LOGIN 场景匹配 'Sign in': {result}")

    matcher.set_scene(Scene.SETTINGS)
    result = matcher.match(capture_frame(), "Settings")
    print(f"SETTINGS 场景匹配 'Settings': {result}")

    result = await matcher.wait_for_match(
        capture_frame,
        "下一步",
        timeout=30,
        scene=Scene.LOGIN
    )
    print(f"等待 '下一步' 出现: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

***

## 十四、手柄操作自动化

手柄操作自动化是 Xbox Agent 的核心功能，负责在各种 Xbox UI 场景下循环检测界面元素并模拟相应的手柄操作。系统基于 pygame 库实现游戏手柄的精确控制，支持所有标准 Xbox 手柄按钮和摇杆操作。

### 9.1 GamepadButton 枚举定义

系统定义了完整的 16 按钮枚举，涵盖 Xbox 手柄的所有标准按钮：

```python
from enum import Enum


class GamepadButton(Enum):
    A = 0
    B = 1
    X = 2
    Y = 3
    LB = 4
    RB = 5
    LT = 6
    RT = 7
    BACK = 8
    START = 9
    L3 = 10
    R3 = 11
    DPAD_UP = 12
    DPAD_DOWN = 13
    DPAD_LEFT = 14
    DPAD_RIGHT = 15
```

| 按钮          | 值  | 说明     |
| ----------- | -- | ------ |
| A           | 0  | 确认按钮   |
| B           | 1  | 返回按钮   |
| X           | 2  | 特殊功能按钮 |
| Y           | 3  | 特殊功能按钮 |
| LB          | 4  | 左肩键    |
| RB          | 5  | 右肩键    |
| LT          | 6  | 左扳机    |
| RT          | 7  | 右扳机    |
| BACK        | 8  | 选择/返回  |
| START       | 9  | 开始/暂停  |
| L3          | 10 | 左摇杆按下  |
| R3          | 11 | 右摇杆按下  |
| DPAD\_UP    | 12 | 方向键上   |
| DPAD\_DOWN  | 13 | 方向键下   |
| DPAD\_LEFT  | 14 | 方向键左   |
| DPAD\_RIGHT | 15 | 方向键右   |

### 9.2 手柄操作方法

#### 9.2.1 GamepadController 类设计

```python
import pygame
import time
import logging
from typing import Tuple, Optional
from .gamepad_button import GamepadButton

logger = logging.getLogger(__name__)


class GamepadController:
    def __init__(self, joystick_id: int = 0):
        pygame.init()
        self.joystick = None
        self.joystick_id = joystick_id
        self._initialized = False
        self._button_state = [False] * 16
        self._stick_deadzone = 0.15

    def initialize(self) -> bool:
        try:
            if pygame.joystick.get_count() == 0:
                logger.warning("未检测到手柄")
                return False

            self.joystick = pygame.joystick.Joystick(self.joystick_id)
            self.joystick.init()
            logger.info(f"手柄已初始化: {self.joystick.get_name()}")
            self._initialized = True
            return True
        except Exception as e:
            logger.error(f"手柄初始化失败: {e}")
            return False

    def _press_button(self, button: GamepadButton, duration: float = 0.1) -> None:
        if not self._initialized:
            logger.warning("手柄未初始化，跳过按钮操作")
            return

        try:
            button_id = button.value
            pygame.event.post(pygame.event.Event(
                pygame.JOYBUTTONDOWN,
                {'joy': self.joystick_id, 'button': button_id}
            ))
            pygame.event.post(pygame.event.Event(
                pygame.JOYBUTTONUP,
                {'joy': self.joystick_id, 'button': button_id}
            ))
            self._button_state[button_id] = True
            logger.debug(f"按下按钮: {button.name}")
            time.sleep(duration)
            self._button_state[button_id] = False
        except Exception as e:
            logger.error(f"按钮操作失败 {button.name}: {e}")

    def _move_stick(
        self,
        stick: str,
        x: float,
        y: float,
        duration: float = 0.1
    ) -> None:
        if not self._initialized:
            return

        x = max(-1.0, min(1.0, x))
        y = max(-1.0, min(1.0, y))

        if abs(x) < self._stick_deadzone:
            x = 0.0
        if abs(y) < self._stick_deadzone:
            y = 0.0

        try:
            stick_id = 0 if stick == "left" else 1

            pygame.event.post(pygame.event.Event(
                pygame.JOYAXISMOTION,
                {'joy': self.joystick_id, 'axis': stick_id * 2, 'value': x}
            ))
            pygame.event.post(pygame.event.Event(
                pygame.JOYAXISMOTION,
                {'joy': self.joystick_id, 'axis': stick_id * 2 + 1, 'value': y}
            ))
            logger.debug(f"移动摇杆: {stick} ({x:.2f}, {y:.2f})")
            time.sleep(duration)
        except Exception as e:
            logger.error(f"摇杆操作失败 {stick}: {e}")

    def _release_all(self) -> None:
        if not self._initialized:
            return

        try:
            for button_id in range(16):
                if self._button_state[button_id]:
                    pygame.event.post(pygame.event.Event(
                        pygame.JOYBUTTONUP,
                        {'joy': self.joystick_id, 'button': button_id}
                    ))
                    self._button_state[button_id] = False

            for axis_id in range(6):
                pygame.event.post(pygame.event.Event(
                    pygame.JOYAXISMOTION,
                    {'joy': self.joystick_id, 'axis': axis_id, 'value': 0.0}
                ))
            logger.debug("释放所有输入")
        except Exception as e:
            logger.error(f"释放所有输入失败: {e}")

    def press_start(self, duration: float = 0.1) -> None:
        self._press_button(GamepadButton.START, duration)

    def press_a(self, duration: float = 0.1) -> None:
        self._press_button(GamepadButton.A, duration)

    def press_b(self, duration: float = 0.1) -> None:
        self._press_button(GamepadButton.B, duration)

    def press_guide(self, duration: float = 0.1) -> None:
        self._press_button(GamepadButton.START, duration)
        time.sleep(0.3)
        self._press_button(GamepadButton.A, duration)

    def move_left_stick(
        self,
        x: float,
        y: float,
        duration: float = 0.1
    ) -> None:
        self._move_stick("left", x, y, duration)

    def move_right_stick(
        self,
        x: float,
        y: float,
        duration: float = 0.1
    ) -> None:
        self._move_stick("right", x, y, duration)

    def shutdown(self) -> None:
        self._release_all()
        if self.joystick:
            self.joystick.quit()
        pygame.quit()
        self._initialized = False
        logger.info("手柄已关闭")
```

#### 9.2.2 手柄操作方法说明

| 方法                                   | 参数                                                               | 说明                          |
| ------------------------------------ | ---------------------------------------------------------------- | --------------------------- |
| `_press_button(button, duration)`    | button: GamepadButton, duration: float = 0.1                     | 按下并释放按钮，duration 为按压时长      |
| `_move_stick(stick, x, y, duration)` | stick: str ("left"/"right"), x: float, y: float, duration: float | 移动摇杆到指定位置，x/y 范围 -1.0 到 1.0 |
| `_release_all()`                     | 无                                                                | 释放所有按钮和摇杆输入                 |
| `press_start(duration)`              | duration: float = 0.1                                            | 快捷方法：按 Start 暂停             |
| `press_a(duration)`                  | duration: float = 0.1                                            | 快捷方法：按 A 确认                 |
| `press_b(duration)`                  | duration: float = 0.1                                            | 快捷方法：按 B 返回                 |
| `press_guide(duration)`              | duration: float = 0.1                                            | 快捷方法：按 Xbox 指南按钮            |
| `move_left_stick(x, y, duration)`    | x: float, y: float, duration: float                              | 移动左摇杆                       |
| `move_right_stick(x, y, duration)`   | x: float, y: float, duration: float                              | 移动右摇杆                       |

### 9.3 界面检测循环

#### 9.3.1 XboxGameAutomation 类设计

```python
import asyncio
import time
import logging
from typing import Optional, Dict, Any
from .gamepad_controller import GamepadController
from .scene_matcher import SceneBasedMatcher, Scene

logger = logging.getLogger(__name__)


class XboxGameAutomation:
    XBOX_UI_TEMPLATES: Dict[str, str] = {
        "pause_menu": "templates/xbox/pause_menu.png",
        "confirm_dialog": "templates/xbox/confirm_dialog.png",
        "back_button": "templates/xbox/back_button.png",
        "guide_button": "templates/xbox/guide_button.png",
        "loading": "templates/xbox/loading.png",
        "error_dialog": "templates/xbox/error_dialog.png",
        "a_button": "templates/xbox/a_button.png",
        "b_button": "templates/xbox/b_button.png",
    }

    def __init__(
        self,
        scene_matcher: SceneBasedMatcher,
        frame_capture_func: callable,
        joystick_id: int = 0
    ):
        self.scene_matcher = scene_matcher
        self.capture_frame = frame_capture_func
        self.gamepad = GamepadController(joystick_id)
        self._failed = False
        self._running = False
        self._lock = asyncio.Lock()

    async def start(self) -> None:
        async with self._lock:
            if self._running:
                logger.warning("自动化已在运行中")
                return

            if not self.gamepad.initialize():
                logger.error("手柄初始化失败，无法启动自动化")
                self._failed = True
                return

            self._running = True
            self._failed = False
            logger.info("Xbox 游戏自动化已启动")

            asyncio.create_task(self._play_game())

    async def stop(self) -> None:
        async with self._lock:
            if not self._running:
                return

            self._running = False
            self.gamepad.shutdown()
            logger.info("Xbox 游戏自动化已停止")

    async def _play_game(self) -> None:
        logger.info("[playing] 开始游戏手柄操作循环...")

        while self._running and not self._failed:
            try:
                frame = self.capture_frame()
                if frame is None:
                    await asyncio.sleep(0.5)
                    continue

                await self._detect_and_act(frame)

            except Exception as e:
                logger.error(f"游戏循环异常: {e}")
                await asyncio.sleep(1)

        logger.info("[playing] 游戏手柄操作循环已结束")

    async def _detect_and_act(self, frame) -> None:
        scene_matcher = self.scene_matcher

        scene_matcher.set_scene(Scene.GAMING)

        if scene_matcher.match(frame, "pause_menu", force_method="template").found:
            logger.info("检测到暂停菜单，按下 Start")
            self.gamepad.press_start()
            await asyncio.sleep(0.5)
            return

        if scene_matcher.match(frame, "confirm_dialog", force_method="template").found:
            logger.info("检测到确认对话框，按下 A")
            self.gamepad.press_a()
            await asyncio.sleep(0.5)
            return

        if scene_matcher.match(frame, "back_button", force_method="template").found:
            logger.info("检测到返回按钮，按下 B")
            self.gamepad.press_b()
            await asyncio.sleep(0.5)
            return

        if scene_matcher.match(frame, "guide_button", force_method="template").found:
            logger.info("检测到 Xbox 指南按钮")
            self.gamepad.press_guide()
            await asyncio.sleep(0.5)
            return

        if scene_matcher.match(frame, "loading", force_method="template").found:
            logger.info("检测到加载界面，等待...")
            await asyncio.sleep(2)
            return

        if scene_matcher.match(frame, "error_dialog", force_method="template").found:
            logger.info("检测到错误对话框，按下 B 关闭")
            self.gamepad.press_b()
            await asyncio.sleep(0.5)
            return

        await asyncio.sleep(0.1)

    async def wait_for_template(
        self,
        template_name: str,
        timeout: float = 30.0,
        fail_on_timeout: bool = True
    ) -> bool:
        result = await self.scene_matcher.wait_for_match(
            self.capture_frame,
            template_name,
            timeout=timeout,
            scene=Scene.GAMING
        )

        if result is None and fail_on_timeout:
            logger.error(f"等待模板 '{template_name}' 超时")
            self._failed = True

        return result is not None

    async def press_button_sequence(
        self,
        buttons: list,
        interval: float = 0.3
    ) -> None:
        for button in buttons:
            self.gamepad._press_button(button)
            await asyncio.sleep(interval)

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_failed(self) -> bool:
        return self._failed
```

#### 9.3.2 界面检测流程

```
┌─────────────────────────────────────────────┐
│            循环检测 Xbox 界面                 │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  检测到 "pause_menu" 模板?                   │
│  是 → press_start() → 暂停/取消暂停           │
│  否 → 继续检测                                │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  检测到 "confirm_dialog" 模板?               │
│  是 → press_a() → 确认操作                   │
│  否 → 继续检测                                │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  检测到 "back_button" 模板?                  │
│  是 → press_b() → 返回上级菜单                │
│  否 → 继续检测                                │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  检测到 "guide_button" 模板?                 │
│  是 → press_guide() → 打开 Xbox 指南          │
│  否 → 继续检测                                │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  检测到 "loading" 模板?                      │
│  是 → 等待 2 秒 → 继续检测                    │
│  否 → 继续检测                                │
└─────────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────┐
│  检测到 "error_dialog" 模板?                 │
│  是 → press_b() → 关闭错误对话框              │
│  否 → 睡眠 100ms → 继续检测                  │
└─────────────────────────────────────────────┘
```

### 9.4 Xbox 界面模板列表

需要在 `templates/xbox/` 目录下准备以下界面模板图片：

| 模板名             | 文件                  | 对应操作          | 匹配场景    |
| --------------- | ------------------- | ------------- | ------- |
| pause\_menu     | pause\_menu.png     | 按 Start 暂停/继续 | GAMING  |
| confirm\_dialog | confirm\_dialog.png | 按 A 确认        | GAMING  |
| back\_button    | back\_button.png    | 按 B 返回        | GAMING  |
| guide\_button   | guide\_button.png   | 按 Xbox 按钮     | GENERAL |
| loading         | loading.png         | 等待加载完成        | GAMING  |
| error\_dialog   | error\_dialog.png   | 按 B 关闭        | GAMING  |
| a\_button       | a\_button.png       | 按 A           | GAMING  |
| b\_button       | b\_button.png       | 按 B           | GAMING  |

### 9.5 模板制作规范

1. **图片格式**：PNG 或 BMP
2. **推荐分辨率**：1280x720 或 1920x1080
3. **命名规范**：使用下划线分隔，如 `pause_menu.png`
4. **匹配阈值**：置信度 > 0.8 时认为匹配成功
5. **模板来源**：从 Xbox 实际界面截图获取

### 9.6 使用示例

```python
import asyncio
import logging
from core.scene_matcher import SceneBasedMatcher, Scene
from core.template_matcher import TemplateMatcher
from core.gamepad_automation import XboxGameAutomation

logging.basicConfig(level=logging.INFO)


async def main():
    template_matcher = TemplateMatcher()
    await template_matcher.load_templates("./templates/xbox")

    from core.ocr_text_matcher import OCRTextMatcher
    ocr_matcher = OCRTextMatcher()
    await ocr_matcher.initialize(use_gpu=True)

    scene_matcher = SceneBasedMatcher(template_matcher, ocr_matcher)

    def capture_frame():
        import numpy as np
        return np.zeros((720, 1280, 3), dtype=np.uint8)

    automation = XboxGameAutomation(
        scene_matcher=scene_matcher,
        frame_capture_func=capture_frame,
        joystick_id=0
    )

    await automation.start()
    await asyncio.sleep(60)
    await automation.stop()


if __name__ == "__main__":
    asyncio.run(main())
```

***

## 十五、游戏账号管理与轮询服务

游戏账号轮询服务是 Python Agent 的核心组件，负责管理游戏账号的分配、轮换和次数限制。

### 10.1 GameAccountRotationService 类设计

```python
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


@dataclass
class GameAccount:
    """游戏账号数据类"""
    id: int
    name: str
    email: str
    password: str
    priority: int = 0
    daily_max_matches: int = 10
    today_match_count: int = 0
    locked_xbox_id: Optional[str] = None
    last_played_at: Optional[datetime] = None
    timezone: str = "Asia/Shanghai"


@dataclass
class RotationResult:
    """轮询结果"""
    selected_account: Optional[GameAccount]
    reason: str
    skipped_accounts: List[int] = field(default_factory=list)


class GameAccountRotationService:
    """
    游戏账号轮询服务

    职责：
    - 管理游戏账号的分配
    - 按优先级选择账号
    - 检查次数限制
    - 处理账号锁定
    - 每日重置计数
    """

    def __init__(self, accounts: List[GameAccount]):
        self.accounts = sorted(accounts, key=lambda a: (a.priority, a.id))
        self.current_index = 0
        self._reset_timezone()

    def _reset_timezone(self) -> None:
        """重置时区信息"""
        self.user_timezone = timezone(self.accounts[0].timezone if self.accounts else "UTC")

    def select_next_account(self, current_xbox_id: Optional[str] = None) -> RotationResult:
        """
        选择下一个可用的游戏账号

        Args:
            current_xbox_id: 当前 Xbox 主机 ID（用于检查锁定状态）

        Returns:
            RotationResult: 包含选中的账号或 None
        """
        skipped = []

        for attempt in range(len(self.accounts)):
            account = self.accounts[self.current_index]

            if not self._is_account_available(account, current_xbox_id):
                skipped.append(account.id)
                self._advance_index()
                continue

            self._advance_index()
            logger.info(f"选中游戏账号: {account.name} (ID: {account.id})")
            return RotationResult(
                selected_account=account,
                reason="available",
                skipped_accounts=skipped
            )

        logger.warning("没有可用的游戏账号")
        return RotationResult(
            selected_account=None,
            reason="no_available_account",
            skipped_accounts=skipped
        )

    def _is_account_available(self, account: GameAccount, current_xbox_id: Optional[str]) -> bool:
        """检查账号是否可用"""
        if account.today_match_count >= account.daily_max_matches:
            logger.debug(f"账号 {account.name} 已达今日上限: {account.today_match_count}/{account.daily_max_matches}")
            return False

        if account.locked_xbox_id is not None and account.locked_xbox_id != current_xbox_id:
            logger.debug(f"账号 {account.name} 被锁定在 Xbox: {account.locked_xbox_id}")
            return False

        return True

    def _advance_index(self) -> None:
        """ advance index with wrap-around """
        self.current_index = (self.current_index + 1) % len(self.accounts)

    def get_rotation_order(self) -> List[GameAccount]:
        """获取轮询顺序列表（按优先级排序）"""
        return self.accounts.copy()

    def should_switch_account(self, current_account: GameAccount, current_xbox_id: str) -> bool:
        """
        判断是否需要切换账号

        Returns:
            True if should switch, False otherwise
        """
        if current_account.today_match_count >= current_account.daily_max_matches:
            logger.info(f"账号 {current_account.name} 已达上限，切换账号")
            return True

        if current_account.locked_xbox_id is not None and current_account.locked_xbox_id != current_xbox_id:
            logger.info(f"账号 {current_account.name} 被其他 Xbox 占用，切换账号")
            return True

        return False

    def reset_daily_counters(self, account_ids: Optional[List[int]] = None) -> None:
        """
        重置每日计数器

        Args:
            account_ids: 指定要重置的账号 ID 列表，None 表示重置所有
        """
        now = datetime.now(self.user_timezone)
        current_hour = now.hour

        reset_hour = 4
        if current_hour < reset_hour:
            logger.info("重置时间未到，跳过")
            return

        for account in self.accounts:
            if account_ids and account.id not in account_ids:
                continue

            if account.today_match_count > 0:
                logger.info(f"重置账号 {account.name} 的今日计数: {account.today_match_count} -> 0")
                account.today_match_count = 0

        logger.info("每日计数器重置完成")

    def lock_account(self, account_id: int, xbox_id: str) -> bool:
        """锁定账号到指定 Xbox"""
        account = self._find_account(account_id)
        if account:
            account.locked_xbox_id = xbox_id
            logger.info(f"账号 {account.name} 已锁定到 Xbox: {xbox_id}")
            return True
        return False

    def unlock_account(self, account_id: int) -> bool:
        """解锁账号"""
        account = self._find_account(account_id)
        if account:
            account.locked_xbox_id = None
            logger.info(f"账号 {account.name} 已解锁")
            return True
        return False

    def _find_account(self, account_id: int) -> Optional[GameAccount]:
        """根据 ID 查找账号"""
        for account in self.accounts:
            if account.id == account_id:
                return account
        return None

    def increment_match_count(self, account_id: int) -> bool:
        """增加比赛计数"""
        account = self._find_account(account_id)
        if account:
            account.today_match_count += 1
            account.last_played_at = datetime.now(self.user_timezone)
            logger.debug(f"账号 {account.name} 比赛计数: {account.today_match_count}")
            return True
        return False
```

### 10.2 账号选择算法

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         游戏账号选择算法                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  输入: 当前 Xbox ID, 游戏账号列表                                           │
│                                                                             │
│  1. 【按优先级排序】                                                        │
│     - 先按 priority ASC (数字越小越优先)                                    │
│     - 再按 id ASC (同等优先级按创建顺序)                                    │
│                                                                             │
│  2. 【检查每个账号】                                                        │
│     │                                                                      │
│     ├── 今日次数 < daily_max_matches?                                      │
│     │    ├── 否 → 跳过 (已达上限)                                           │
│     │    └── 是 → 继续检查                                                  │
│     │                                                                      │
│     ├── locked_xbox_id == null?                                            │
│     │    ├── 是 → 可用                                                      │
│     │    └── 否 → locked_xbox_id == current_xbox_id?                       │
│     │         ├── 是 → 可用 (当前 Xbox)                                    │
│     │         └── 否 → 跳过 (被其他 Xbox 占用)                              │
│                                                                             │
│  3. 【返回结果】                                                            │
│     - 找到可用账号 → 返回账号                                                │
│     - 未找到 → 返回 None                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.3 每日重置机制

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


class DailyResetScheduler:
    """每日重置定时任务"""

    def __init__(self, rotation_service: GameAccountRotationService):
        self.rotation_service = rotation_service
        self.scheduler = AsyncIOScheduler()

    def start(self, hour: int = 4, minute: int = 0) -> None:
        """
        启动每日重置定时任务

        Args:
            hour: 重置小时 (默认 4:00)
            minute: 重置分钟
        """
        self.scheduler.add_job(
            self.rotation_service.reset_daily_counters,
            CronTrigger(hour=hour, minute=minute),
            id="daily_reset",
            name="每日游戏账号计数器重置",
            replace_existing=True
        )
        self.scheduler.start()
        logger.info(f"每日重置任务已启动: {hour:02d}:{minute:02d}")

    def stop(self) -> None:
        """停止定时任务"""
        self.scheduler.shutdown()
        logger.info("每日重置任务已停止")
```

### 10.4 Xbox 账号切换流程

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        Xbox 账号切换流程                                     │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  【切换触发条件】                                                            │
│  - 当前账号今日次数已满                                                      │
│  - 当前账号被其他 Xbox 占用                                                  │
│  - 商户手动切换                                                              │
│                                                                             │
│  【步骤 1: 登出当前账号】                                                    │
│                                                                             │
│  1. 检测 Xbox 主界面                                                        │
│  2. 按 B 返回到 Xbox Guide                                                 │
│  3. 选择 "Sign out" 或 "注销"                                               │
│  4. 确认登出                                                                │
│                                                                             │
│  【步骤 2: 选择新账号】                                                      │
│                                                                             │
│  1. 调用 GameAccountRotationService.select_next_account()                   │
│  2. 检查账号可用性                                                           │
│  3. 返回可用的游戏账号                                                       │
│                                                                             │
│  【步骤 3: 登录新账号】                                                      │
│                                                                             │
│  1. 在 Xbox 登录界面输入邮箱                                                │
│  2. 输入密码                                                                 │
│  3. 确认登录                                                                │
│  4. 等待进入主界面                                                          │
│                                                                             │
│  【步骤 4: 更新锁定状态】                                                    │
│                                                                             │
│  1. 调用 lock_account(account_id, xbox_id)                                 │
│  2. 更新 today_match_count = 0                                             │
│  3. 更新 last_played_at                                                    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 10.5 轮询配置参数

| 参数                  | 默认值 | 说明           |
| ------------------- | --- | ------------ |
| daily\_max\_matches | 10  | 每个账号每日最大比赛次数 |
| default\_priority   | 0   | 默认优先级（0=不设置） |
| reset\_hour         | 4   | 每日重置小时       |
| reset\_minute       | 0   | 每日重置分钟       |
| max\_retry          | 3   | 选择账号最大重试次数   |
| lock\_timeout       | 300 | 账号锁定超时（秒）    |

### 9.7 高级操作

#### 9.7.1 复合操作

```python
async def navigate_to_game_settings(self) -> None:
    self.gamepad.press_guide()
    await asyncio.sleep(1)
    self.gamepad.press_b()
    await asyncio.sleep(0.5)
    self.gamepad.move_left_stick(0, 1, duration=0.5)
    await asyncio.sleep(0.5)
    self.gamepad.press_a()

async def confirm_and_continue(self) -> None:
    self.gamepad.press_a()
    await asyncio.sleep(2)
    self.gamepad.press_a()
    await asyncio.sleep(1)

async def cancel_and_back(self) -> None:
    self.gamepad.press_b()
    await asyncio.sleep(0.5)
    self.gamepad.press_b()
    await asyncio.sleep(1)
```

#### 9.7.2 摇杆精确移动

```python
def move_to_position(self, direction: str, steps: int = 5) -> None:
    directions = {
        "up": (0, -1),
        "down": (0, 1),
        "left": (-1, 0),
        "right": (1, 0),
    }

    if direction not in directions:
        return

    dx, dy = directions[direction]
    for _ in range(steps):
        self.gamepad.move_left_stick(dx, dy, duration=0.1)
        time.sleep(0.15)
```

### 7.3 Vue 前端

```
frontend/
├── src/
│   ├── api/
│   │   ├── streaming.js
│   │   ├── game.js
│   │   ├── agent.js
│   │   └── task.js
│   │
│   ├── components/
│   │   ├── StreamingAccountList.vue
│   │   ├── GameAccountTree.vue
│   │   ├── AgentStatus.vue
│   │   └── TaskTimeline.vue
│   │
│   ├── views/
│   │   ├── StreamingAccount.vue
│   │   ├── GameAccount.vue
│   │   ├── Agent.vue
│   │   ├── TaskHistory.vue
│   │   └── Statistics.vue
│   │
│   ├── stores/
│   │   └── websocket.js     # WebSocket 状态管理
│   │
│   └── router/
│       └── index.js
│
└── package.json
```

***

## 十六、前端Vue 3组件详细设计

### 12.1 前端技术栈与组件

| 技术               | 说明                                | 版本   |
| ---------------- | --------------------------------- | ---- |
| **Vue 3**        | 渐进式JavaScript框架，支持Composition API | 3.4+ |
| **Element Plus** | 基于Vue 3的组件库，提供丰富的UI组件             | 2.5+ |
| **Pinia**        | Vue 3官方推荐的状态管理库                   | 2.1+ |
| **Vue Router 4** | Vue 3官方路由管理                       | 4.2+ |
| **Vite**         | 新一代前端构建工具，开发体验优秀                  | 5.0+ |
| **Axios**        | HTTP请求库，用于API调用                   | 1.6+ |

### 12.2 核心组件结构（Vue 3目录规范）

```
src/
├── views/                    # 页面级组件
│   ├── StreamingAccount.vue  # 串流账号管理
│   ├── GameAccount.vue       # 游戏账号管理
│   ├── Agent.vue             # Agent管理
│   ├── TaskHistory.vue       # 任务历史
│   └── Statistics.vue        # 数据统计
│
├── components/               # 公共组件
│   ├── VideoMonitor.vue      # 视频监控组件
│   ├── LogViewer.vue          # 日志查看器
│   ├── StreamingAccountList.vue
│   ├── GameAccountTree.vue
│   ├── AgentStatus.vue
│   └── TaskTimeline.vue
│
├── stores/                   # Pinia状态管理
│   ├── account.js            # 账号状态管理
│   ├── agent.js              # Agent状态管理
│   └── websocket.js          # WebSocket连接状态
│
├── api/                      # API接口封装
│   ├── streaming.js          # 串流账号API
│   ├── game.js               # 游戏账号API
│   ├── agent.js              # Agent API
│   └── task.js               # 任务API
│
├── utils/                    # 工具函数
│   ├── request.js            # Axios封装
│   └── websocket.js          # WebSocket工具
│
└── router/
    └── index.js              # 路由配置
```

### 12.3 状态管理方案（Pinia Stores）

#### 12.3.1 account.js - 账号状态管理

```javascript
// stores/account.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getStreamingAccounts, getGameAccounts, updateAccountStatus } from '@/api/streaming'

export const useAccountStore = defineStore('account', () => {
  const streamingAccounts = ref([])
  const gameAccounts = ref([])
  const loading = ref(false)
  const currentStreamingId = ref(null)

  const activeStreamingAccounts = computed(() =>
    streamingAccounts.value.filter(a => a.status !== 'idle')
  )

  const accountsByStreaming = computed(() => {
    const map = new Map()
    for (const ga of gameAccounts.value) {
      const list = map.get(ga.streaming_id) || []
      list.push(ga)
      map.set(ga.streaming_id, list)
    }
    return map
  })

  async function fetchStreamingAccounts() {
    loading.value = true
    try {
      const res = await getStreamingAccounts()
      streamingAccounts.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function fetchGameAccounts(streamingId) {
    loading.value = true
    try {
      const res = await getGameAccounts(streamingId)
      gameAccounts.value = res.data
    } finally {
      loading.value = false
    }
  }

  async function setAccountStatus(id, status) {
    await updateAccountStatus(id, { status })
    const account = streamingAccounts.value.find(a => a.id === id)
    if (account) {
      account.status = status
    }
  }

  function setCurrentStreaming(id) {
    currentStreamingId.value = id
  }

  return {
    streamingAccounts,
    gameAccounts,
    loading,
    currentStreamingId,
    activeStreamingAccounts,
    accountsByStreaming,
    fetchStreamingAccounts,
    fetchGameAccounts,
    setAccountStatus,
    setCurrentStreaming
  }
})
```

#### 12.3.2 agent.js - Agent状态管理

```javascript
// stores/agent.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getAgents, registerAgent, removeAgent } from '@/api/agent'

export const useAgentStore = defineStore('agent', () => {
  const agents = ref([])
  const loading = ref(false)
  const selectedAgentId = ref(null)

  const onlineAgents = computed(() =>
    agents.value.filter(a => a.status === 'online')
  )

  const agentById = computed(() => (id) =>
    agents.value.find(a => a.id === id)
  )

  async function fetchAgents() {
    loading.value = true
    try {
      const res = await getAgents()
      agents.value = res.data
    } finally {
      loading.value = false
    }
  }

  function updateAgentHeartbeat(agentId, heartbeat) {
    const agent = agents.value.find(a => a.id === agentId)
    if (agent) {
      agent.last_heartbeat = heartbeat
      agent.status = 'online'
    }
  }

  function addAgent(agent) {
    const exists = agents.value.find(a => a.id === agent.id)
    if (!exists) {
      agents.value.push(agent)
    }
  }

  function removeAgentById(id) {
    const index = agents.value.findIndex(a => a.id === id)
    if (index !== -1) {
      agents.value.splice(index, 1)
    }
  }

  function setSelectedAgent(id) {
    selectedAgentId.value = id
  }

  return {
    agents,
    loading,
    selectedAgentId,
    onlineAgents,
    agentById,
    fetchAgents,
    updateAgentHeartbeat,
    addAgent,
    removeAgentById,
    setSelectedAgent
  }
})
```

#### 12.3.3 websocket.js - WebSocket连接状态

```javascript
// stores/websocket.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useWebSocketStore = defineStore('websocket', () => {
  const connected = ref(false)
  const connecting = ref(false)
  const error = ref(null)
  const messages = ref([])
  const subscribers = new Map()

  const isConnected = computed(() => connected.value)

  function connect(url) {
    if (connected.value || connecting.value) return

    connecting.value = true
    error.value = null

    const ws = new WebSocket(url)

    ws.onopen = () => {
      connected.value = true
      connecting.value = false
      console.log('[WebSocket] Connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        messages.value.push(data)
        notifySubscribers(data.type, data)
      } catch (e) {
        console.error('[WebSocket] Parse error:', e)
      }
    }

    ws.onerror = (e) => {
      error.value = 'WebSocket connection error'
      connecting.value = false
      console.error('[WebSocket] Error:', e)
    }

    ws.onclose = () => {
      connected.value = false
      connecting.value = false
      console.log('[WebSocket] Disconnected')
    }

    return ws
  }

  function disconnect() {
    if (ws) {
      ws.close()
    }
    connected.value = false
    connecting.value = false
  }

  function subscribe(eventType, callback) {
    if (!subscribers.has(eventType)) {
      subscribers.set(eventType, [])
    }
    subscribers.get(eventType).push(callback)

    return () => {
      const callbacks = subscribers.get(eventType)
      const index = callbacks.indexOf(callback)
      if (index !== -1) {
        callbacks.splice(index, 1)
      }
    }
  }

  function notifySubscribers(eventType, data) {
    const callbacks = subscribers.get(eventType) || []
    callbacks.forEach(cb => cb(data))
  }

  function send(data) {
    if (connected.value && ws) {
      ws.send(JSON.stringify(data))
    }
  }

  let ws = null

  return {
    connected,
    connecting,
    error,
    messages,
    isConnected,
    connect,
    disconnect,
    subscribe,
    send
  }
})
```

### 12.4 WebSocket封装

```javascript
// utils/websocket.js
class WebSocketClient {
  constructor(url, options = {}) {
    this.url = url
    this.options = {
      reconnectInterval: 3000,
      maxReconnectAttempts: 10,
      heartbeatInterval: 30000,
      ...options
    }
    this.ws = null
    this.reconnectAttempts = 0
    this.reconnectTimer = null
    this.heartbeatTimer = null
    this.listeners = new Map()
  }

  connect() {
    return new Promise((resolve, reject) => {
      try {
        this.ws = new WebSocket(this.url)

        this.ws.onopen = () => {
          console.log('[WebSocket] Connected to:', this.url)
          this.reconnectAttempts = 0
          this.startHeartbeat()
          this.emit('connected')
          resolve()
        }

        this.ws.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data)
            this.handleMessage(data)
          } catch (e) {
            console.error('[WebSocket] Parse error:', e)
          }
        }

        this.ws.onerror = (error) => {
          console.error('[WebSocket] Error:', error)
          this.emit('error', error)
          reject(error)
        }

        this.ws.onclose = () => {
          console.log('[WebSocket] Connection closed')
          this.stopHeartbeat()
          this.emit('disconnected')
          this.scheduleReconnect()
        }
      } catch (e) {
        reject(e)
      }
    })
  }

  handleMessage(data) {
    const { type, payload } = data
    this.emit(type, payload)
    this.emit('message', data)
  }

  scheduleReconnect() {
    if (this.reconnectAttempts >= this.options.maxReconnectAttempts) {
      console.error('[WebSocket] Max reconnect attempts reached')
      this.emit('max_reconnect_attempts')
      return
    }

    const delay = this.options.reconnectInterval * Math.pow(2, this.reconnectAttempts)
    console.log(`[WebSocket] Reconnecting in ${delay}ms...`)

    this.reconnectTimer = setTimeout(() => {
      this.reconnectAttempts++
      this.connect()
    }, delay)
  }

  startHeartbeat() {
    this.heartbeatTimer = setInterval(() => {
      this.send({ type: 'ping', timestamp: Date.now() })
    }, this.options.heartbeatInterval)
  }

  stopHeartbeat() {
    if (this.heartbeatTimer) {
      clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  send(data) {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data))
    } else {
      console.warn('[WebSocket] Cannot send, not connected')
    }
  }

  on(event, callback) {
    if (!this.listeners.has(event)) {
      this.listeners.set(event, [])
    }
    this.listeners.get(event).push(callback)
  }

  off(event, callback) {
    if (!this.listeners.has(event)) return
    const callbacks = this.listeners.get(event)
    const index = callbacks.indexOf(callback)
    if (index !== -1) {
      callbacks.splice(index, 1)
    }
  }

  emit(event, data) {
    if (!this.listeners.has(event)) return
    this.listeners.get(event).forEach(cb => cb(data))
  }

  disconnect() {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer)
    }
    this.stopHeartbeat()
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }
}

export default WebSocketClient
```

### 12.5 核心Vue组件详细设计

#### 12.5.1 VideoMonitor.vue - 视频监控组件

```vue
<!-- components/VideoMonitor.vue -->
<template>
  <div class="video-monitor">
    <div class="video-header">
      <span class="status-indicator" :class="connectionStatus"></span>
      <span class="instance-id">实例: {{ instanceId }}</span>
      <el-button size="small" @click="toggleConnection">
        {{ isConnected ? '断开' : '连接' }}
      </el-button>
    </div>
    <div class="video-container" ref="containerRef">
      <img
        v-if="isConnected"
        :src="videoUrl"
        class="video-stream"
        alt="Video Stream"
      />
      <div v-else class="video-placeholder">
        <el-icon size="48"><VideoCamera /></el-icon>
        <span>未连接</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { VideoCamera } from '@element-plus/icons-vue'

const props = defineProps({
  instanceId: {
    type: String,
    required: true
  },
  agentHost: {
    type: String,
    required: true
  },
  agentPort: {
    type: Number,
    required: true
  }
})

const emit = defineEmits(['onConnect', 'onDisconnect', 'onError'])

const containerRef = ref(null)
const isConnected = ref(false)
const connectionError = ref(null)

const connectionStatus = computed(() => {
  if (connectionError.value) return 'error'
  if (isConnected.value) return 'connected'
  return 'disconnected'
})

const videoUrl = computed(() => {
  return `http://${props.agentHost}:${props.agentPort}/stream/${props.instanceId}`
})

let eventSource = null

function toggleConnection() {
  if (isConnected.value) {
    disconnect()
  } else {
    connect()
  }
}

function connect() {
  disconnect()

  eventSource = new EventSource(
    `http://${props.agentHost}:${props.agentPort}/stream/${props.instanceId}/events`
  )

  eventSource.onopen = () => {
    isConnected.value = true
    connectionError.value = null
    emit('onConnect', { instanceId: props.instanceId })
  }

  eventSource.onerror = (error) => {
    connectionError.value = error
    isConnected.value = false
    emit('onError', { instanceId: props.instanceId, error })
  }

  eventSource.onmessage = (event) => {
    console.log('[VideoMonitor] Event:', event.data)
  }
}

function disconnect() {
  if (eventSource) {
    eventSource.close()
    eventSource = null
  }
  isConnected.value = false
  emit('onDisconnect', { instanceId: props.instanceId })
}

onMounted(() => {
  console.log('[VideoMonitor] Mounted:', props.instanceId)
})

onUnmounted(() => {
  disconnect()
})

watch([() => props.agentHost, () => props.agentPort], () => {
  if (isConnected.value) {
    disconnect()
  }
})
</script>

<style scoped>
.video-monitor {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-bg-color);
}

.video-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
}

.status-indicator {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.status-indicator.connected {
  background: var(--el-color-success);
  box-shadow: 0 0 8px var(--el-color-success);
}

.status-indicator.disconnected {
  background: var(--el-color-info);
}

.status-indicator.error {
  background: var(--el-color-danger);
  box-shadow: 0 0 8px var(--el-color-danger);
}

.instance-id {
  flex: 1;
  font-family: monospace;
  font-size: 13px;
}

.video-container {
  position: relative;
  width: 100%;
  aspect-ratio: 16 / 9;
  background: #000;
}

.video-stream {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.video-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  color: var(--el-text-color-secondary);
  gap: 12px;
}
</style>
```

#### 12.5.2 LogViewer.vue - 日志查看器

```vue
<!-- components/LogViewer.vue -->
<template>
  <div class="log-viewer">
    <div class="log-header">
      <span class="log-title">日志监控</span>
      <div class="log-filters">
        <el-radio-group v-model="levelFilter" size="small">
          <el-radio-button value="ALL">全部</el-radio-button>
          <el-radio-button value="DEBUG">DEBUG</el-radio-button>
          <el-radio-button value="INFO">INFO</el-radio-button>
          <el-radio-button value="WARN">WARN</el-radio-button>
          <el-radio-button value="ERROR">ERROR</el-radio-button>
        </el-radio-group>
        <el-button size="small" @click="clearLogs">清空</el-button>
        <el-button size="small" @click="toggleAutoScroll">
          {{ autoScroll ? '暂停滚动' : '自动滚动' }}
        </el-button>
      </div>
    </div>
    <div class="log-content" ref="logContainerRef">
      <div
        v-for="(log, index) in filteredLogs"
        :key="index"
        class="log-entry"
        :class="`log-${log.level.toLowerCase()}`"
      >
        <span class="log-time">{{ formatTime(log.timestamp) }}</span>
        <span class="log-level">{{ log.level }}</span>
        <span class="log-message">{{ log.message }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'

const props = defineProps({
  logs: {
    type: Array,
    default: () => []
  },
  level: {
    type: String,
    default: 'ALL'
  }
})

const logContainerRef = ref(null)
const levelFilter = ref(props.level)
const autoScroll = ref(true)

const filteredLogs = computed(() => {
  if (levelFilter.value === 'ALL') {
    return props.logs
  }
  return props.logs.filter(log => log.level === levelFilter.value)
})

function formatTime(timestamp) {
  const date = new Date(timestamp)
  return date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    fractionalSecondDigits: 3
  })
}

function clearLogs() {
  props.logs.length = 0
}

function toggleAutoScroll() {
  autoScroll.value = !autoScroll.value
}

function scrollToBottom() {
  if (autoScroll.value && logContainerRef.value) {
    nextTick(() => {
      logContainerRef.value.scrollTop = logContainerRef.value.scrollHeight
    })
  }
}

watch(() => props.logs.length, () => {
  scrollToBottom()
})
</script>

<style scoped>
.log-viewer {
  display: flex;
  flex-direction: column;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
  background: var(--el-bg-color);
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}

.log-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--el-fill-color-light);
  border-bottom: 1px solid var(--el-border-color);
}

.log-title {
  font-weight: 600;
}

.log-filters {
  display: flex;
  align-items: center;
  gap: 12px;
}

.log-content {
  flex: 1;
  max-height: 400px;
  overflow-y: auto;
  padding: 8px;
  background: #1e1e1e;
}

.log-entry {
  display: flex;
  gap: 12px;
  padding: 4px 8px;
  border-radius: 4px;
  line-height: 1.5;
}

.log-entry:hover {
  background: rgba(255, 255, 255, 0.05);
}

.log-time {
  color: #888;
  flex-shrink: 0;
}

.log-level {
  flex-shrink: 0;
  font-weight: 600;
  min-width: 50px;
}

.log-debug .log-level {
  color: #888;
}

.log-info .log-level {
  color: #4fc3f7;
}

.log-warn .log-level {
  color: #ffb74d;
}

.log-error .log-level {
  color: #ef5350;
}

.log-message {
  color: #e0e0e0;
  word-break: break-all;
}
</style>
```

### 12.6 API接口封装示例

```javascript
// api/streaming.js
import request from '@/utils/request'

export function getStreamingAccounts() {
  return request({
    url: '/api/streaming-accounts',
    method: 'get'
  })
}

export function getStreamingAccount(id) {
  return request({
    url: `/api/streaming-accounts/${id}`,
    method: 'get'
  })
}

export function createStreamingAccount(data) {
  return request({
    url: '/api/streaming-accounts',
    method: 'post',
    data
  })
}

export function updateStreamingAccount(id, data) {
  return request({
    url: `/api/streaming-accounts/${id}`,
    method: 'put',
    data
  })
}

export function deleteStreamingAccount(id) {
  return request({
    url: `/api/streaming-accounts/${id}`,
    method: 'delete'
  })
}

export function updateAccountStatus(id, status) {
  return request({
    url: `/api/streaming-accounts/${id}/status`,
    method: 'patch',
    data: status
  })
}
```

### 12.7 路由配置示例

```javascript
// router/index.js
import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    redirect: '/streaming'
  },
  {
    path: '/streaming',
    name: 'StreamingAccount',
    component: () => import('@/views/StreamingAccount.vue'),
    meta: { title: '串流账号' }
  },
  {
    path: '/game',
    name: 'GameAccount',
    component: () => import('@/views/GameAccount.vue'),
    meta: { title: '游戏账号' }
  },
  {
    path: '/agents',
    name: 'Agent',
    component: () => import('@/views/Agent.vue'),
    meta: { title: 'Agent管理' }
  },
  {
    path: '/tasks',
    name: 'TaskHistory',
    component: () => import('@/views/TaskHistory.vue'),
    meta: { title: '任务历史' }
  },
  {
    path: '/statistics',
    name: 'Statistics',
    component: () => import('@/views/Statistics.vue'),
    meta: { title: '数据统计' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - XStreaming管理平台`
  }
  next()
})

export default router
```

***

## 十七、实施优先级

### 第一阶段：基础搭建

1. MySQL 数据库创建（SQL 脚本 + 数据库用户创建）
2. Java Spring Boot 项目初始化
3. 基础 CRUD API 开发
4. Vue 项目初始化
5. **数据库安全配置（创建复杂密码、使用环境变量）**

### 第二阶段：核心功能

1. 串流账号管理完整功能
2. 游戏账号管理
3. Agent 注册和心跳机制
4. 启动/暂停/停止自动化

### 第三阶段：实时监控

1. WebSocket 实时状态推送
2. 前端状态展示优化
3. 任务历史和统计

### 第四阶段：自动化集成

1. Agent 与自动化项目对接
2. 多窗口自动化支持
3. 游戏账号切换逻辑

***

## 十八、SQL 脚本

```sql
-- =====================================================
-- XStreaming 管理平台 - 数据库初始化脚本
-- =====================================================

-- 创建数据库用户（需要 DBA 或具有 CREATE USER 权限的账号执行）
-- 密码要求：至少16位，包含大小写字母、数字和特殊字符
-- 密码示例：XStr3@m$2024!DB#Sec
CREATE USER IF NOT EXISTS 'xstreaming_app'@'%' IDENTIFIED BY 'XStr3@m$2024!DB#Sec';

-- 创建数据库
CREATE DATABASE IF NOT EXISTS xstreaming_manager
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

-- 授权
GRANT ALL PRIVILEGES ON xstreaming_manager.* TO 'xstreaming_app'@'%';
FLUSH PRIVILEGES;

USE xstreaming_manager;

-- =====================================================
-- 表结构
-- =====================================================

-- 商户表
CREATE TABLE IF NOT EXISTS merchant (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    phone VARCHAR(20) NOT NULL UNIQUE COMMENT '手机号',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码',
    name VARCHAR(100) COMMENT '商户名称',
    status ENUM('active', 'expired', 'suspended') DEFAULT 'active' COMMENT '状态',
    expire_time DATETIME COMMENT '账号过期时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_phone (phone),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商户表';

-- 商户用户表（商户子账号）
CREATE TABLE IF NOT EXISTS merchant_user (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    username VARCHAR(50) NOT NULL COMMENT '用户名',
    phone VARCHAR(20) NOT NULL COMMENT '手机号',
    password_hash VARCHAR(255) NOT NULL COMMENT '密码哈希',
    role ENUM('owner', 'admin', 'operator') DEFAULT 'operator' COMMENT '角色',
    status ENUM('active', 'disabled') DEFAULT 'active' COMMENT '状态',
    last_login_at DATETIME COMMENT '最后登录时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_username (username),
    UNIQUE KEY uk_phone (phone),
    INDEX idx_merchant_id (merchant_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='商户用户表';

-- 模板表（商户维度的自动化模板）
CREATE TABLE IF NOT EXISTS template (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    category VARCHAR(100) NOT NULL COMMENT '模板分类',
    name VARCHAR(100) NOT NULL COMMENT '模板名称',
    version VARCHAR(20) NOT NULL COMMENT '版本号',
    content_type ENUM('image', 'json', 'script') NOT NULL COMMENT '内容类型',
    file_path VARCHAR(500) COMMENT '文件路径',
    file_size BIGINT COMMENT '文件大小',
    checksum VARCHAR(64) COMMENT '文件校验和',
    is_current TINYINT(1) DEFAULT 1 COMMENT '是否为当前版本',
    changelog TEXT COMMENT '更新日志',
    created_by BIGINT COMMENT '创建人',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_category_name (category, name),
    INDEX idx_is_current (is_current),
    UNIQUE KEY uk_merchant_category_name_version (merchant_id, category, name, version)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='模板表';

-- 串流账号表
CREATE TABLE IF NOT EXISTS streaming_account (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    merchant_id BIGINT NOT NULL COMMENT '所属商户',
    name VARCHAR(100) NOT NULL COMMENT '账号名称',
    email VARCHAR(255) NOT NULL COMMENT '邮箱',
    password_encrypted VARCHAR(512) COMMENT '加密密码',
    auth_code VARCHAR(512) COMMENT '认证码',
    status ENUM('idle', 'ready', 'running', 'paused', 'error') DEFAULT 'idle' COMMENT '状态',
    last_heartbeat DATETIME COMMENT '最后心跳时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_email (email),
    INDEX idx_merchant_id (merchant_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='串流账号表';

-- 游戏账号表
CREATE TABLE IF NOT EXISTS game_account (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    streaming_id BIGINT NOT NULL COMMENT '所属串流账号ID',
    name VARCHAR(100) NOT NULL COMMENT '游戏账号名称',
    xbox_gamertag VARCHAR(50) NOT NULL COMMENT 'Xbox Gamertag',
    xbox_live_email VARCHAR(255) COMMENT 'Xbox Live 邮箱（用于账号切换）',
    xbox_live_password_encrypted VARCHAR(512) COMMENT '密码加密存储（AES）',
    locked_xbox_id BIGINT COMMENT '当前登录的Xbox主机ID（NULL=未登录）',
    is_primary TINYINT(1) DEFAULT 0 COMMENT '是否主账号',
    is_active TINYINT(1) DEFAULT 1 COMMENT '是否启用',
    priority INT DEFAULT 0 COMMENT '优先级（数字越小越优先，0=不设置按列表顺序）',
    daily_match_limit INT DEFAULT 3 COMMENT '每日比赛次数限制',
    today_match_count INT DEFAULT 0 COMMENT '今日已完成比赛数',
    total_match_count INT DEFAULT 0 COMMENT '历史总比赛数',
    last_used_at DATETIME COMMENT '最后使用时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_streaming_id (streaming_id),
    INDEX idx_locked_xbox_id (locked_xbox_id),
    UNIQUE KEY uk_gamertag (xbox_gamertag),
    UNIQUE KEY uk_email (xbox_live_email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='游戏账号表';

-- Agent 实例表
CREATE TABLE IF NOT EXISTS agent_instance (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    agent_id VARCHAR(64) NOT NULL UNIQUE COMMENT 'Agent唯一标识',
    host VARCHAR(255) NOT NULL COMMENT '主机地址',
    port INT NOT NULL COMMENT '端口',
    status ENUM('online', 'offline', 'busy') DEFAULT 'offline' COMMENT '状态',
    current_streaming_id BIGINT COMMENT '当前执行的串流账号ID',
    current_task_id BIGINT COMMENT '当前任务ID',
    last_heartbeat DATETIME COMMENT '最后心跳时间',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_status (status),
    INDEX idx_current_streaming_id (current_streaming_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='Agent实例表';

-- 自动化任务表
CREATE TABLE IF NOT EXISTS automation_task (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    agent_id BIGINT COMMENT '执行的Agent',
    streaming_id BIGINT NOT NULL COMMENT '串流账号ID',
    game_id BIGINT COMMENT '游戏账号ID',
    task_type ENUM('login', 'stream', 'game_switch', 'custom') NOT NULL COMMENT '任务类型',
    status ENUM('pending', 'running', 'paused', 'completed', 'failed', 'cancelled') DEFAULT 'pending',
    started_at DATETIME COMMENT '开始时间',
    finished_at DATETIME COMMENT '结束时间',
    result JSON COMMENT '执行结果',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_agent_id (agent_id),
    INDEX idx_streaming_id (streaming_id),
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='自动化任务表';

-- 任务统计表
CREATE TABLE IF NOT EXISTS task_statistics (
    id BIGINT PRIMARY KEY COMMENT '主键（雪花ID）',
    streaming_id BIGINT NOT NULL,
    game_id BIGINT,
    stat_date DATE NOT NULL,
    total_tasks INT DEFAULT 0,
    completed_tasks INT DEFAULT 0,
    failed_tasks INT DEFAULT 0,
    total_duration_seconds BIGINT DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_stream_game_date (streaming_id, game_id, stat_date),
    INDEX idx_stat_date (stat_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='任务统计表';

-- =====================================================
-- 初始化测试数据
-- =====================================================

INSERT INTO streaming_account (name, email, password_encrypted, status) VALUES
('测试账号1', 'test1@outlook.com', 'encrypted_pass_1', 'idle'),
('测试账号2', 'test2@outlook.com', 'encrypted_pass_2', 'idle');

INSERT INTO game_account (streaming_id, name, xbox_gamertag, is_primary) VALUES
(1, '主游戏账号', 'PlayerOne', 1),
(1, '副游戏账号', 'PlayerTwo', 0),
(2, '主游戏账号', 'PlayerThree', 1);
```

