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
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger('microsoft_msal_auth')


# ============================================
# 第 1 层：数据模型
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
    gssv_base_uri: Optional[str] = None  # xHome 返回的默认区域 baseUri，后续发现/串流必须复用
    xhome_token_response: Optional[Dict[str, Any]] = None  # 保留 xHome 原始响应，便于真实主机联调排查


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
# 第 2 层：Token 存储
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
        
        返回:
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
            logger.debug(f"尝试从 {tokens_file} 加载认证缓存")
            
            if tokens_file.exists():
                with open(tokens_file, 'r', encoding='utf-8') as f:
                    tokens = json.load(f)
                    if isinstance(tokens, dict):
                        cls._cache.clear()
                        cls._cache.update(tokens)
                        logger.info(f"已从文件加载 {len(tokens)} 个账号的认证缓存")
            else:
                logger.info(f"未找到认证缓存文件: {tokens_file}，首次使用需要手动登录")
        except Exception as e:
            logger.error(f"加载认证缓存文件失败: {e}")
    
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
                    
                logger.debug(f"已保存 {len(cls._cache)} 个账号的认证缓存（带锁）")
            except Exception as e:
                logger.error(f"保存认证缓存文件失败: {e}")
    
    @classmethod
    def get_token(cls, email: str) -> Optional[str]:
        """
        获取指定账号的Refresh Token
        
        参数:
            email: 用户邮箱（作为缓存键）
        
        返回:
            Refresh Token或None
        """
        return cls._cache.get(email)
    
    @classmethod
    def set_token(cls, email: str, refresh_token: str):
        """
        设置指定账号的Refresh Token（同时更新缓存和文件）
        
        参数:
            email: 用户邮箱（作为缓存键）
            refresh_token: 要保存的Refresh Token
        """
        cls._cache[email] = refresh_token
        cls.save_all_tokens()
    
    @classmethod
    async def set_token_async(cls, email: str, refresh_token: str):
        """
        异步设置指定账号的Refresh Token（带锁）
        
        参数:
            email: 用户邮箱（作为缓存键）
            refresh_token: 要保存的Refresh Token
        """
        cls._cache[email] = refresh_token
        await cls.save_all_tokens_async()
        logger.info(f"已保存账号 {email} 的认证缓存（异步带锁）")
    
    @classmethod
    def remove_token(cls, email: str):
        """
        删除指定账号的Refresh Token
        
        参数:
            email: 用户邮箱
        """
        if email in cls._cache:
            del cls._cache[email]
            cls.save_all_tokens()
            logger.info(f"已删除账号 {email} 的认证缓存")
    
    @classmethod
    async def remove_token_async(cls, email: str):
        """
        异步删除指定账号的Refresh Token（带锁）
        
        参数:
            email: 用户邮箱
        """
        if email in cls._cache:
            del cls._cache[email]
            await cls.save_all_tokens_async()
            logger.info(f"已删除账号 {email} 的认证缓存（异步带锁）")
    
    @classmethod
    def get_all_accounts(cls) -> list:
        """
        获取已存储的所有账号列表
        
        返回:
            邮箱列表
        """
        return list(cls._cache.keys())


