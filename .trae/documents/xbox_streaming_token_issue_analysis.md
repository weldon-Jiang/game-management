# Xbox 串流 Token 获取问题分析与解决方案

## 🔍 问题概述

**问题描述**: 在使用已获取的 token 进行 Xbox 串流操作时遇到困难，特别是在获取 Xbox 串流服务所需的 token 过程中存在问题。

**根本原因**: 经过代码审查发现，认证模块中存在一个关键缺陷：

```python
# 文件: src/agent/auth/microsoft_auth_msal.py
# 第 1065 行

async def _get_xbox_live_tokens(self) -> Optional[XboxLiveTokens]:
    """获取Xbox Live令牌"""
    if not self._microsoft_tokens:
        logger.error("未获取到微软令牌")
        return None
    
    xbox_client = XboxLiveClient()
    return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)  # ❌ 这里调用了错误的方法！
```

**问题**: 调用的是 `get_xbox_tokens()` 方法，该方法只获取 Xbox User Token 和 XSTS Token，**没有获取 GSSV Token 和 xHome Token (gsToken)**！

---

## 📊 Token 获取流程分析

### ✅ 正确的完整 Token 获取流程

```
┌─────────────────────────────────────────────────────────────────┐
│              Xbox 串流 Token 完整获取流程                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  1. Microsoft OAuth (MSAL)                                      │
│     ├── 获取 access_token                                       │
│     └── 获取 refresh_token                                      │
│                                                                 │
│  2. Xbox User Token (user.auth.xboxlive.com)                   │
│     └── 使用 MSAL access_token 获取                             │
│                                                                 │
│  3. XSTS Token (xsts.auth.xboxlive.com)                        │
│     └── 使用 Xbox User Token 获取                               │
│                                                                 │
│  4. GSSV Token (http://gssv.xboxlive.com/) ⚠️ 关键步骤         │
│     └── 使用 XSTS Token 获取                                    │
│                                                                 │
│  5. xHome Token / gsToken ⚠️ 关键步骤                           │
│     └── 使用 GSSV Token 获取                                    │
│                                                                 │
│  6. 使用 gsToken 访问 Xbox Live API                             │
│     └── GET https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### ❌ 当前错误的 Token 获取流程

```python
# 当前代码只执行到步骤 3，缺少步骤 4 和 5

# xbox_auth.py 中存在两个方法：

class XboxAuth:
    """Xbox Live 完整认证类"""
    
    # 方法 1: 获取 GSSV Token 和 xHome Token ✅
    async def get_stream_token(self, offering_id: str) -> Dict[str, Any]:
        """获取 Streaming Token (xHome 或 xCloud)"""
        # 步骤 4: XSTS → GSSV
        # 步骤 5: GSSV → xHome
        
    async def get_xhome_token(self) -> str:
        """获取 xHome Token (gsToken)"""
        return self.get_stream_token("xhome")


class MicrosoftMsalAuthenticator:
    """微软账号认证器"""
    
    # ❌ 错误的方法调用
    async def _get_xbox_live_tokens(self) -> Optional[XboxLiveTokens]:
        xbox_client = XboxLiveClient()
        return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)
        #                     ↑ 只获取到 XSTS Token，没有 gsToken
```

---

## 🐛 代码问题定位

### 问题 1: `XboxLiveClient.get_xbox_tokens()` 缺少关键步骤

**文件**: `src/agent/auth/microsoft_auth_msal.py`

**位置**: 第 525-558 行

```python
async def get_xbox_tokens(self, access_token: str) -> Optional[XboxLiveTokens]:
    """
    获取Xbox Live令牌
    
    ❌ 问题：此方法只获取到 XSTS Token，缺少：
    1. GSSV Token 获取 (http://gssv.xboxlive.com/)
    2. xHome Token / gsToken 获取
    """
    try:
        # Step 1: 获取Xbox User Token ✅
        user_token = await self._get_xbox_user_token(access_token)
        
        # Step 2: 获取XSTS Token ✅
        xsts_token, user_hash = await self._get_xsts_token(user_token)
        
        # ❌ 缺失: GSSV Token 和 xHome Token
        # ❌ 应该调用 get_xbox_tokens_with_gssv() 方法
        
        return XboxLiveTokens(
            user_token=user_token,
            xsts_token=xsts_token,
            user_hash=user_hash
            # ❌ gs_token 字段为 None
        )
