"""
微软账号认证模块 - MSAL设备码认证方案

分层设计说明：
┌─────────────────────────────────────────────────────────────────────┐
│                        认证模块分层架构                            │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 1: 数据模型层 (Data Models)                                │
│     ├── AuthStatus          # 认证状态枚举                          │
│     ├── MicrosoftTokens     # 微软访问令牌                          │
│     ├── XboxLiveTokens      # Xbox Live令牌                        │
│     └── AuthenticationResult # 认证结果封装                        │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 2: Token存储层 (Token Storage)                             │
│     └── TokenStorage        # 负责Token的持久化和缓存                │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 3: 微软OAuth认证层 (Microsoft OAuth)                        │
│     └── MicrosoftOAuthClient # 处理微软OAuth协议交互                │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 4: Xbox认证层 (Xbox Auth)                                 │
│     └── XboxLiveClient      # 处理Xbox Live令牌获取                │
├─────────────────────────────────────────────────────────────────────┤
│  Layer 5: 认证器主类 (Authenticator)                              │
│     └── MicrosoftMsalAuthenticator # 协调各层，提供统一接口          │
└─────────────────────────────────────────────────────────────────────┘

设计原则：
1. 单一职责：每个类只负责一个功能
2. 依赖倒置：高层模块不依赖低层模块，都依赖抽象
3. 开闭原则：对扩展开放，对修改封闭
4. 接口隔离：客户端只依赖需要的接口

参考文档：
- XStreamingDesktop: https://github.com/unknownskl/XStreamingDesktop
- Microsoft OAuth 2.0 Device Code Flow: https://learn.microsoft.com/zh-cn/azure/active-directory/develop/v2-oauth2-device-code
- Xbox Live Authentication: https://learn.microsoft.com/zh-cn/gaming/xbox-live/api-ref/xbox-live-rest/references/authentication/auth-flow
"""

import asyncio
import time
import json
import os
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger('microsoft_msal_auth')


# ============================================
# Layer 1: 数据模型层 (Data Models)
# ============================================

class AuthStatus(Enum):
    """
    认证状态枚举
    
    状态流转：
    PENDING → AUTHENTICATING → AUTHENTICATED
                              ↓
                          FAILED
    """
    PENDING = "pending"           # 待认证
    AUTHENTICATING = "authenticating" # 认证中
    AUTHENTICATED = "authenticated"   # 已认证
    FAILED = "failed"             # 认证失败


@dataclass
class MicrosoftTokens:
    """
    微软OAuth访问令牌
    
    包含从微软OAuth服务器获取的令牌信息，用于后续Xbox Live认证
    """
    access_token: str       # 访问令牌，用于访问微软资源
    refresh_token: str      # 刷新令牌，用于获取新的访问令牌
    expires_in: int         # 令牌有效期（秒）
    expires_at: float       # 令牌过期时间戳
    scope: str              # 权限范围
    token_type: str = "Bearer"  # 令牌类型


@dataclass
class XboxLiveTokens:
    """
    Xbox Live令牌
    
    包含连接Xbox主机所需的核心令牌，通过微软访问令牌转换获得
    
    参考 XStreamingDesktop 项目的认证流程：
    1. Microsoft OAuth Token → Xbox User Token
    2. Xbox User Token → XSTS Token
    3. XSTS Token → GSSV Token (Xbox Live Gaming Service)
    4. GSSV Token → xHomeToken (gsToken)
    """
    user_token: str   # Xbox用户令牌
    xsts_token: str   # XSTS令牌（用于主机认证）
    user_hash: str    # 用户哈希（UHS）
    gs_token: Optional[str] = None  # GSSV Token (Xbox Live Gaming Service Token) - Xbox Live API 需要这个


@dataclass
class AuthenticationResult:
    """
    认证结果封装
    
    统一的认证结果返回格式，包含成功/失败状态和相关令牌信息
    """
    success: bool                          # 是否成功
    status: AuthStatus                     # 认证状态
    message: str                           # 结果消息
    microsoft_tokens: Optional[MicrosoftTokens] = None  # 微软令牌
    xbox_tokens: Optional[XboxLiveTokens] = None       # Xbox令牌
    error_code: Optional[str] = None       # 错误码
    error_details: Optional[str] = None    # 错误详情


