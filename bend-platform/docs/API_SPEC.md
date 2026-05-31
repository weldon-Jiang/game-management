# Agent-Backend 接口规范文档 v2.0

## 📋 版本历史

| 版本 | 日期 | 变更内容 |
|------|------|----------|
| 1.0 | 2026-05-13 | 初始版本 |
| 2.0 | 2026-05-31 | 统一接口规范重构 |

## 🎯 核心原则

| 原则 | 说明 |
|------|------|
| **统一前缀** | 所有回调接口使用 `/api/v1/agent-callback` |
| **请求体JSON** | 所有参数通过请求体JSON传递，禁止使用URL参数 |
| **版本控制** | 使用URL版本号 `/v1/` 支持向后兼容 |
| **统一认证** | 使用 `X-Agent-Id` 和 `X-Agent-Secret` (Base64编码) 请求头 |
| **统一响应** | 使用 `ApiResponse<T>` 包装响应 |

## 📡 接口规范

### 1. 统一进度上报 `POST /api/v1/agent-callback/progress`

**功能**：统一的进度上报接口，替代原有的多个分散接口

#### 请求头
```
Content-Type: application/json
X-Agent-Id: {agentId}
X-Agent-Secret: {Base64编码的secret}
```

#### 请求体
```json
{
  "taskId": "string (必需)",
  "timestamp": 1234567890,
  "data": {
    "step": "STEP1|STEP2|STEP3|STEP4 (当前步骤)",
    "status": "RUNNING|COMPLETED|FAILED|GAME_PREPARING|GAMING|PAUSED|CANCELLED (必需)",
    "message": "string (状态描述)",
    "gameAccountId": "string (可选，游戏账号ID)",
    "metrics": {
      "todayCompleted": 1,
      "dailyLimit": 3,
      "failedCount": 0
    },
    "error": {
      "code": "ERROR_CODE",
      "details": "string"
    }
  }
}
```

#### 响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "received": true,
    "action": "CONTINUE|STOP|CANCEL",
    "instructions": {}
  }
}
```

#### 后端业务逻辑
| Status | 触发动作 |
|--------|----------|
| RUNNING | 更新任务状态为running，更新游戏账号状态 |
| COMPLETED | 更新完成标记，检查是否所有游戏账号完成 |
| FAILED | 更新任务状态为failed，记录错误信息 |
| GAME_PREPARING | 更新游戏账号状态为game_preparing |
| GAMING | 更新游戏账号状态为gaming |

---

### 2. 获取任务信息 `GET /api/v1/agent-callback/task/{taskId}`

**功能**：获取任务的完整信息，包括流媒体账号和游戏账号列表

#### 请求头
```
X-Agent-Id: {agentId}
X-Agent-Secret: {Base64编码的secret}
```

#### 响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "taskId": "string",
    "streamingAccount": {
      "id": "string",
      "email": "string",
      "password": "string (解密后)"
    },
    "gameAccounts": [
      {
        "id": "string",
        "gamertag": "string",
        "dailyMatchLimit": 3
      }
    ],
    "taskType": "custom|template_match",
    "createdAt": "timestamp"
  }
}
```

---

### 3. Xbox主机锁定 `POST /api/v1/agent-callback/xbox/{xboxHostId}/lock`

**功能**：锁定Xbox主机，防止多Agent抢占

#### 请求体
```json
{
  "taskId": "string (可选)"
}
```

#### 响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "locked": true,
    "expiresAt": "timestamp"
  }
}
```

---

### 4. Xbox主机解锁 `POST /api/v1/agent-callback/xbox/{xboxHostId}/unlock`

**功能**：释放Xbox主机

#### 请求体
```json
{
  "taskId": "string (可选)"
}
```

#### 响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "unlocked": true
  }
}
```

---

### 5. Xbox主机状态查询 `GET /api/v1/agent-callback/xbox/{xboxHostId}`

**功能**：查询Xbox主机详细信息和锁定状态

#### 响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "id": "string",
    "deviceId": "string",
    "name": "string",
    "ipAddress": "string",
    "status": "online|offline",
    "locked": false,
    "lockedByAgentId": null,
    "lockExpiresTime": null
  }
}
```

---

### 6. 凭证兑换 `POST /api/v1/agent-callback/credentials/exchange`

**功能**：兑换一次性令牌获取敏感凭证

#### 请求体
```json
{
  "token": "string (一次性令牌)"
}
```

#### 响应
```json
{
  "code": 200,
  "message": "success",
  "data": {
    "credential": "string (解密后的凭证)"
  }
}
```

---

## 🔌 WebSocket 消息规范

### 消息格式
```json
{
  "type": "string (消息类型)",
  "data": {
    "taskId": "string",
    "timestamp": 1234567890,
    ...其他字段
  }
}
```

### 后端 → Agent 消息

| Type | 触发条件 | Data字段 |
|------|----------|----------|
| **task** | 任务分配 | taskId, streamingAccount, gameAccounts, taskType |
| **cancel_task** | 任务取消 | taskId |
| **pause** | 任务暂停 | taskId |
| **resume** | 任务恢复 | taskId |
| **stop** | 任务停止 | taskId |
| **version_update** | 版本更新 | version, downloadUrl, md5Checksum, changelog, mandatory |
| **discover_xbox** | Xbox发现 | timestamp |

### Agent → 后端 消息

| Type | 触发时机 | Data字段 |
|------|----------|----------|
| **heartbeat** | 定时30秒 | agentId, timestamp, status, currentTaskId, currentStreamingId, version |
| **progress** | 步骤进展 | taskId, step, status, message, metrics |
| **xbox_discovered** | Xbox发现 | agentId, xboxes[] |
| **task_result** | 任务完成 | agentId, taskId, result |

---

## 🔄 向后兼容策略

### 旧接口保留期
- 保留旧接口 `POST /api/agent-callback/task/{taskId}/status` 至 `v2.0`
- 旧接口返回时添加 `deprecated: true` 标记
- 建议使用方尽快迁移至新接口

### 版本检测
```java
// 后端检测请求版本
String acceptVersion = request.getHeader("X-API-Version");
if ("v1".equals(acceptVersion)) {
  // 使用新规范处理
} else {
  // 使用旧规范处理，添加deprecated标记
}
```

---

## 📝 状态码定义

### 任务状态 (TaskStatus)
| 状态 | 说明 |
|------|------|
| pending | 等待执行 |
| running | 执行中 |
| completed | 已完成 |
| failed | 执行失败 |
| cancelled | 已取消 |
| timeout | 超时 |
| paused | 已暂停 |

### 游戏账号状态 (GameAccountStatus)
| 状态 | 说明 |
|------|------|
| pending | 等待执行 |
| running | 操作中 |
| game_preparing | 游戏准备中 |
| gaming | 游戏中 |
| completed | 已完成 |
| failed | 失败 |
| skipped | 已跳过 |

### 步骤状态 (StepStatus)
| 状态 | 说明 |
|------|------|
| STEP1 | 串流账号登录 |
| STEP2 | Xbox连接 |
| STEP3 | 流媒体初始化 |
| STEP4 | 游戏自动化 |

---

## ✅ 接口检查清单

- [ ] 所有回调接口使用 `/api/v1/agent-callback` 前缀
- [ ] 所有参数通过请求体JSON传递
- [ ] 使用 `X-Agent-Id` 和 `X-Agent-Secret` 请求头认证
- [ ] 响应使用 `ApiResponse<T>` 包装
- [ ] 添加请求时间戳和版本号
- [ ] 添加详细的错误码和错误信息
- [ ] 记录接口调用日志
- [ ] 添加接口文档注释
