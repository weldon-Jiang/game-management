# 数据库与前端字段优化分析报告

## 📊 问题总结

### 一、字段命名不一致问题

#### 1.1 驼峰命名 vs 下划线命名混用

| 位置 | 字段名 | 问题 |
|------|--------|------|
| Task表 | `current_step` | 数据库使用下划线 |
| Task Entity | `currentStep` | Java实体使用驼峰 |
| TaskGameAccountStatus表 | `completed_count` | 数据库使用下划线 |
| TaskGameAccountStatus Entity | `completedCount` | Java实体使用驼峰 |

**原因**：MyBatis-Plus默认会自动转换驼峰和下划线（驼峰映射开关）

**影响**：
- API返回JSON使用驼峰（符合前端规范）
- 但内部代码容易混淆
- 数据库迁移时需要注意

**建议**：
- ✅ 统一使用驼峰命名（符合JSON标准）
- ✅ 数据库字段统一使用下划线（符合SQL规范）
- ✅ MyBatis-Plus的驼峰映射（camelCase）应该开启

---

### 二、XboxHost表字段缺失

#### 2.1 缺少 `locked` 布尔字段

**现状分析**：

| 位置 | 字段 | 类型 | 说明 |
|------|------|------|------|
| 数据库 | `locked_by_agent_id` | VARCHAR(36) | 锁定者AgentID |
| 数据库 | `locked_time` | DATETIME | 锁定时间 |
| 数据库 | `locked_expires_time` | DATETIME | 锁定过期时间 |
| **缺失** | `locked` | TINYINT(1) | 锁定状态布尔值 |

**问题**：
1. **前端需要**：`XboxHostList.vue` 第38-43行使用 `row.locked` 布尔字段判断锁定状态
2. **接口返回**：`AgentCallbackController.getXboxHostStatus()` 返回 `lockedByAgentId`，前端需要自行判断
3. **逻辑冗余**：每次都需要判断 `locked_by_agent_id IS NOT NULL AND lock_expires_time > NOW()`

**优化方案**：

```sql
-- 添加 locked 字段
ALTER TABLE xbox_host
ADD COLUMN `locked` TINYINT(1) DEFAULT 0 COMMENT '是否被锁定';

-- 添加索引优化查询
ALTER TABLE xbox_host
ADD INDEX `idx_locked` (`locked`);
```

**代码修改**：

```java
// XboxHostServiceImpl.lock() 中添加
host.setLocked(true);

// XboxHostServiceImpl.unlock() 中添加
host.setLocked(false);
```

---

### 三、接口返回字段与前端需求不匹配

#### 3.1 AgentCallbackController.getXboxHostStatus() 问题

**前端需求** (XboxHostList.vue)：
```javascript
{
  "id": "...",
  "locked": true/false,           // ❌ 缺失
  "lockedByAgentId": "...",        // ✅ 有
  "lockExpiresTime": "...",        // ✅ 有
  "name": "...",
  "ipAddress": "...",
  ...
}
```

**当前返回** (AgentCallbackController.java)：
```java
result.put("id", host.getId());
result.put("deviceId", host.getXboxId());  // ❌ 字段名错误
result.put("name", host.getName());
result.put("ipAddress", host.getIpAddress());
result.put("status", host.getStatus());
result.put("locked", host.getLocked() != null && host.getLocked());  // ❌ 逻辑错误
result.put("lockedByAgentId", host.getLockedByAgentId());
result.put("lockExpiresTime", host.getLockExpiresTime());
```

**问题列表**：
1. ❌ `deviceId` 应该是 `xboxId`（前端期望的字段名）
2. ❌ `locked` 布尔字段计算逻辑错误
3. ❌ 缺少 `port`, `liveId`, `consoleType`, `macAddress` 等字段

---

#### 3.2 XboxHostItemDto 字段不完整

**当前DTO** (XboxHostItemDto.java)：
```java
private String id;
private String merchantId;
private String merchantName;
private String xboxId;              // ✅ 有
private String name;               // ✅ 有
private String ipAddress;           // ✅ 有
private String boundStreamingAccountId;  // ✅ 有
private String boundGamertag;       // ✅ 有
private String status;             // ✅ 有
private LocalDateTime lastSeenTime; // ✅ 有
private LocalDateTime createdTime;   // ✅ 有
// ❌ 缺少 locked, lockedByAgentId, lockExpiresTime, port, liveId, consoleType, macAddress
```

**前端需求** (XboxHostList.vue)：
- ✅ 需要显示 `locked` 布尔字段
- ✅ 需要显示 `lockedByAgentId`
- ✅ 需要显示 `lockExpiresTime`
- ✅ 需要显示 `macAddress`
- ✅ 需要显示 `port`

---

### 四、字段类型不一致

#### 4.1 Task 表 status 字段

| 位置 | 类型 | 说明 |
|------|------|------|
| Task表 | `VARCHAR(16)` | 无枚举约束 |
| Task Entity | 无枚举类型 | 使用String |
| 前端期望 | 固定枚举值 | pending, running, completed, failed, cancelled |

**风险**：数据库可以存储任意字符串，可能导致前端显示异常

**建议**：添加CHECK约束
```sql
ALTER TABLE task
ADD CONSTRAINT chk_task_status
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout', 'paused'));
```

---

