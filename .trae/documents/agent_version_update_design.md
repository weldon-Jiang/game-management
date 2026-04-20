# Agent版本更新系统详细设计方案

## 一、系统概述

Agent版本更新系统实现平台管理员向Agent推送版本更新通知，Agent自动检查下载并安装更新的完整流程。

## 二、架构设计

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   平台管理员     │────▶│  Bend Platform   │◀────│  Bend Agent     │
│  (发布版本)      │     │                  │     │                 │
└─────────────────┘     │  - AgentVersion  │     │ - UpdateManager │
                        │  - WebSocket     │     │ - 下载安装包    │
┌─────────────────┐     │  - 消息推送      │     │ - 自动更新      │
│  文件服务器/CDN  │◀────│                  │────▶│                 │
│  (存储安装包)    │     └──────────────────┘     └─────────────────┘
└─────────────────┘
```

## 三、版本更新流程

### 3.1 版本发布流程（平台管理员操作）

1. **准备安装包**
   - 开发团队打包Agent新版本（使用 PyArmor + PyInstaller）
   - 上传安装包到文件服务器/CDN
   - 获取下载URL和MD5校验码

2. **平台发布版本**
   - 管理员登录平台 → Agent版本管理
   - 点击"发布新版本"
   - 填写版本信息：
     - 版本号（如 1.0.1）
     - 下载链接（安装包URL）
     - MD5校验码
     - 更新日志
     - 更新类型（可选更新/强制更新）
     - 重启方式（热更新/需要重启）
     - 最低兼容版本（可选）

3. **发布后状态**
   - `status=0`：未发布（仅保存在平台，Agent不会收到通知）
   - `status=1`：已发布（Agent启动或心跳时会收到通知）

### 3.2 Agent版本检查流程

**触发时机：**
- Agent启动时
- Agent心跳时（每30秒，可配置）
- 管理员主动推送

**检查流程：**
```
Agent                              平台
  │                                 │
  │──── GET /api/agents/version/    │
  │      check?currentVersion=1.0.0  │
  │                                 │
  │◀─── {"hasUpdate": true,         │
  │      "latestVersion": "1.0.1",  │
  │      "downloadUrl": "...",       │
  │      "mandatory": true,          │
  │      "forceRestart": true}       │
  │                                 │
```

### 3.3 主动推送流程（管理员通知Agent）

当平台发布新版本后，管理员可以主动通知所有在线Agent：

**WebSocket消息推送：**
```json
{
  "type": "version_update",
  "data": {
    "version": "1.0.1",
    "downloadUrl": "https://cdn.example.com/agent-1.0.1.exe",
    "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e",
    "changelog": "修复了XX问题",
    "mandatory": true,
    "forceRestart": true
  }
}
```

## 四、数据结构

### 4.1 AgentVersion 表

| 字段 | 类型 | 说明 |
|------|------|------|
| id | VARCHAR(64) | 主键ID |
| version | VARCHAR(32) | 版本号（如1.0.1） |
| download_url | VARCHAR(512) | 下载链接 |
| md5_checksum | VARCHAR(64) | MD5校验码 |
| changelog | TEXT | 更新日志 |
| mandatory | TINYINT | 是否强制更新（0-否，1-是） |
| force_restart | TINYINT | 是否需要重启（0-否，1-是） |
| min_compatible_version | VARCHAR(32) | 最低兼容版本 |
| status | TINYINT | 发布状态（0-未发布，1-已发布） |
| created_at | DATETIME | 创建时间 |
| updated_at | DATETIME | 更新时间 |
| deleted | TINYINT | 软删除标记 |

### 4.2 Agent端版本信息

```python
@dataclass
class UpdateInfo:
    current_version: str      # 当前版本
    latest_version: str       # 最新版本
    download_url: str         # 下载地址
    md5_checksum: str         # MD5校验
    changelog: str            # 更新日志
    mandatory: bool           # 是否强制更新
    force_restart: bool       # 是否需要重启
```

## 五、API接口

### 5.1 Agent端接口

**版本检查**
```
GET /api/agents/version/check?currentVersion=1.0.0
Headers:
  X-Agent-ID: xxxx
  X-Agent-Secret: xxxx

Response:
{
  "code": 0,
  "data": {
    "hasUpdate": true,
    "currentVersion": "1.0.0",
    "latestVersion": "1.0.1",
    "downloadUrl": "https://cdn.example.com/agent-1.0.1.exe",
    "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e",
    "changelog": "修复了XX问题",
    "mandatory": true,
    "forceRestart": true
  }
}
```

**获取最新版本**
```
GET /api/agents/version/latest

Response:
{
  "code": 0,
  "data": {
    "version": "1.0.1",
    "downloadUrl": "...",
    "md5Checksum": "..."
  }
}
```

**获取指定版本下载信息**
```
GET /api/agents/version/download/{version}

