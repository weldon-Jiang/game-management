# XStreamingDesktop 认证和串流架构分析

## 📋 概述

XStreamingDesktop 实现了两种认证方式来获取 Xbox Live token：

| 认证方式 | 描述 | Token 来源 | 是否需要 ECDSA 签名 |
|---------|------|-----------|-------------------|
| **XAL 方式** | Authorization Code Flow with PKCE | `login.live.com` | ✅ 需要 |
| **MSAL 方式** | Device Code Flow | `login.microsoftonline.com` | ❌ 不需要 |

## 🔐 认证流程对比

### 方式一：XAL 方式 (需要 ECDSA 签名)

```
┌─────────────────────────────────────────────────────────────┐
│                  XAL 认证流程 (Authorization Code + PKCE)    │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 获取 Redirect URI (包含 Sisu Auth)                       │
│     └── getRedirectUri() → sisu.xboxlive.com/authenticate   │
│                                                             │
│  2. 用户在浏览器中完成 OAuth 授权                             │
│     └── 浏览器打开 login.live.com                           │
│                                                             │
│  3. 交换 Authorization Code                                 │
│     └── exchangeCodeForToken(code, verifier)                │
│                                                             │
│  4. 获取 User Token                                         │
│     └── user.auth.xboxlive.com/user/authenticate           │
│                                                             │
│  5. 获取 Device Token (需要 ECDSA 签名!)                     │
│     └── device.auth.xboxlive.com/device/authenticate        │
│                                                             │
│  6. Sisu Authorization (需要 ECDSA 签名!)                    │
│     └── sisu.xboxlive.com/authorize                         │
│                                                             │
│  7. XSTS Authorization                                      │
│     └── xsts.auth.xboxlive.com/xsts/authorize               │
│                                                             │
│  8. 获取 Streaming Token (gsToken)                          │
│     └── xhome.gssv-play-prod.xboxlive.com/v2/login/user   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**关键 API 端点：**
- `login.live.com/oauth20_authorize.srf` - 授权
- `login.live.com/oauth20_token.srf` - 交换 token
- `device.auth.xboxlive.com/device/authenticate` - Device Token (ECDSA)
- `sisu.xboxlive.com/authorize` - Sisu Token (ECDSA)
- `xsts.auth.xboxlive.com/xsts/authorize` - XSTS Token
- `xhome.gssv-play-prod.xboxlive.com/v2/login/user` - Streaming Token

### 方式二：MSAL 方式 (不需要 ECDSA 签名)

```
┌─────────────────────────────────────────────────────────────┐
│                    MSAL 认证流程 (Device Code)              │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. Device Code 请求                                         │
│     POST login.microsoftonline.com/consumers/oauth2/v2.0/devicecode
│     client_id: 1f907974-e22b-4810-a9de-d9647380c97e        │
│     scope: xboxlive.signin openid profile offline_access   │
│                                                             │
│  2. 用户在终端输入代码完成授权                                │
│                                                             │
│  3. 轮询获取 Access Token                                    │
│     POST login.microsoftonline.com/consumers/oauth2/v2.0/token
│     grant_type: urn:ietf:params:oauth:grant-type:device_code│
│                                                             │
│  4. 获取 Xbox User Token                                    │
│     POST user.auth.xboxlive.com/user/authenticate           │
│     payload: { AuthMethod: "RPS", RpsTicket: "d=<token>" } │
│                                                             │
│  5. XSTS Authorization (使用 Xbox User Token)               │
│     POST xsts.auth.xboxlive.com/xsts/authorize              │
│     payload: { UserTokens: [<xbox_user_token>] }            │
│                                                             │
│  6. 获取 GSSV Token (用于串流)                               │
│     POST xsts.auth.xboxlive.com/xsts/authorize              │
│     RelyingParty: http://gssv.xboxlive.com/                 │
│                                                             │
│  7. 获取 Streaming Token (gsToken)                          │
│     POST xhome.gssv-play-prod.xboxlive.com/v2/login/user   │
│     POST xgpuweb.gssv-play-prod.xboxlive.com/v2/login/user │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**关键 API 端点：**
- `login.microsoftonline.com/consumers/oauth2/v2.0/devicecode` - Device Code
- `login.microsoftonline.com/consumers/oauth2/v2.0/token` - Token 交换
- `user.auth.xboxlive.com/user/authenticate` - Xbox User Token
- `xsts.auth.xboxlive.com/xsts/authorize` - XSTS Token
- `login.live.com/oauth20_token.srf` - 获取 MSAL Token (xbox cloud transfer)
- `{offering}.gssv-play-prod.xboxlive.com/v2/login/user` - Streaming Token

## 🎮 Xbox 发现流程

### Home Xbox 发现 (本地网络)