#### 4.2 TaskGameAccountStatus 表 status 字段

**前端期望状态** (AgentTaskDialog.vue)：
```javascript
pending    // 待执行
running    // 执行中
completed  // 已完成
failed     // 失败
skipped    // 跳过
```

**建议**：同样添加CHECK约束
```sql
ALTER TABLE task_game_account_status
ADD CONSTRAINT chk_task_game_account_status
CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped'));
```

---

### 五、统一响应格式

#### 5.1 AgentCallbackController 接口响应

**当前问题**：
- 部分接口返回 `ApiResponse<T>`
- 部分接口直接返回 `Map<String, Object>` 或 `List<Map>`
- 缺少统一的错误码和错误消息

**优化方案**：
```java
// 统一返回格式
ApiResponse<Map<String, Object>> reportProgress(@RequestBody ...)

// 错误码规范
// 200: 成功
// 400: 请求参数错误
// 401: 认证失败
// 404: 资源不存在
// 500: 服务器内部错误
```

---

### 六、待优化的具体问题清单

| # | 问题 | 影响范围 | 优先级 | 建议操作 |
|---|------|----------|--------|----------|
| 1 | XboxHost 缺少 `locked` 布尔字段 | XboxHostList前端显示 | 🔴 高 | 添加字段 + 更新代码 |
| 2 | getXboxHostStatus 返回 `deviceId` 应为 `xboxId` | Agent回调接口 | 🔴 高 | 修改字段名 |
| 3 | getXboxHostStatus 缺少多个字段 | XboxHostList前端 | 🟡 中 | 补充字段 |
| 4 | XboxHostItemDto 缺少锁定相关字段 | Xbox主机列表页 | 🟡 中 | 补充DTO字段 |
| 5 | task表 status 字段无CHECK约束 | 数据完整性 | 🟡 中 | 添加CHECK约束 |
| 6 | task_game_account_status 表无CHECK约束 | 数据完整性 | 🟡 中 | 添加CHECK约束 |
| 7 | 部分接口响应格式不统一 | API一致性 | 🟢 低 | 统一响应格式 |

---

## ✅ 优化实施计划

### Phase 1: 数据库优化（立即执行）

1. **XboxHost表添加 locked 字段**
```sql
ALTER TABLE bend_platform.xbox_host
ADD COLUMN `locked` TINYINT(1) DEFAULT 0 COMMENT '是否被锁定' AFTER `locked_expires_time`;

CREATE INDEX idx_locked ON bend_platform.xbox_host(`locked`);
```

2. **添加CHECK约束**
```sql
ALTER TABLE bend_platform.task
ADD CONSTRAINT chk_task_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'cancelled', 'timeout', 'paused'));

ALTER TABLE bend_platform.task_game_account_status
ADD CONSTRAINT chk_task_game_account_status CHECK (status IN ('pending', 'running', 'completed', 'failed', 'skipped'));
```

### Phase 2: 后端代码优化（1-2天）

1. **修改 XboxHostServiceImpl.lock/unlock**
   - 添加 `host.setLocked(true/false)`

2. **修改 AgentCallbackController.getXboxHostStatus**
   - 修正 `deviceId` → `xboxId`
   - 添加 `locked` 布尔字段
   - 补充缺失字段

3. **修改 XboxHostItemDto**
   - 补充锁定相关字段

### Phase 3: 前端适配（1天）

1. **XboxHostList.vue**
   - 确认 `locked` 字段使用正确

2. **TaskList.vue**
   - 确认字段映射正确

---

## 📋 字段对照表

### XboxHost 完整字段列表

| 数据库字段 | Entity字段 | DTO字段 | 前端期望 | 状态 |
|-----------|-----------|---------|----------|------|
| id | id | id | id | ✅ |
| xbox_id | xboxId | xboxId | xboxId | ⚠️ 需修正 |
| name | name | name | name | ✅ |
| ip_address | ipAddress | ipAddress | ipAddress | ✅ |
| port | port | port | port | ❌ 缺失 |
| live_id | liveId | - | - | ⚠️ 可选 |
| console_type | consoleType | - | - | ⚠️ 可选 |
| mac_address | macAddress | - | macAddress | ❌ 缺失 |
| status | status | status | status | ✅ |
| locked | locked | - | locked | ❌ 缺失 |
| locked_by_agent_id | lockedByAgentId | lockedByAgentId | lockedByAgentId | ✅ |
| locked_time | lockedTime | - | - | ⚠️ 可选 |
| lock_expires_time | lockExpiresTime | lockExpiresTime | lockExpiresTime | ✅ |
| bound_streaming_account_id | boundStreamingAccountId | boundStreamingAccountId | - | ✅ |
| bound_gamertag | boundGamertag | boundGamertag | boundGamertag | ✅ |
| last_seen_time | lastSeenTime | lastSeenTime | lastSeenTime | ✅ |
| created_time | createdTime | createdTime | createdTime | ✅ |
| merchant_id | merchantId | merchantId | merchantId | ✅ |
| merchant_name | - | merchantName | merchantName | ✅ |

---

## 🎯 优化后的预期效果

1. **数据一致性**：数据库约束确保数据合法性
2. **API清晰度**：接口返回字段完整、前端使用方便
3. **维护性**：字段命名统一、类型明确
4. **扩展性**：预留字段方便未来扩展