Response:
{
  "code": 0,
  "data": {
    "version": "1.0.1",
    "downloadUrl": "https://cdn.example.com/agent-1.0.1.exe",
    "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e"
  }
}
```

### 5.2 平台管理端接口

**创建版本**
```
POST /api/admin/agent-versions
{
  "version": "1.0.1",
  "downloadUrl": "https://cdn.example.com/agent-1.0.1.exe",
  "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e",
  "changelog": "修复了XX问题",
  "mandatory": 1,
  "forceRestart": 1
}
```

**发布版本**
```
POST /api/admin/agent-versions/{id}/publish
```

**取消发布**
```
POST /api/admin/agent-versions/{id}/unpublish
```

**通知所有Agent更新**
```
POST /api/admin/agent-versions/notify-all
```

**通知指定Agent更新**
```
POST /api/admin/agent-versions/notify/{agentId}
```

## 六、WebSocket消息类型

| 消息类型 | 方向 | 说明 |
|---------|------|------|
| version_update | Server → Agent | 版本更新通知 |
| version_update_ack | Agent → Server | 版本通知确认 |
| update_progress | Agent → Server | 更新进度报告 |
| update_completed | Agent → Server | 更新完成报告 |
| update_failed | Agent → Server | 更新失败报告 |

### 6.1 version_update 消息（Server → Agent）

```json
{
  "type": "version_update",
  "data": {
    "version": "1.0.1",
    "downloadUrl": "https://cdn.example.com/agent-1.0.1.exe",
    "md5Checksum": "d41d8cd98f00b204e9800998ecf8427e",
    "changelog": "修复了XX问题",
    "mandatory": true,
    "forceRestart": true,
    "timestamp": 1713441234567
  }
}
```

### 6.2 update_progress 消息（Agent → Server）

```json
{
  "type": "update_progress",
  "data": {
    "version": "1.0.1",
    "stage": "downloading",
    "progress": 45,
    "message": "下载中..."
  }
}
```

### 6.3 update_completed 消息（Agent → Server）

```json
{
  "type": "update_completed",
  "data": {
    "version": "1.0.1",
    "oldVersion": "1.0.0",
    "restartRequired": true
  }
}
```

## 七、Agent更新流程

### 7.1 更新决策流程

```
                    ┌─────────────────┐
                    │  收到更新通知   │
                    └────────┬────────┘
                             │
                    ┌────────▼────────┐
                    │  是否强制更新？  │
                    └────────┬────────┘
                             │
              ┌──────────────┴──────────────┐
              │ YES                         │ NO
    ┌─────────▼─────────┐       ┌──────────▼──────────┐
    │  自动下载安装更新   │       │  记录更新信息，      │
    │  （禁止取消）      │       │  等待用户确认        │
    └─────────┬─────────┘       └──────────┬──────────┘
              │                              │
    ┌─────────▼─────────┐           ┌───────▼───────┐
    │  下载并验证MD5    │           │  用户点击更新  │
    └─────────┬─────────┘           └───────┬───────┘
              │                              │
    ┌─────────▼─────────┐                   │
    │  是否需要重启？     │◀──────────────────┘
    └─────────┬─────────┘
              │
    ┌─────────┴─────────┐
    │YES                │NO
    ▼                   ▼
┌───────────┐     ┌───────────┐
│  热更新    │     │ 替换文件   │
│  或重启    │     │ 下次启动  │
└───────────┘     └───────────┘
```

### 7.2 更新状态

| 状态 | 说明 |
|------|------|
| checking | 正在检查更新 |
| compatible | 当前版本已是最新 |
| update_available | 发现新版本 |
| downloading | 正在下载 |
| verifying | 正在验证 |
| installing | 正在安装 |
| rebooting | 正在重启 |
| failed | 更新失败 |

## 八、前端实现

### 8.1 版本管理页面

**功能：**
- 列表显示所有版本
- 创建新版本（仅平台管理员）
- 发布/取消发布版本
- 一键通知所有Agent更新
- 查看版本使用统计

**版本列表字段：**
- 版本号
- 状态（未发布/已发布）
- 更新类型（可选/强制）
- 下载链接
- 创建时间
- 操作（发布/取消/删除）

### 8.2 版本更新通知

**通知方式：**
- WebSocket实时推送（在线Agent）
- 下次心跳时检查（离线Agent）

**前端显示：**
- Agent在线状态
- Agent当前版本
- Agent是否已更新

## 九、文件服务器

### 9.1 存储方案

**推荐方案：**
- 对象存储（OSS/MinIO/CDN）
- 自建文件服务器
- Nginx静态文件服务

### 9.2 目录结构

```
/agent/
  ├── releases/
  │   ├── 1.0.0/
  │   │   ├── agent-1.0.0.exe
  │   │   └── checksum.txt
  │   └── 1.0.1/
  │       ├── agent-1.0.1.exe
  │       └── checksum.txt
  └── latest.exe
```

## 十、安全考虑

### 10.1 传输安全
- HTTPS加密传输
- MD5校验确保完整性

### 10.2 访问控制
- 下载链接添加签名验证
- Agent身份认证（AgentID + AgentSecret）

### 10.3 回滚机制
- 自动备份当前版本
- 更新失败自动回滚
- 紧急回滚接口

## 十一、配置参数

### 平台端
```yaml
agent:
  update:
    check-interval: 3600    # 检查间隔（秒）
    notify-on-publish: true # 发布时自动通知
```

### Agent端
```yaml
agent:
  update:
    auto-check: true        # 启动时自动检查
    check-interval: 3600    # 检查间隔（秒）
    auto-download: true      # 自动下载可选更新
    allow-user-skip: true   # 允许用户跳过可选更新
```

## 十二、错误处理

| 错误码 | 说明 | 处理方式 |
|--------|------|----------|
| 10001 | 下载链接无效 | 提示管理员检查 |
| 10002 | MD5校验失败 | 自动重新下载 |
| 10003 | 安装失败 | 自动回滚 |
| 10004 | 版本不兼容 | 提示升级Agent |
| 10005 | 磁盘空间不足 | 提示清理空间 |

## 十三、监控与日志

### 13.1 监控指标
- 各版本安装数量
- 更新成功率
- 更新耗时统计
- Agent版本分布

### 13.2 日志记录
- 版本发布记录
- Agent更新记录
- 更新失败详情
