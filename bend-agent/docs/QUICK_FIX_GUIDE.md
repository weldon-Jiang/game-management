# Xbox 串流 Token 获取问题 - 快速修复指南

## 🎯 问题总结

经过代码审查，发现 Xbox 串流 Token 获取失败的根本原因是：

**认证器调用了错误的方法，导致缺少关键的 `gsToken`**

### 正确的 Token 流程

```
Microsoft OAuth (access_token)
  ↓
Xbox User Token
  ↓
XSTS Token
  ↓
GSSV Token (http://gssv.xboxlive.com/) ← 缺失！
  ↓
xHome Token / gsToken ← 缺失！
  ↓
Xbox Live API (发现 Xbox 主机)
```

### 当前问题

```python
# microsoft_auth_msal.py 第 1065 行
async def _get_xbox_live_tokens(self):
    return await xbox_client.get_xbox_tokens(...)  # ❌ 缺少 gsToken
    # 应该调用:
    return await xbox_client.get_xbox_tokens_with_gssv(...)  # ✅ 包含 gsToken
```

---

## 🚀 快速修复（3 步）

### 步骤 1: 运行自动修复脚本

```bash
cd d:\auto-xbox\team-management\bend-agent
python fix_streaming_token.py
```

**预期输出**:
```
============================================================
Xbox 串流 Token 修复脚本
============================================================

[1] 读取文件: src\agent\auth\microsoft_auth_msal.py
[OK] 成功读取文件，共 1075 行

[2] 找到需要修复的代码 (第 1065 行):
    return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)

[3] 执行修复...
[OK] 已创建备份: src\agent\auth\microsoft_auth_msal.py.backup
[OK] 文件已更新

[4] 验证修复...
[OK] ✓ 修复成功！第 1065 行已更新

============================================================
✓ 修复完成！
============================================================
```

### 步骤 2: 验证修复

```bash
python test_xbox_auth_debug.py
```

**预期输出**:
```
============================================================
Xbox Live 认证测试 - 详细调试模式
============================================================

[OK] Microsoft OAuth 登录成功
  access_token: eyJ0eXAiOiJKV1...
  refresh_token: M.r42423...

[2] 测试 Refresh MSAL Token...
[OK] MSAL Token 刷新成功
  MSAL access_token: eyJ0eXAiOiJKV1...

[3] 测试获取 Device Token...
[OK] Device Token 获取成功

[4] 测试获取 Xbox User Token...
[OK] Xbox User Token 获取成功

[5] 测试 Sisu Authorization...
[OK] Sisu Authorization 成功

[6] 测试 XSTS Authorization...
[OK] XSTS Authorization 成功
  XSTS Token: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
  User Hash: 123456789

[7] 测试获取 xHome Token...
[OK] xHome Token 获取成功
  gsToken: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

[8] 测试 gsToken 对 Xbox Live API 的有效性...
GET https://uks.core.gssv-play-prodxhome.xboxlive.com/v6/servers/home
Status: 200
[OK] gsToken 有效!
发现 1 台 Xbox 主机:
  - abc123def456: Xbox Series X
```

### 步骤 3: 测试串流功能

```bash
# 运行步骤 1（账号登录）
python -m agent.automation.step1_stream_account_login

# 运行步骤 2（Xbox 连接）
python -m agent.automation.step2_xbox_streaming
```

---

## 🔍 手动修复（如果自动修复失败）

### 1. 编辑文件

```bash
notepad src\agent\auth\microsoft_auth_msal.py
```

### 2. 找到第 1065 行

```python
# 找到这行（约第 1065 行）：
return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)
```

### 3. 替换为

```python
# 改为：
return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)
```

### 4. 保存文件

按 `Ctrl+S` 保存

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

## 📝 重要说明

### 关于步骤 1 的备用逻辑

在 `step1_stream_account_login.py` 中（行 302-316），已经有备用逻辑：

```python
# 先尝试获取包含 GSSV Token 的完整 Token
xbox_tokens = await xbox_client.get_xbox_tokens_with_gssv(...)

if xbox_tokens and xbox_tokens.gs_token:
    # 成功
else:
    # 回退到旧方法
    xbox_tokens = await xbox_client.get_xbox_tokens(...)
```

**这意味着步骤 1 可能会绕过第 1065 行的错误**，但其他调用 `_get_xbox_live_tokens()` 的地方仍会失败。

**因此，修复第 1065 行仍然必要！**

---

## 🆘 常见问题

### Q1: 修复后仍然失败？

**可能原因**: Token 已过期

**解决**: 
```bash
# 删除旧的 token 文件
del tokens\refresh_tokens.json

# 重新认证
python test_xbox_auth_debug.py
```

### Q2: "gsToken 为空" 错误？

**检查**:
1. 是否重启了程序？（需要重新加载代码）
2. Token 文件是否被正确保存？
3. 检查日志中的详细错误信息

**解决**:
```bash
# 查看详细日志
python test_xbox_auth_debug.py 2>&1 | tee debug.log
```

### Q3: "401 Unauthorized" 错误？

**可能原因**: Token 过期或无效

**解决**:
```python
# 在代码中添加 token 刷新逻辑
if token.expires_at < time.time():
    # 刷新 token
    token = await refresh_token(token.refresh_token)
```

### Q4: 回滚修复？

```bash
# 恢复备份文件
copy src\agent\auth\microsoft_auth_msal.py.backup src\agent\auth\microsoft_auth_msal.py
```

---

## 📊 代码对比

### 修复前（第 1065 行）

```python
async def _get_xbox_live_tokens(self) -> Optional[XboxLiveTokens]:
    if not self._microsoft_tokens:
        logger.error("未获取到微软令牌")
        return None
    
    xbox_client = XboxLiveClient()
    
    # ❌ 问题：调用了缺少 GSSV Token 的方法
    return await xbox_client.get_xbox_tokens(self._microsoft_tokens.access_token)
    # 返回的 XboxLiveTokens.gs_token 为 None
```

### 修复后（第 1065 行）

```python
async def _get_xbox_live_tokens(self) -> Optional[XboxLiveTokens]:
    if not self._microsoft_tokens:
        logger.error("未获取到微软令牌")
        return None
    
    xbox_client = XboxLiveClient()
    
    # ✅ 正确：调用包含完整 Token 的方法
    return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)
    # 返回的 XboxLiveTokens.gs_token 有值
```

---

## 🎯 下一步

1. **运行测试**: `python test_xbox_auth_debug.py`
2. **检查日志**: 确保所有 Token 都成功获取
3. **测试串流**: 启动完整的串流流程
4. **监控系统**: 监控 gsToken 有效期，及时刷新

---

## 📚 相关文档

- 详细分析报告: `XSTREAMING_ARCHITECTURE.md`
- 问题分析文档: `xbox_streaming_token_issue_analysis.md`
- 完整修复脚本: `fix_streaming_token.py`

---

**如有任何问题，请提供完整的错误日志！**