# ============================================
# 第 3 层：微软 OAuth 认证
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
        
        返回:
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
    
    async def poll_for_token(self, device_code: str, max_wait_seconds: int) -> Optional[MicrosoftTokens]:
        """
        轮询获取Token
        
        在用户完成验证后，定期向服务器轮询获取访问令牌
        
        参数:
            device_code: 设备代码
            max_wait_seconds: 最大等待时间（秒），超时后立即停止轮询
        
        返回:
            MicrosoftTokens对象或None
        """
        import aiohttp

        if max_wait_seconds <= 0:
            logger.warning("设备代码认证超时：无剩余等待时间")
            return None
        
        url = f"{self.AUTHORITY}/oauth2/v2.0/token"
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": self.CLIENT_ID,
            "device_code": device_code
        }

        start_time = time.time()
        attempt = 0

        while (time.time() - start_time) < max_wait_seconds:
            elapsed = time.time() - start_time
            sleep_time = min(5, max_wait_seconds - elapsed)
            if sleep_time <= 0:
                break
            await asyncio.sleep(sleep_time)
            attempt += 1
            
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(url, data=data) as resp:
                        result = await resp.json()
                        
                        if resp.status == 200:
                            expires_at = time.time() + result.get("expires_in", 3600)
                            logger.info(f"OAuth 授权成功，有效期: {result.get('expires_in', 3600)}秒")
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
                            logger.debug(f"等待用户授权... (第{attempt}次轮询)")
                            continue
                        elif error == "slow_down":
                            logger.debug("服务器请求过频繁，减慢轮询速度")
                            await asyncio.sleep(3)
                            continue
                        elif error in ("expired_token", "invalid_grant"):
                            logger.error(f"设备代码认证失败: {error}")
                            return None
                        else:
                            logger.error(f"未知错误: {error}, {result.get('error_description')}")
                            return None
                            
            except Exception as e:
                logger.error(f"轮询授权结果异常: {e}")
                continue
        
        logger.warning("设备代码认证超时")
        return None
    
    async def refresh_token(self, refresh_token: str) -> Optional[MicrosoftTokens]:
        """
        使用Refresh Token刷新获取新Token
        
        参数:
            refresh_token: 已有的Refresh Token
        
        返回:
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
                        await resp.text()
                        logger.error(f"刷新认证缓存失败: HTTP {resp.status}")
                        return None
        except Exception as e:
            logger.error(f"刷新认证缓存异常: {e}")
            return None


# ============================================
# 第 4 层：Xbox 认证
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
        
        参数:
            access_token: 微软OAuth访问令牌
        
        返回:
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
            
            logger.info(f"Xbox Live 认证成功，用户哈希: {user_hash}")
            
            return XboxLiveTokens(
                user_token=user_token,
                xsts_token=xsts_token,
                user_hash=user_hash
            )
            
        except Exception as e:
            logger.error(f"Xbox Live 认证异常: {e}", exc_info=True)
            return None
    
    async def _get_xbox_user_token(self, access_token: str) -> Optional[str]:
        """
        获取Xbox User Token
        
        参数:
            access_token: 微软OAuth访问令牌
        
        返回:
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
                    await resp.text()
                    logger.error(f"Xbox User 认证失败: HTTP {resp.status}")
                    return None
                
                data = await resp.json()
                token = data.get("Token")
                
                if not token:
                    logger.error("Xbox User 认证数据不完整")
                    return None
                
                logger.info("Xbox User 认证成功")
                return token
    
    async def _get_xsts_token(self, user_token: str) -> tuple:
        """
        获取XSTS Token和User Hash
        
        参数:
            user_token: Xbox User Token
        
        返回:
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
                    await resp.text()
                    logger.error(f"XSTS 认证失败: HTTP {resp.status}")
                    return None, None
                
                data = await resp.json()
                xsts_token = data.get("Token")
                user_hash = data.get("DisplayClaims", {}).get("xui", [{}])[0].get("uhs")
                
                if not xsts_token:
                    logger.error("XSTS 认证数据不完整")
                    return None, None
                
                logger.info("XSTS 认证成功")
                return xsts_token, user_hash
    
    async def _get_gssv_token(self, xsts_token: str) -> Optional[str]:
        """
        获取 GSSV Token (Xbox Live Gaming Service Token)
        
        这是 Xbox Live API 认证的关键步骤。
        参考 XStreamingDesktop 项目的 doXstsAuthorization 方法。
        
        参数:
            xsts_token: XSTS Token
        
        返回:
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
                        await resp.text()
                        logger.error(f"GSSV 认证失败: HTTP {resp.status}")
                        return None
                    
                    data = await resp.json()
                    gssv_token = data.get("Token")
                    
                    if not gssv_token:
                        logger.error("GSSV 认证数据不完整")
                        return None
                    
                    logger.info("GSSV 认证成功")
                    return gssv_token
                    
        except Exception as e:
            logger.error(f"GSSV 认证异常: {e}", exc_info=True)
            return None
    
    def _select_xhome_base_uri(self, data: Dict[str, Any]) -> Optional[str]:
        """从 xHome token 响应里选择默认区域 baseUri。"""
        server_details = data.get("serverDetails") or {}
        regions = server_details.get("regions") or data.get("regions") or []
        if not isinstance(regions, list):
            return None

        for region in regions:
            if isinstance(region, dict) and region.get("isDefault") and region.get("baseUri"):
                return str(region["baseUri"]).rstrip("/")

        for region in regions:
            if isinstance(region, dict) and region.get("baseUri"):
                return str(region["baseUri"]).rstrip("/")

        return None

    async def _get_xhome_token(self, gssv_token: str) -> Optional[Tuple[str, Optional[str], Dict[str, Any]]]:
        """
        获取 xHome Token (gsToken)
        
        这是 Xbox Live 主机发现和串流所需的专用 Token。
        参考 XStreamingDesktop 项目的 getStreamToken('xhome') 方法。
        
        参数:
            gssv_token: GSSV Token
        
        返回:
            (gsToken, 默认 baseUri, 原始响应) 或 None
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
                        await resp.text()
                        logger.error(f"xHome 认证失败: HTTP {resp.status}")
                        return None
                    
                    data = await resp.json()
                    
                    # xHomeToken 返回格式包含 gsToken
                    gs_token = data.get("gsToken") or data.get("Token")
                    
                    if not gs_token:
                        logger.error("xHome 认证数据不完整")
                        return None
                    
                    base_uri = self._select_xhome_base_uri(data)
                    if base_uri:
                        logger.info(f"xHome 认证成功，默认区域: {base_uri}")
                    else:
                        logger.warning("xHome 认证成功，但响应中未找到默认区域 baseUri，将使用默认 GSSV 地址")
                    return gs_token, base_uri, data
                    
        except Exception as e:
            logger.error(f"xHome 认证异常: {e}", exc_info=True)
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
        
        参数:
            access_token: 微软 OAuth 访问令牌
        
        返回:
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
            xhome_token = await self._get_xhome_token(gssv_token)
            if not xhome_token:
                logger.error("Step 4 失败：无法获取 xHome Token")
                return None
            gs_token, gssv_base_uri, xhome_response = xhome_token
            
            logger.info(f"完整 Xbox Live 认证成功，用户哈希: {user_hash}")
            
            return XboxLiveTokens(
                user_token=user_token,
                xsts_token=xsts_token,
                user_hash=user_hash,
                gs_token=gs_token,
                gssv_base_uri=gssv_base_uri,
                xhome_token_response=xhome_response,
            )
            
        except Exception as e:
            logger.error(f"完整 Xbox Live 认证异常: {e}", exc_info=True)
            return None


# ============================================
# 第 5 层：认证器主类
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
        self._auto_code: Optional[str] = None  # MFA 用 TOTP 密钥
        self._last_device_code_error: Optional[str] = None
        
        # 初始化Token存储（从文件加载已保存的Token）
        TokenStorage.load_all_tokens()

    @staticmethod
    def _get_device_code_timeout() -> int:
        """读取设备码认证总超时（秒），默认 300 秒（5 分钟）"""
        try:
            from ..core.config import get_config
            return max(60, int(get_config().auth.DEVICE_CODE_TIMEOUT))
        except Exception:
            return 300

    @staticmethod
    def _remaining_seconds(deadline: float) -> int:
        """计算距离截止时间的剩余秒数"""
        return max(0, int(deadline - time.time()))
    
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

        参数:
            email: 微软账号邮箱（用于标识和日志）
            password: 明文密码（用于浏览器自动化登录）
            encrypted_password: 加密密码（预留参数）
            auto_code: TOTP Secret Key，用于MFA自动验证码生成

        返回:
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
                logger.info("使用认证缓存刷新成功")
            else:
                # Step 2: Refresh Token不可用，使用设备码认证（浏览器自动化）
                microsoft_tokens, device_code_error = await self._try_device_code_auth(
                    email, password, self._auto_code
                )
                if not microsoft_tokens:
                    error_code = device_code_error or self._last_device_code_error or "DEVICE_CODE_FAILED"
                    if error_code == "DEVICE_CODE_TIMEOUT":
                        message = f"设备码认证超时（{self._get_device_code_timeout()}秒）"
                    else:
                        message = "设备码认证失败"
                    return AuthenticationResult(
                        success=False,
                        status=AuthStatus.FAILED,
                        message=message,
                        error_code=error_code
                    )
                self._microsoft_tokens = microsoft_tokens
                logger.info(f"设备码认证成功")
            
            # Step 3: 保存Refresh Token（使用异步带锁版本，防止并发冲突）
            if self._microsoft_tokens.refresh_token:
                await TokenStorage.set_token_async(email, self._microsoft_tokens.refresh_token)
                logger.info("认证缓存已保存（异步带锁）")
            
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
        
        参数:
            email: 用户邮箱
        
        返回:
            MicrosoftTokens或None（刷新失败时）
        """
        refresh_token = TokenStorage.get_token(email)
        if not refresh_token:
            logger.info("未找到缓存的认证凭据")
            return None
        
        logger.info("尝试使用认证缓存刷新...")
        oauth_client = MicrosoftOAuthClient()
        return await oauth_client.refresh_token(refresh_token)
    
    async def _try_device_code_auth(
        self,
        email: str,
        password: str = None,
        auto_code: str = None
    ) -> Tuple[Optional[MicrosoftTokens], Optional[str]]:
        """
        执行设备码认证流程（浏览器自动化，总时限由 DEVICE_CODE_TIMEOUT 控制）

        参数:
            email: 微软账号邮箱
            password: 微软账号密码（用于自动登录）
            auto_code: TOTP Secret Key，用于MFA自动验证码生成

        返回:
            (MicrosoftTokens, error_code): 成功时 error_code 为 None
        """
        self._last_device_code_error = None
        auth_timeout = self._get_device_code_timeout()
        deadline = time.time() + auth_timeout

        oauth_client = MicrosoftOAuthClient()
        device_code_data = await oauth_client.get_device_code()
        if not device_code_data:
            self._last_device_code_error = "DEVICE_CODE_FAILED"
            return None, "DEVICE_CODE_FAILED"

        user_code = device_code_data.get("user_code")
        verification_uri = device_code_data.get("verification_uri")
        device_code = device_code_data.get("device_code")
        ms_expires_in = device_code_data.get("expires_in", 300)
        effective_timeout = min(ms_expires_in, auth_timeout)

        logger.info(
            f"设备代码: {user_code}, 验证URL: {verification_uri}, "
            f"认证时限: {effective_timeout}秒（上限 {auth_timeout}秒）"
        )
        print(f"\n开始设备码认证（账号: {email}）...")
        print(f"设备代码: {user_code}, 认证时限: {effective_timeout}秒\n")

        if not password:
            logger.warning("未提供密码，跳过浏览器自动化，使用轮询等待授权")
            print("注意: 未提供密码，请在验证页面手动完成登录")
            tokens = await oauth_client.poll_for_token(
                device_code, self._remaining_seconds(deadline)
            )
            if tokens:
                return tokens, None
            error_code = (
                "DEVICE_CODE_TIMEOUT"
                if self._remaining_seconds(deadline) <= 0
                else "DEVICE_CODE_FAILED"
            )
            self._last_device_code_error = error_code
            return None, error_code

        try:
            from .browser_automation import DeviceCodeAuthenticator

            remaining = self._remaining_seconds(deadline)
            if remaining <= 0:
                self._last_device_code_error = "DEVICE_CODE_TIMEOUT"
                return None, "DEVICE_CODE_TIMEOUT"

            logger.info(f"启动浏览器自动化认证（账号: {email}，剩余 {remaining} 秒）...")
            print(f"启动浏览器自动化认证（账号: {email}，剩余 {remaining} 秒）...")

            authenticator = DeviceCodeAuthenticator(headless=True)
            auth_success = await authenticator.authenticate(
                verification_url=verification_uri,
                user_code=user_code,
                email=email,
                password=password,
                auto_code=auto_code,
                timeout=remaining
            )
            logger.info(f"authenticate() 执行完成，结果: {auth_success}")

            if not auth_success:
                error_code = (
                    "DEVICE_CODE_TIMEOUT"
                    if self._remaining_seconds(deadline) <= 0
                    else "DEVICE_CODE_FAILED"
                )
                logger.error(f"浏览器自动化认证失败: {error_code}")
                print(f"浏览器自动化认证失败: {error_code}")
                self._last_device_code_error = error_code
                return None, error_code

            remaining = self._remaining_seconds(deadline)
            if remaining <= 0:
                self._last_device_code_error = "DEVICE_CODE_TIMEOUT"
                return None, "DEVICE_CODE_TIMEOUT"

            logger.info(f"浏览器自动化认证成功（账号: {email}），开始获取授权结果（剩余 {remaining} 秒）...")
            print("浏览器自动化认证成功，正在获取 Token...")

            microsoft_tokens = await oauth_client.poll_for_token(device_code, remaining)
            if microsoft_tokens:
                logger.info("授权结果获取成功")
                return microsoft_tokens, None

            error_code = (
                "DEVICE_CODE_TIMEOUT"
                if self._remaining_seconds(deadline) <= 0
                else "DEVICE_CODE_FAILED"
            )
            logger.error(f"授权结果获取失败: {error_code}")
            self._last_device_code_error = error_code
            return None, error_code

        except Exception as e:
            logger.error(f"浏览器自动化异常: {e}", exc_info=True)
            error_code = (
                "DEVICE_CODE_TIMEOUT"
                if self._remaining_seconds(deadline) <= 0
                else "DEVICE_CODE_FAILED"
            )
            self._last_device_code_error = error_code
            return None, error_code
    
    async def _get_xbox_live_tokens(self) -> Optional[XboxLiveTokens]:
        """
        获取Xbox Live令牌
        
        返回:
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