```

**正确的方法** (第 768-823 行):

```python
async def get_xbox_tokens_with_gssv(self, access_token: str) -> Optional[XboxLiveTokens]:
    """获取完整的 Xbox Live 令牌（包含 GSSV Token）"""
    try:
        # Step 1: Xbox User Token ✅
        user_token = await self._get_xbox_user_token(access_token)
        
        # Step 2: XSTS Token ✅
        xsts_token, user_hash = await self._get_xsts_token(user_token)
        
        # Step 3: GSSV Token ✅ (缺失的关键步骤)
        gssv_token = await self._get_gssv_token(xsts_token)
        
        # Step 4: xHome Token (gsToken) ✅ (缺失的关键步骤)
        gs_token = await self._get_xhome_token(gssv_token)
        
        return XboxLiveTokens(
            user_token=user_token,
            xsts_token=xsts_token,
            user_hash=user_hash,
            gs_token=gs_token  # ✅ 包含 gsToken
        )
```

### 问题 2: 认证器调用了错误的方法

**文件**: `src/agent/auth/microsoft_auth_msal.py`

**位置**: 第 1065 行

```python
async def _get_xbox_live_tokens(self) -> Optional[XboxLiveTokens]:
    """获取Xbox Live令牌"""
    if not self._microsoft_tokens:
        logger.error("未获取到微软令牌")
        return None
    
    xbox_client = XboxLiveClient()
    
    # ❌ 错误：应该调用 get_xbox_tokens_with_gssv()
    return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)
    
    # ✅ 正确：调用包含 GSSV 和 xHome token 的方法
    # return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)
```

---

## 💡 解决方案

### 方案 1: 修复 `_get_xbox_live_tokens()` 方法 (推荐)

**文件**: `src/agent/auth/microsoft_auth_msal.py`

**修改位置**: 第 1065 行

**修改前**:
```python
return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)
```

**修改后**:
```python
return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)
```

**优点**: 
- 修复简单，只需修改一行代码
- 复用现有正确实现
- 向后兼容，不影响其他模块

### 方案 2: 增强 `get_xbox_tokens()` 方法

**文件**: `src/agent/auth/microsoft_auth_msal.py`

**位置**: 第 525-558 行

**建议**: 将 `get_xbox_tokens()` 重命名为 `get_xbox_tokens_basic()`，并新增 `get_xbox_tokens()` 方法调用 `get_xbox_tokens_with_gssv()`。

---

## 🧪 验证步骤

### 步骤 1: 修复代码

```bash
# 编辑文件
notepad src/agent/auth/microsoft_auth_msal.py
```

找到第 1065 行，将:
```python
return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)
```

改为:
```python
return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)
```

### 步骤 2: 测试 Token 获取

创建测试脚本 `test_streaming_token.py`:

```python
"""
测试 Xbox 串流 Token 获取
"""

import asyncio
import aiohttp
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from agent.auth.microsoft_auth_msal import MicrosoftMsalAuthenticator