# ============================================
# Layer 2: Token存储层 (Token Storage)
# ============================================

class TokenStorage:
    """
    Token持久化存储管理器
    
    负责Refresh Token的持久化存储和内存缓存，支持多账号管理
    
    文件结构（与exe同目录）：
    ├── agent.exe
    └── tokens/
        └── refresh_tokens.json  # {"email": "refresh_token", ...}
    """
    
    # 内存缓存（类级别的共享缓存）
    _cache: Dict[str, str] = {}
    
    # 文件锁（防止并发写入冲突）
    _file_lock: asyncio.Lock = None
    
    @classmethod
    def _get_file_lock(cls) -> asyncio.Lock:
        """获取或创建文件锁"""
        if cls._file_lock is None:
            cls._file_lock = asyncio.Lock()
        return cls._file_lock
    
    @classmethod
    def _get_tokens_dir(cls) -> Path:
        """
        获取tokens目录的绝对路径
        
        关键逻辑：无论程序是直接运行还是打包成exe，都确保token文件存储在程序所在目录
        
        Returns:
            tokens目录的绝对路径
        """
        import sys
        
        # 获取程序入口文件路径
        if getattr(sys, 'frozen', False):
            # 打包成exe后的情况
            # sys.executable 是exe文件的完整路径
            exe_path = Path(sys.executable).resolve()
            app_dir = exe_path.parent
        else:
            # 开发环境运行的情况
            # __file__ 是当前模块文件的路径
            module_path = Path(__file__).resolve()
            # 向上找到agent目录
            app_dir = module_path.parent.parent.parent.parent
        
        return app_dir / "tokens"
    
    @classmethod
    def _get_tokens_file(cls) -> Path:
        """获取token文件的绝对路径"""
        return cls._get_tokens_dir() / "refresh_tokens.json"
    
    @classmethod
    def load_all_tokens(cls):
        """
        从文件加载所有账号的Refresh Token到内存缓存
        
        调用时机：程序启动时、需要同步文件内容时
        
        关键逻辑：确保从exe所在目录加载token文件
        """
        try:
            tokens_file = cls._get_tokens_file()
            logger.debug(f"尝试从 {tokens_file} 加载token")
            
            if tokens_file.exists():
                with open(tokens_file, 'r', encoding='utf-8') as f:
                    tokens = json.load(f)
                    if isinstance(tokens, dict):
                        cls._cache.clear()
                        cls._cache.update(tokens)
                        logger.info(f"已从文件加载 {len(tokens)} 个账号的Refresh Token")
            else:
                logger.info(f"未找到token文件: {tokens_file}，首次使用需要手动登录")
        except Exception as e:
            logger.error(f"加载token文件失败: {e}")
    
    @classmethod
    async def save_all_tokens_async(cls):
        """
        异步将内存缓存中的所有Refresh Token保存到文件（带锁）
        
        调用时机：Token更新后、程序退出前
        
        关键逻辑：
        1. 使用锁防止并发写入冲突
        2. 读取最新文件内容合并到缓存
        3. 写入文件确保数据不丢失
        """
        async with cls._get_file_lock():
            try:
                # 重新加载文件（其他协程可能已写入）
                tokens_file = cls._get_tokens_file()
                
                if tokens_file.exists():
                    try:
                        with open(tokens_file, 'r', encoding='utf-8') as f:
                            file_tokens = json.load(f)
                            if isinstance(file_tokens, dict):
                                # 合并文件中的其他账号数据
                                for email, token in file_tokens.items():
                                    if email not in cls._cache:
                                        cls._cache[email] = token
                    except json.JSONDecodeError:
                        pass
                
                # 确保目录存在
                tokens_dir = cls._get_tokens_dir()
                tokens_dir.mkdir(parents=True, exist_ok=True)
                
                # 写入文件
                with open(tokens_file, 'w', encoding='utf-8') as f:
                    json.dump(cls._cache, f, indent=2)
                    
                logger.debug(f"已保存 {len(cls._cache)} 个账号的Refresh Token（带锁）")
            except Exception as e:
                logger.error(f"保存token文件失败: {e}")
    
    @classmethod
    def get_token(cls, email: str) -> Optional[str]:
        """
        获取指定账号的Refresh Token
        
        Args:
            email: 用户邮箱（作为缓存键）
        
        Returns:
            Refresh Token或None
        """
        return cls._cache.get(email)
    
    @classmethod
    def set_token(cls, email: str, refresh_token: str):
        """
        设置指定账号的Refresh Token（同时更新缓存和文件）
        
        Args:
            email: 用户邮箱（作为缓存键）
            refresh_token: 要保存的Refresh Token
        """
        cls._cache[email] = refresh_token
        cls.save_all_tokens()
    
    @classmethod
    async def set_token_async(cls, email: str, refresh_token: str):
        """
        异步设置指定账号的Refresh Token（带锁）
        
        Args:
            email: 用户邮箱（作为缓存键）
            refresh_token: 要保存的Refresh Token
        """
        cls._cache[email] = refresh_token
        await cls.save_all_tokens_async()
        logger.info(f"已保存账号 {email} 的Refresh Token（异步带锁）")
    
    @classmethod
    def remove_token(cls, email: str):
        """
        删除指定账号的Refresh Token
        
        Args:
            email: 用户邮箱
        """
        if email in cls._cache:
            del cls._cache[email]
            cls.save_all_tokens()
            logger.info(f"已删除账号 {email} 的Refresh Token")
    
    @classmethod
    async def remove_token_async(cls, email: str):
        """
        异步删除指定账号的Refresh Token（带锁）
        
        Args:
            email: 用户邮箱
        """
        if email in cls._cache:
            del cls._cache[email]
            await cls.save_all_tokens_async()
            logger.info(f"已删除账号 {email} 的Refresh Token（异步带锁）")
    
    @classmethod
    def get_all_accounts(cls) -> list:
        """
        获取已存储的所有账号列表
        
        Returns:
            邮箱列表
        """
        return list(cls._cache.keys())


