# Agent API 认证说明

## 概述

Agent 与后端通信时使用独立的 `AgentSecret` 认证机制，不使用 JWT。注册时后端生成 Secret，保证安全性。

## 安全机制

| 机制 | 说明 |
|------|------|
| **后端生成 Secret** | Agent 不再生成 Secret，由服务器生成更安全 |
| **一次性注册码** | 注册码验证后立即标记为已使用，防止重复使用 |
| **注册码有效期** | 支持设置过期时间，过期后无法使用 |
| **Secret 只返回一次** | 注册成功时 Secret 只返回一次，Agent 需本地保存 |
| **Secret 验证** | 每次 API 请求都需要验证 Secret |

## 注册流程

```
Agent（商户电脑）                          后端
      |                                        |
      |  1. 调用注册接口                        |
      |     POST /api/agents/register           |
      |     参数: registrationCode, host, port  |
      | ─────────────────────────────────────► |
      |                                        |
      |  2. 验证注册码（一次性）                |
      |     - 检查是否存在                     |
      |     - 检查是否已使用                   |
      |     - 检查是否过期                     |
      |                                        |
      |  3. 后端生成凭证                       |
      |     - agentId = "agent-" + UUID       |
      |     - agentSecret = 随机32位字符串     |
      |     - 存储到数据库                     |
      |                                        |
      |  4. 返回凭证                          |
      |     {                                 |
      |       agentId: "agent-xxx",           |
      |       agentSecret: "xxx...",          |
      |       merchantId: "merchant-xxx"      |
      |     }                                 |
      | ◄──────────────────────────────────── │
      |                                        |
      |  5. 本地保存 Secret                    |
      |                                        |
      |  6. 后续请求带认证头                   |
      |     X-Agent-Id: agent-xxx             |
      |     X-Agent-Secret: Base64(xxx...)   |
```

## 认证方式

Agent 请求需要在 HTTP 请求头中携带以下两个参数：

| 请求头 | 说明 | 示例 |
|--------|------|------|
| `X-Agent-Id` | Agent 唯一标识（服务器生成） | `agent-a1b2c3d4` |
| `X-Agent-Secret` | Agent 密钥（Base64编码） | `YTMyZWUzMGQtYjYyYS00...` |

## Secret 编码

Agent Secret 需要进行 **Base64 编码**后传输：

```python
import base64
import requests

agent_id = "agent-a1b2c3d4"
agent_secret = "your-agent-secret-from-registration"

# Base64 编码
encoded_secret = base64.b64encode(agent_secret.encode()).decode()

# 发送请求
headers = {
    "X-Agent-Id": agent_id,
    "X-Agent-Secret": encoded_secret
}
response = requests.post(
    "http://server:8090/api/agents/heartbeat",
    headers=headers
)
```

```java
import java.util.Base64;

String agentId = "agent-a1b2c3d4";
String agentSecret = "your-agent-secret-from-registration";

// Base64 编码
String encodedSecret = Base64.getEncoder().encodeToString(agentSecret.getBytes());

// 发送请求时设置头
headers.set("X-Agent-Id", agentId);
headers.set("X-Agent-Secret", encodedSecret);
```

## 受保护的 API 路径

以下 API 需要进行 Agent 认证：

| 路径 | 方法 | 说明 |
|------|------|------|
| `/api/agents/register` | POST | 注册 Agent（无需认证，使用注册码） |
| `/api/agents/heartbeat` | POST | 发送心跳 |
| `/api/agents/status` | POST | 更新状态 |
| `/api/agents/uninstall` | POST | 卸载通知 |
| `/api/agents/offline` | POST | 离线通知 |
| `/api/agent-callback/*` | * | Agent 回调接口 |

## 认证失败响应

认证失败时，返回 HTTP 401：

```json
{
  "code": 401,
  "message": "Invalid credentials",
  "success": false
}
```

## 注册码安全机制

| 防护措施 | 说明 |
|----------|------|
| **一次性使用** | 验证后立即标记为 used，无法再次使用 |
| **过期时间** | 可设置 expire_time，过期后无法使用 |
| **日志审计** | 所有注册尝试都会记录日志 |
| **商户绑定** | 注册码与商户ID绑定 |

## 注意事项

1. **保存 Secret**：Secret 只在注册成功时返回一次，请务必本地保存
2. **安全传输**：生产环境请使用 HTTPS 传输
3. **日志记录**：认证失败时会记录 IP 地址和 Agent ID，便于安全审计
4. **定期更换**：建议定期更换 Agent Secret（在管理后台操作）

## 获取注册码

注册码由商户在管理后台生成，每个商户可以生成多个注册码。

注册码格式示例：`REG-ABC123DEF456`