async def test_streaming_token():
    """测试串流 Token 获取"""
    
    print("="*60)
    print("Xbox 串流 Token 获取测试")
    print("="*60)
    
    try:
        # 1. 认证
        print("\n[1] 执行 Microsoft OAuth 认证...")
        authenticator = MicrosoftMsalAuthenticator()
        
        auth_result = await authenticator.login_with_credentials(
            "jwdong1991@outlook.com",
            "jwdong@666"
        )
        
        if not auth_result or not auth_result.success:
            print("[FAIL] 认证失败")
            return False
        
        print("[OK] 认证成功")
        
        # 2. 检查 Xbox Tokens
        xbox_tokens = auth_result.xbox_tokens
        if not xbox_tokens:
            print("[FAIL] Xbox Tokens 为空")
            return False
        
        print("\n[2] 检查 Xbox Tokens...")
        print(f"  user_token: {'✓' if xbox_tokens.user_token else '✗'}")
        print(f"  xsts_token: {'✓' if xbox_tokens.xsts_token else '✗'}")
        print(f"  user_hash: {xbox_tokens.user_hash}")
        
        # 3. 关键检查：gs_token
        print("\n[3] 检查 gsToken (串流必需)...")
        if not xbox_tokens.gs_token:
            print("[FAIL] ❌ gsToken 为空！这是导致串流失败的根本原因！")
            print("\n[解决] 修复方法:")
            print("  编辑 src/agent/auth/microsoft_auth_msal.py")
            print("  找到第 1065 行:")
            print("    return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)")
            print("  改为:")
            print("    return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)")
            return False
        
        print(f"[OK] gsToken: {xbox_tokens.gs_token[:50]}...")
        
        # 4. 测试 Xbox Live API
        print("\n[4] 测试 Xbox Live API (gsToken 有效性)...")
        url = "https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home"
        headers = {
            "Authorization": f"Bearer {xbox_tokens.gs_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-xbl-contract-version": "1"
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                print(f"\n  GET {url}")
                print(f"  Status: {resp.status}")
                
                if resp.status == 200:
                    data = await resp.json()
                    total = data.get('totalItems', 0)
                    print(f"[OK] gsToken 有效！")
                    print(f"     发现 {total} 台 Xbox 主机:")
                    
                    for server in data.get('results', []):
                        print(f"     - {server.get('serverId')}: {server.get('deviceName', 'Unknown')}")
                    
                    return True
                else:
                    text = await resp.text()
                    print(f"[FAIL] gsToken 无效: {text}")
                    return False
        
    except Exception as e:
        print(f"\n[FAIL] 测试异常: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    result = asyncio.run(test_streaming_token())
    
    print("\n" + "="*60)
    if result:
        print("✓ 所有测试通过！")
    else:
        print("✗ 测试失败，请检查上述错误信息")
    print("="*60)
```

### 步骤 3: 运行测试

```bash
python test_streaming_token.py
```

**预期输出** (修复后):
```
[3] 检查 gsToken (串流必需)...
[OK] gsToken: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

[4] 测试 Xbox Live API (gsToken 有效性)...
  GET https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home
  Status: 200
[OK] gsToken 有效！
     发现 1 台 Xbox 主机:
     - abc123...: Xbox Series X
```

---

## 🔧 API 调用流程详解

### 1. Microsoft OAuth (MSAL)

**端点**: `https://login.microsoftonline.com/consumers/oauth2/v2.0/token`

**请求**:
```http
POST /oauth2/v2.0/token HTTP/1.1
Host: login.microsoftonline.com
Content-Type: application/x-www-form-urlencoded

grant_type=refresh_token&client_id=1f907974-e22b-4810-a9de-d9647380c97e&refresh_token=xxx&scope=xboxlive.signin%20openid%20profile%20offline_access
```

**响应**:
```json
{
  "access_token": "eyJ0eXAiOiJKV1...",
  "refresh_token": "M.r42423...",
  "expires_in": 3600
}
```

### 2. Xbox User Token

**端点**: `https://user.auth.xboxlive.com/user/authenticate`

**请求**:
```json
{
  "RelyingParty": "http://auth.xboxlive.com",
  "TokenType": "JWT",
  "Properties": {
    "AuthMethod": "RPS",
    "SiteName": "user.auth.xboxlive.com",
    "RpsTicket": "d=eyJ0eXAiOiJKV1..."
  }
}
```

### 3. XSTS Token

**端点**: `https://xsts.auth.xboxlive.com/xsts/authorize`

**请求**:
```json
{
  "RelyingParty": "http://xboxlive.com",
  "TokenType": "JWT",
  "Properties": {
    "UserTokens": ["eyJhbGci..."],
    "SandboxId": "RETAIL"
  }
}
```

### 4. GSSV Token (⚠️ 关键步骤，缺失导致串流失败)

**端点**: `https://xsts.auth.xboxlive.com/xsts/authorize`

**请求**:
```json
{
  "RelyingParty": "http://gssv.xboxlive.com/",
  "TokenType": "JWT",
  "Properties": {
    "UserTokens": ["eyJhbGci..."],  // ← 使用 XSTS Token，不是 User Token
    "SandboxId": "RETAIL"
  }
}
```

**❌ 常见错误**: 
- 使用 Xbox User Token 而非 XSTS Token
- RelyingParty 使用 `http://xboxlive.com` 而非 `http://gssv.xboxlive.com/`

### 5. xHome Token (gsToken) (⚠️ 关键步骤)

**端点**: `https://xhome.gssv-play-prod.xboxlive.com/v2/login/user`

**请求**:
```json
{
  "token": "eyJhbGci...",  // ← 使用 GSSV Token
  "offeringId": "xhome"
}
```

**响应**:
```json
{
  "gsToken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "expiresIn": 86400
}
```

### 6. Xbox Live API

**端点**: `https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home`

**请求**:
```http
GET /v6/servers/home HTTP/1.1
Host: uks.core.gssv-play-prodxhome.xboxlive.com
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
x-xbl-contract-version: 1
```

---

## ⚠️ 常见错误排查

### 错误 1: "Token 响应缺少 gsToken"

**原因**: `_get_xbox_live_tokens()` 调用了错误的方法

**解决**: 见上述修复方案

### 错误 2: "gsToken 无效" (401 Unauthorized)

**可能原因**:
1. Token 过期（gsToken 有效期约 24 小时）
2. Token 未正确传递
3. 网络请求失败

**解决**:
```python
# 检查 token 是否过期
import time
if token.expires_at < time.time():
    # 刷新 token
    pass
```

### 错误 3: "X-Err Header: InvalidRealm"

**原因**: RelyingParty 设置错误

**解决**: 
- GSSV Token 使用: `"RelyingParty": "http://gssv.xboxlive.com/"`
- XSTS Token 使用: `"RelyingParty": "http://xboxlive.com"`
- ❌ 错误：混用这两个 RelyingParty

### 错误 4: "Device Token 失败" (403 Forbidden)

**原因**: ECDSA 签名失败

**解决**:
```python
# 检查 cryptography 库安装
pip install cryptography

# 验证 ECDSA 密钥生成
from cryptography.hazmat.primitives.asymmetric import ec
key = ec.generate_private_key(ec.SECP256R1())
```

---

## 📝 完整修复代码

**文件**: `src/agent/auth/microsoft_auth_msal.py`

**修改位置 1**: 第 1065 行

```python
# 找到这行代码：
return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)

# 替换为：
return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)
```

**修改位置 2**: 第 817-819 行（在 `get_xbox_tokens_with_gssv` 方法末尾）

```python
return XboxLiveTokens(
    user_token=user_token,
    xsts_token=xsts_token,
    user_hash=user_hash,
    gs_token=gs_token  # 确保此字段正确返回
)
```

---

## ✅ 验证清单

修复后，请验证以下所有项目：

- [ ] `gs_token` 字段不为 None
- [ ] `gs_token` 长度 > 100 字符
- [ ] Xbox Live API 返回 200 状态码
- [ ] 能够发现 Xbox 主机
- [ ] PlaySession 创建成功
- [ ] SDP 交换成功
- [ ] 视频流接收正常

---

## 📚 参考资料

- XStreamingDesktop 项目: https://github.com/freexbox/XStreamingDesktop
- Xbox Live 认证文档: https://learn.microsoft.com/zh-cn/gaming/xbox-live/api-ref/xbox-live-rest/references/authentication/auth-flow
- Microsoft OAuth 2.0: https://learn.microsoft.com/zh-cn/azure/active-directory/develop/v2-oauth2-device-code