# ============================================
# Layer 3: 微软OAuth认证层 (Microsoft OAuth)
# ============================================

class MicrosoftOAuthClient:
    """
    微软OAuth客户端
    
    负责与微软OAuth服务器交互，实现设备码认证流程和Refresh Token刷新
    
    核心功能：
    1. 获取设备代码（Device Code Flow）
    2. 轮询等待用户授权并获取Token
    3. 使用Refresh Token刷新获取新Token
    
    参考文档：
    https://learn.microsoft.com/zh-cn/azure/active-directory/develop/v2-oauth2-device-code
    """
    
    # 微软OAuth配置
    AUTHORITY = "https://login.microsoftonline.com/consumers"
    CLIENT_ID = "1f907974-e22b-4810-a9de-d9647380c97e"
    
    # 请求权限范围
    SCOPES = [
        "xboxlive.signin",    # Xbox Live登录权限
        "openid",             # OpenID标识
        "profile",            # 用户资料
        "offline_access"      # 离线访问（获取Refresh Token）
    ]
    
    async def get_device_code(self) -> Optional[Dict[str, Any]]:
        """
        获取设备代码
        
        向微软OAuth服务器请求设备代码，用于用户手动验证
        
        Returns:
            设备代码信息字典，包含：
            - user_code: 用户需要输入的代码
            - device_code: 后台轮询使用的代码
            - verification_uri: 用户访问的验证URL
            - expires_in: 有效期（秒）
            - interval: 建议轮询间隔（秒）
        """
        import aiohttp
        
        url = f"{self.AUTHORITY}/oauth2/v2.0/devicecode"
        data = {
            "client_id": self.CLIENT_ID,
            "scope": " ".join(self.SCOPES)
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        logger.debug(f"设备代码响应: {json.dumps(result)[:200]}")
                        return result
                    else:
                        text = await resp.text()
                        logger.error(f"获取设备代码失败: {resp.status}, {text}")
                        return None
        except Exception as e:
            logger.error(f"获取设备代码异常: {e}")
            return None
    
    async def poll_for_token(self, device_code: str, expires_in: int) -> Optional[MicrosoftTokens]:
        """
        轮询获取Token
        
        在用户完成验证后，定期向服务器轮询获取访问令牌
        
        Args:
            device_code: 设备代码
            expires_in: 设备代码有效期（秒）
        
        Returns:
            MicrosoftTokens对象或None
        """
        import aiohttp
        
        url = f"{self.AUTHORITY}/oauth2/v2.0/token"
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": self.CLIENT_ID,
            "device_code": device_code
        }
        
        # 计算最大轮询次数（有效期/5秒 + 额外10次）
        max_attempts = int(expires_in / 5) + 10
        
        for attempt in range(max_attempts):
            await asyncio.sleep(5)
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data=data) as resp:
                        result = await resp.json()
                        
                        if resp.status == 200:
                            # Token获取成功
                            expires_at = time.time() + result.get("expires_in", 3600)
                            logger.info(f"Token获取成功，有效期: {result.get('expires_in', 3600)}秒")
                            return MicrosoftTokens(
                                access_token=result["access_token"],
                                refresh_token=result.get("refresh_token", ""),
                                expires_in=result.get("expires_in", 3600),
                                expires_at=expires_at,
                                scope=result.get("scope", ""),
                                token_type=result.get("token_type", "Bearer")
                            )
                        
                        error = result.get("error")
                        if error == "authorization_pending":
                            # 用户尚未完成授权
                            logger.debug(f"等待用户授权... ({attempt+1}/{max_attempts})")
                            continue
                        elif error == "slow_down":
                            # 服务器要求减慢轮询速度
                            logger.debug("服务器请求过频繁，减慢轮询速度")
                            await asyncio.sleep(3)
                            continue
                        elif error in ("expired_token", "invalid_grant"):
                            # 设备代码过期或无效
                            logger.error(f"设备代码认证失败: {error}")
                            return None
                        else:
                            # 其他错误
                            logger.error(f"未知错误: {error}, {result.get('error_description')}")
                            return None
                            
            except Exception as e:
                logger.error(f"轮询Token异常: {e}")
                continue
        
        logger.warning("设备代码认证超时")
        return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[MicrosoftTokens]:
        """
        使用Refresh Token刷新获取新Token
        
        Args:
            refresh_token: 已有的Refresh Token
        
        Returns:
            新的MicrosoftTokens对象或None
        """
        import aiohttp
        
        url = f"{self.AUTHORITY}/oauth2/v2.0/token"
        data = {
            "grant_type": "refresh_token",
            "client_id": self.CLIENT_ID,
            "refresh_token": refresh_token,
            "scope": " ".join(self.SCOPES)
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=data) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        expires_at = time.time() + result.get("expires_in", 3600)
                        return MicrosoftTokens(
                            access_token=result["access_token"],
                            refresh_token=result.get("refresh_token", refresh_token),
                            expires_in=result.get("expires_in", 3600),
                            expires_at=expires_at,
                            scope=result.get("scope", ""),
                            token_type=result.get("token_type", "Bearer")
                        )
                    else:
                        text = await resp.text()
                        logger.error(f"Refresh Token刷新失败: {resp.status}, {text}")
                        return None
        except Exception as e:
            logger.error(f"Refresh Token刷新异常: {e}")
            return None