```
┌─────────────────────────────────────────────────────────────┐
│                     Xbox Home 发现流程                        │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 获取 Streaming Token (xHome)                            │
│     └── gsToken from xhome.gssv-play-prod.xboxlive.com     │
│                                                             │
│  2. 查询 Xbox 列表                                          │
│     GET xhome.gssv-play-prod.xboxlive.com/v6/servers/home  │
│     Headers:                                                │
│       Authorization: Bearer <gsToken>                      │
│       X-MS-Device-Info: <device_info_json>                 │
│                                                             │
│  3. 返回 Xbox 列表                                          │
│     {                                                       │
│       "results": [                                          │
│         { "id": "...", "name": "Xbox Series X", ... }     │
│       ]                                                     │
│     }                                                       │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**设备信息格式：**
```json
{
  "appInfo": {
    "env": {
      "clientAppId": "www.xbox.com",
      "clientAppType": "browser",
      "clientSdkVersion": "10.3.7"
    }
  },
  "dev": {
    "hw": { "make": "Microsoft", "model": "unknown", "sdktype": "web" },
    "os": { "name": "windows", "ver": "22631.2715", "platform": "desktop" },
    "displayInfo": {
      "dimensions": { "widthInPixels": 1920, "heightInPixels": 1080 }
    },
    "browser": { "browserName": "chrome", "browserVersion": "130.0" }
  }
}
```

## 🔄 串流流程

### 完整串流流程

```
┌─────────────────────────────────────────────────────────────┐
│                      完整串流流程                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  1. 启动串流会话                                            │
│     POST {host}/v5/sessions/{type}/play                   │
│     Headers:                                                │
│       Authorization: Bearer <gsToken>                      │
│       X-MS-Device-Info: <device_info>                      │
│     Body:                                                   │
│       {                                                     │
│         "serverId": "<xbox_id>",     // for home          │
│         "titleId": "<title_id>",      // for cloud         │
│         "settings": { ... }                                 │
│       }                                                     │
│                                                             │
│  2. 轮询会话状态                                            │
│     GET {host}/v5/sessions/{type}/{sessionId}/state       │
│     状态转换:                                                │
│       Provisioning → ReadyToConnect → Provisioned          │
│       (或 WaitingForResources → ...)                        │
│                                                             │
│  3. ReadyToConnect 状态                                     │
│     └── 需要发送 MSAL Token 进行认证                         │
│     POST {host}/v5/sessions/{type}/{sessionId}/connect    │
│     Body: { "userToken": "<msal_lpt>" }                    │
│                                                             │
│  4. 发送 SDP (WebRTC)                                      │
│     POST {host}/v5/sessions/{type}/{sessionId}/sdp        │
│     Body: { "messageType": "offer", "sdp": "..." }         │
│                                                             │
│  5. ICE 候选交换                                            │
│     POST {host}/v5/sessions/{type}/{sessionId}/ice         │
│     └── 处理 Teredo 地址获取外部 IP                         │
│                                                             │
│  6. 保持连接                                                │
│     POST {host}/v5/sessions/{type}/{sessionId}/keepalive  │
│                                                             │
│  7. 停止串流                                                │
│     DELETE {host}/v5/sessions/{type}/{sessionId}           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## 🔑 Token 类型总结

| Token 类型 | 用途 | 获取方式 | 有效期 |
|-----------|------|---------|--------|
| **MSAL Access Token** | 微软账号认证 | Device Code / Auth Code | ~1小时 |
| **Xbox User Token** | Xbox Live 用户标识 | user.auth.xboxlive.com | ~24小时 |
| **XSTS Token** | Xbox 服务认证 | xsts.auth.xboxlive.com | ~1小时 |
| **GSSV Token** | 游戏流认证 | xsts.auth.xboxlive.com (gssv) | ~1小时 |
| **Streaming Token (gsToken)** | 串流连接 | gssv-play-prod.xboxlive.com | ~24小时 |
| **Device Token** | 设备认证 | device.auth.xboxlive.com | 约25天 |
| **Sisu Token** | 高级认证 | sisu.xboxlive.com | ~24小时 |

## ⚠️ 关键发现

### 1. MSAL 方式更简单

MSAL 方式 (Device Code Flow) **不需要 ECDSA 签名**，这意味着：
- 实现更简单
- 不需要处理复杂的签名算法
- Token 可以从 `login.microsoftonline.com` 获取

### 2. refresh_token 问题

- `login.microsoftonline.com` 获取的 refresh_token **不能在 `login.live.com` 使用**
- 两者使用不同的 `client_id`
- 如果需要使用 XAL 方式，需要从 `login.live.com` 获取 token

### 3. Streaming Token 端点

- Home Xbox: `xhome.gssv-play-prod.xboxlive.com`
- xCloud: `xgpuweb.gssv-play-prod.xboxlive.com` 或 `xgpuwebf2p.gssv-play-prod.xboxlive.com`

### 4. Token 刷新策略

XStreamingDesktop 使用 23 小时阈值来决定是否刷新 token：
```javascript
// Skip refreshTokens within 23 hours
if (Date.now() - this._tokenStore.getTokenUpdateTime() < 23 * 60 * 60 * 1000) {
  // 使用缓存的 token
}
```

## 📝 Python 实现建议

基于以上分析，建议 Python 实现采用 **MSAL 方式**，因为：

1. ✅ 不需要实现 ECDSA 签名
2. ✅ 实现更简单可靠
3. ✅ 可以使用 Device Code Flow
4. ✅ 可以获取有效的 gsToken

### 推荐实现流程

```
1. Device Code Flow 获取 MSAL Token
   └── login.microsoftonline.com/consumers/oauth2/v2.0/devicecode
   └── login.microsoftonline.com/consumers/oauth2/v2.0/token

2. Xbox User Token
   └── user.auth.xboxlive.com/user/authenticate

3. XSTS Token (GSSV)
   └── xsts.auth.xboxlive.com/xsts/authorize
       RelyingParty: "http://gssv.xboxlive.com/"

4. Streaming Token
   └── xhome.gssv-play-prod.xboxlive.com/v2/login/user
       Body: { "token": "<xsts_token>", "offeringId": "xhome" }

5. Xbox 发现
   └── GET xhome.gssv-play-prod.xboxlive.com/v6/servers/home
       Headers: Authorization: Bearer <gsToken>
```