# ============================================
# Layer 4: Xbox认证层 (Xbox Auth)
# ============================================

class XboxLiveClient:
    """
    Xbox Live认证客户端
    
    负责将微软访问令牌转换为Xbox Live令牌，用于连接Xbox主机
    
    认证流程：
    1. 使用微软访问令牌获取Xbox User Token
    2. 使用Xbox User Token获取XSTS Token
    3. 返回包含User Hash的完整Xbox令牌
    
    参考文档：
    https://learn.microsoft.com/zh-cn/gaming/xbox-live/api-ref/xbox-live-rest/references/authentication/auth-flow
    """
    
    async def get_xbox_tokens(self, access_token: str) -> Optional[XboxLiveTokens]:
        """
        获取Xbox Live令牌
        
        Args:
            access_token: 微软OAuth访问令牌
        
        Returns:
            XboxLiveTokens对象或None
        """
        import aiohttp
        
        try:
            # Step 1: 获取Xbox User Token
            user_token = await self._get_xbox_user_token(access_token)
            if not user_token:
                return None
            
            # Step 2: 获取XSTS Token
            xsts_token, user_hash = await self._get_xsts_token(user_token)
            if not xsts_token or not user_hash:
                return None
            
            logger.info(f"获取Xbox Live Tokens成功，用户哈希: {user_hash}")
            
            return XboxLiveTokens(
                user_token=user_token,
                xsts_token=xsts_token,
                user_hash=user_hash
            )
            
        except Exception as e:
            logger.error(f"获取Xbox Live Tokens异常: {e}", exc_info=True)
            return None
    
    async def _get_xbox_user_token(self, access_token: str) -> Optional[str]:
        """
        获取Xbox User Token
        
        Args:
            access_token: 微软OAuth访问令牌
        
        Returns:
            Xbox User Token字符串或None
        """
        import aiohttp
        
        url = "https://user.auth.xboxlive.com/user/authenticate"
        body = {
            "RelyingParty": "http://auth.xboxlive.com",
            "TokenType": "JWT",
            "Properties": {
                "AuthMethod": "RPS",
                "SiteName": "user.auth.xboxlive.com",
                "RpsTicket": f"d={access_token}"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                headers={"x-xbl-contract-version": "1"}
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"获取Xbox User Token失败: {resp.status}, {text}")
                    return None
                
                data = await resp.json()
                token = data.get("Token")
                
                if not token:
                    logger.error("获取Xbox User Token数据不完整")
                    return None
                
                logger.info("获取Xbox User Token成功")
                return token
    
    async def _get_xsts_token(self, user_token: str) -> tuple:
        """
        获取XSTS Token和User Hash
        
        Args:
            user_token: Xbox User Token
        
        Returns:
            (XSTS Token, User Hash) 元组，失败返回(None, None)
        """
        import aiohttp
        
        # 参考XStreamingDesktop项目，使用http://xboxlive.com而非https
        url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        body = {
            "RelyingParty": "http://xboxlive.com",
            "TokenType": "JWT",
            "Properties": {
                "UserTokens": [user_token],
                "SandboxId": "RETAIL"
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=body,
                headers={"x-xbl-contract-version": "1"}
            ) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    logger.error(f"获取XSTS Token失败: {resp.status}, {text}")
                    return None, None
                
                data = await resp.json()
                xsts_token = data.get("Token")
                user_hash = data.get("DisplayClaims", {}).get("xui", [{}])[0].get("uhs")
                
                if not xsts_token:
                    logger.error("获取XSTS Token数据不完整")
                    return None, None
                
                logger.info("获取XSTS Token成功")
                return xsts_token, user_hash
    
    async def _get_gssv_token(self, xsts_token: str) -> Optional[str]:
        """
        获取 GSSV Token (Xbox Live Gaming Service Token)
        
        这是 Xbox Live API 认证的关键步骤。
        参考 XStreamingDesktop 项目的 doXstsAuthorization 方法。
        
        Args:
            xsts_token: XSTS Token
        
        Returns:
            GSSV Token 字符串或 None
        """
        import aiohttp
        
        url = "https://xsts.auth.xboxlive.com/xsts/authorize"
        body = {
            "RelyingParty": "http://gssv.xboxlive.com/",
            "TokenType": "JWT",
            "Properties": {
                "UserTokens": [xsts_token],
                "SandboxId": "RETAIL"
            }
        }
        headers = {
            "x-xbl-contract-version": "1",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/",
            "Accept": "*/*",
            "ms-cv": "0",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=body,
                    headers=headers
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"获取GSSV Token失败: {resp.status}, {text}")
                        return None
                    
                    data = await resp.json()
                    gssv_token = data.get("Token")
                    
                    if not gssv_token:
                        logger.error("获取GSSV Token数据不完整")
                        return None
                    
                    logger.info("获取GSSV Token成功")
                    return gssv_token
                    
        except Exception as e:
            logger.error(f"获取GSSV Token异常: {e}", exc_info=True)
            return None
    
    async def _get_xhome_token(self, gssv_token: str) -> Optional[str]:
        """
        获取 xHome Token (gsToken)
        
        这是 Xbox Live 主机发现和串流所需的专用 Token。
        参考 XStreamingDesktop 项目的 getStreamToken('xhome') 方法。
        
        Args:
            gssv_token: GSSV Token
        
        Returns:
            xHome Token (gsToken) 字符串或 None
        """
        import aiohttp
        
        url = "https://xhome.gssv-play-prod.xboxlive.com/v2/login/user"
        body = {
            "token": gssv_token,
            "offeringId": "xhome"
        }
        headers = {
            "Content-Type": "application/json",
            "Cache-Control": "no-store, must-revalidate, no-cache",
            "x-gssv-client": "XboxComBrowser",
            "Origin": "https://www.xbox.com",
            "Referer": "https://www.xbox.com/",
            "Accept": "*/*",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json=body,
                    headers=headers
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        logger.error(f"获取xHome Token失败: {resp.status}, {text}")
                        return None
                    
                    data = await resp.json()
                    
                    # xHomeToken 返回格式包含 gsToken
                    gs_token = data.get("gsToken") or data.get("Token")
                    
                    if not gs_token:
                        logger.error(f"获取xHome Token数据不完整，响应: {data}")
                        return None
                    
                    logger.info("获取xHome Token成功")
                    return gs_token
                    
        except Exception as e:
            logger.error(f"获取xHome Token异常: {e}", exc_info=True)
            return None

    async def get_xbox_tokens_with_gssv(self, access_token: str) -> Optional[XboxLiveTokens]:
        """
        获取完整的 Xbox Live 令牌（包含 GSSV Token）
        
        这是正确的认证流程，对比 XStreamingDesktop 项目。
        
        流程：
        1. 使用微软访问令牌获取 Xbox User Token
        2. 使用 Xbox User Token 获取 XSTS Token
        3. 使用 XSTS Token 获取 GSSV Token ← 关键：使用 XSTS Token，不是 User Token
        4. 使用 GSSV Token 获取 xHome Token (gsToken) ← 新增
        5. 返回包含完整令牌的 XboxLiveTokens
        
        Args:
            access_token: 微软 OAuth 访问令牌
        
        Returns:
            XboxLiveTokens 对象或 None（包含 gs_token）
        """
        try:
            # Step 1: 获取 Xbox User Token
            user_token = await self._get_xbox_user_token(access_token)
            if not user_token:
                logger.error("Step 1 失败：无法获取 Xbox User Token")
                return None
            
            # Step 2: 获取 XSTS Token
            xsts_token, user_hash = await self._get_xsts_token(user_token)
            if not xsts_token or not user_hash:
                logger.error("Step 2 失败：无法获取 XSTS Token")
                return None
            
            # Step 3: 获取 GSSV Token（直接使用 Xbox User Token，不是 XSTS Token）
            gssv_token = await self._get_gssv_token(user_token)
            if not gssv_token:
                logger.error("Step 3 失败：无法获取 GSSV Token")
                return None
            
            # Step 4: 获取 xHome Token (gsToken)
            gs_token = await self._get_xhome_token(gssv_token)
            if not gs_token:
                logger.error("Step 4 失败：无法获取 xHome Token")
                return None
            
            logger.info(f"获取完整的 Xbox Live Tokens 成功，用户哈希: {user_hash}")
            
            return XboxLiveTokens(
                user_token=user_token,
                xsts_token=xsts_token,
                user_hash=user_hash,
                gs_token=gs_token
            )
            
        except Exception as e:
            logger.error(f"获取 Xbox Live Tokens 异常: {e}", exc_info=True)
            return None


# ============================================
# Layer 5: 认证器主类 (Authenticator)
# ============================================

class MicrosoftMsalAuthenticator:
    """
    微软账号认证器（主入口）
    
    协调各层组件，提供统一的认证接口。
    实现智能认证策略：优先使用Refresh Token刷新，失败则回退到设备码认证。
    
    核心流程：
    1. 初始化时加载已保存的Refresh Token
    2. 登录时优先尝试Refresh Token刷新
    3. 刷新失败则使用设备码认证
    4. 成功后获取Xbox Live令牌
    5. 保存Refresh Token到持久化存储
    
    使用示例：
        authenticator = MicrosoftMsalAuthenticator()
        result = await authenticator.login_with_credentials("user@outlook.com")
        if result.success:
            print(f"用户哈希: {result.xbox_tokens.user_hash}")
    """
    
    def __init__(self):
        """初始化认证器"""
        self._auth_status = AuthStatus.PENDING
        self._user_email = None
        self._microsoft_tokens: Optional[MicrosoftTokens] = None
        self._xbox_tokens: Optional[XboxLiveTokens] = None
        self._auto_code: Optional[str] = None  # TOTP Secret Key for MFA
        
        # 初始化Token存储（从文件加载已保存的Token）
        TokenStorage.load_all_tokens()
    
    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return (
            self._auth_status == AuthStatus.AUTHENTICATED
            and self._microsoft_tokens is not None
            and self._xbox_tokens is not None
        )
    
    async def login_with_credentials(
        self,
        email: str,
        password: str = None,
        encrypted_password: Optional[str] = None,
        auto_code: str = None
    ) -> AuthenticationResult:
        """
        执行完整的认证流程

        Args:
            email: 微软账号邮箱（用于标识和日志）
            password: 明文密码（用于浏览器自动化登录）
            encrypted_password: 加密密码（预留参数）
            auto_code: TOTP Secret Key，用于MFA自动验证码生成

        Returns:
            AuthenticationResult: 认证结果
        """
        self._auth_status = AuthStatus.AUTHENTICATING
        self._user_email = email
        self._auto_code = auto_code

        try:
            logger.info(f"开始MSAL认证: {email}")

            # Step 1: 尝试使用Refresh Token刷新
            microsoft_tokens = await self._try_refresh_token(email)
            if microsoft_tokens:
                self._microsoft_tokens = microsoft_tokens
                logger.info(f"使用Refresh Token刷新成功")
            else:
                # Step 2: Refresh Token不可用，使用设备码认证（浏览器自动化）
                microsoft_tokens = await self._try_device_code_auth(email, password, self._auto_code)
                if not microsoft_tokens:
                    return AuthenticationResult(
                        success=False,
                        status=AuthStatus.FAILED,
                        message="设备码认证失败"
                    )
                self._microsoft_tokens = microsoft_tokens
                logger.info(f"设备码认证成功")
            
            # Step 3: 保存Refresh Token（使用异步带锁版本，防止并发冲突）
            if self._microsoft_tokens.refresh_token:
                await TokenStorage.set_token_async(email, self._microsoft_tokens.refresh_token)
                logger.info("Refresh Token已保存（异步带锁）")
            
            # Step 4: 获取Xbox Live Tokens
            xbox_tokens = await self._get_xbox_live_tokens()
            if not xbox_tokens:
                return AuthenticationResult(
                    success=False,
                    status=AuthStatus.FAILED,
                    message="获取Xbox Live令牌失败"
                )
            self._xbox_tokens = xbox_tokens
            
            # Step 5: 更新认证状态
            self._auth_status = AuthStatus.AUTHENTICATED
            logger.info(f"认证完成: {email}, 用户哈希: {xbox_tokens.user_hash}")
            
            return AuthenticationResult(
                success=True,
                status=AuthStatus.AUTHENTICATED,
                message="认证成功",
                microsoft_tokens=self._microsoft_tokens,
                xbox_tokens=xbox_tokens
            )
        
        except Exception as e:
            self._auth_status = AuthStatus.FAILED
            logger.error(f"认证异常: {e}", exc_info=True)
            return AuthenticationResult(
                success=False,
                status=AuthStatus.FAILED,
                message=f"认证异常: {str(e)}",
                error_code="EXCEPTION"
            )
    
    async def _try_refresh_token(self, email: str) -> Optional[MicrosoftTokens]:
        """
        尝试使用Refresh Token刷新获取新Token
        
        Args:
            email: 用户邮箱
        
        Returns:
            MicrosoftTokens或None（刷新失败时）
        """
        refresh_token = TokenStorage.get_token(email)
        if not refresh_token:
            logger.info("未找到缓存的Refresh Token")
            return None
        
        logger.info("尝试使用Refresh Token刷新...")
        oauth_client = MicrosoftOAuthClient()
        return await oauth_client.refresh_token(refresh_token)
    
    async def _try_device_code_auth(
        self,
        email: str,
        password: str = None,
        auto_code: str = None
    ) -> Optional[MicrosoftTokens]:
        """
        执行设备码认证流程（浏览器自动化 + 并发控制）

        Args:
            email: 微软账号邮箱
            password: 微软账号密码（用于自动登录）
            auto_code: TOTP Secret Key，用于MFA自动验证码生成

        Returns:
            MicrosoftTokens或None（认证失败时）
        """
        # 获取设备代码（无需并发控制，多个账号可以同时获取）
        oauth_client = MicrosoftOAuthClient()
        device_code_data = await oauth_client.get_device_code()
        if not device_code_data:
            return None

        user_code = device_code_data.get("user_code")
        verification_uri = device_code_data.get("verification_uri")
        device_code = device_code_data.get("device_code")
        expires_in = device_code_data.get("expires_in", 300)

        # 输出设备码信息
        logger.info(f"设备代码: {user_code}, 验证URL: {verification_uri}")
        print(f"\n开始浏览器自动化设备码认证（账号: {email}）...")
        print(f"设备代码: {user_code}, 有效期: {expires_in}秒\n")

        # 检查是否有密码用于自动化登录
        if not password:
            logger.warning("未提供密码，跳过浏览器自动化，使用手动验证模式")
            print("注意: 未提供密码，将使用传统轮询方式（需要手动验证）")
            return await oauth_client.poll_for_token(device_code, expires_in)

        # 使用浏览器自动化进行设备码认证
        # 注意：并发控制应在任务调度器层面处理，不在认证模块内部
        try:
            from .browser_automation import DeviceCodeAuthenticator

            logger.info(f"启动浏览器自动化认证（账号: {email}）...")
            print(f"启动浏览器自动化认证（账号: {email}）...")

            # 创建浏览器自动化器（隐藏模式）
            logger.info("创建 DeviceCodeAuthenticator 实例...")
            authenticator = DeviceCodeAuthenticator(headless=True)
            logger.info("DeviceCodeAuthenticator 实例已创建")

            # 执行自动化认证
            logger.info("开始执行 authenticate() ...")
            print("开始执行浏览器自动化...")
            auth_success = await authenticator.authenticate(
                verification_url=verification_uri,
                user_code=user_code,
                email=email,
                password=password,
                auto_code=auto_code,
                timeout=expires_in
            )
            logger.info(f"authenticate() 执行完成，结果: {auth_success}")

            # 关闭浏览器
            await authenticator.close()

            if auth_success:
                logger.info(f"浏览器自动化认证成功（账号: {email}），开始获取Token...")
                print("浏览器自动化认证成功！")

                # 轮询获取Token（设备码认证仍需此步骤）
                microsoft_tokens = await oauth_client.poll_for_token(device_code, expires_in)

                if microsoft_tokens:
                    logger.info("Token获取成功")
                    return microsoft_tokens
                else:
                    logger.error("Token获取失败")
                    return None
            else:
                logger.error("浏览器自动化认证失败")
                print("浏览器自动化认证失败，尝试使用传统方式...")
                # 回退到传统轮询方式
                return await oauth_client.poll_for_token(device_code, expires_in)

        except Exception as e:
            logger.error(f"浏览器自动化异常: {e}", exc_info=True)
            print(f"浏览器自动化失败: {e}，回退到传统方式...")

            # 回退到传统轮询方式
            return await oauth_client.poll_for_token(device_code, expires_in)
    
    async def _get_xbox_live_tokens(self) -> Optional[XboxLiveTokens]:
        """
        获取Xbox Live令牌
        
        Returns:
            XboxLiveTokens或None
        """
        if not self._microsoft_tokens:
            logger.error("未获取到微软令牌")
            return None
        
        xbox_client = XboxLiveClient()
        return await xbox_client.get_xbox_tokens_with_gssv(self._microsoft_tokens.access_token)
    
    @classmethod
    def get_stored_accounts(cls) -> list:
        """获取已存储的所有账号列表"""
        return TokenStorage.get_all_accounts()
    
    @classmethod
    def remove_stored_token(cls, email: str):
        """删除指定账号的存储Token"""
        TokenStorage.remove_token(email)