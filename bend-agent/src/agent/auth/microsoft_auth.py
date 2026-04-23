"""
Microsoft Account Authentication Module
=====================================

功能说明：
- 通过微软账号密码登录获取 Xbox Live 认证
- 支持 Refresh Token 自动续期
- 支持 Xbox 主机绑定

认证流程：
1. 设备代码流获取用户授权
2. 获取 Microsoft OAuth Tokens (access_token, refresh_token)
3. 使用 Tokens 获取 Xbox Live Tokens
4. Xbox Live Tokens 用于 SmartGlass 连接

作者：技术团队
版本：1.0
"""

import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

import aiohttp

from ..core.logger import get_logger
from ..core.config import config


class AuthError(Exception):
    """认证异常"""
    pass


class AuthStatus(Enum):
    """认证状态"""
    PENDING = "pending"           # 待认证
    AUTHENTICATING = "authenticating"  # 认证中
    AUTHENTICATED = "authenticated"    # 已认证
    FAILED = "failed"            # 认证失败
    EXPIRED = "expired"          # 已过期


@dataclass
class MicrosoftTokens:
    """微软 OAuth 令牌"""
    access_token: str
    refresh_token: str
    expires_in: int          # 过期时间（秒）
    expires_at: float        # 过期时间戳
    scope: str
    token_type: str = "Bearer"

    @property
    def is_expired(self) -> bool:
        """检查是否已过期"""
        return time.time() >= self.expires_at

    @property
    def needs_refresh(self) -> bool:
        """检查是否需要刷新"""
        return time.time() >= (self.expires_at - 300)  # 提前5分钟刷新


@dataclass
class XboxLiveTokens:
    """Xbox Live 令牌"""
    xbox_token: str          # Xbox Live Token
    user_hash: str           # 用户哈希 (uhs)
    expires_at: float        # 过期时间戳
    device_token: Optional[str] = None
    title_token: Optional[str] = None

    @property
    def is_expired(self) -> bool:
        """检查是否已过期"""
        return time.time() >= self.expires_at


@dataclass
class AuthenticationResult:
    """认证结果"""
    success: bool
    status: AuthStatus
    message: str
    microsoft_tokens: Optional[MicrosoftTokens] = None
    xbox_tokens: Optional[XboxLiveTokens] = None
    error_code: Optional[str] = None
    error_details: Optional[str] = None


class MicrosoftAuthenticator:
    """
    微软账号认证器

    支持：
    - 设备代码流登录（用户手动授权）
    - 账号密码直接登录（需要特殊权限）
    - Refresh Token 自动续期
    - Xbox Live Token 获取
    - Xbox 主机绑定

    使用示例：
        auth = MicrosoftAuthenticator()
        result = await auth.login_with_credentials("email@example.com", "password")
        if result.success:
            xbox_token = result.xbox_tokens.xbox_token
    """

    # 微软 OAuth 2.0 端点
    AUTHORITY = "https://login.microsoftonline.com/consumers"
    TOKEN_URL = f"{AUTHORITY}/oauth2/v2.0/token"
    DEVICE_CODE_URL = f"{AUTHORITY}/oauth2/v2.0/devicecode"
    USERINFO_URL = f"{AUTHORITY}/oauth2/v2.0/userinfo"

    # Xbox Live 认证端点
    XBOX_AUTH_URL = "https://user.auth.xboxlive.com/user/authenticate"
    XBOX_XSTS_URL = "https://xsts.auth.xboxlive.com/xsts/authorize"
    XBOX_LOGIN_URL = "https://login.xboxlive.com/oauth20/xsts.srf"

    # OAuth 客户端ID (Xbox Live 默认)
    CLIENT_ID = "00000000-0000-0000-0000-000000000000"

    # 默认作用域
    SCOPES = [
        "XboxLive.signin",
        "XboxLive.offline_access",
        "openid",
        "profile",
        "email"
    ]

    def __init__(self):
        """初始化认证器"""
        self.logger = get_logger('microsoft_auth')

        # 认证状态
        self._auth_status = AuthStatus.PENDING
        self._microsoft_tokens: Optional[MicrosoftTokens] = None
        self._xbox_tokens: Optional[XboxLiveTokens] = None

        # 用户信息
        self._user_email: Optional[str] = None
        self._user_id: Optional[str] = None

        # HTTP 会话
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def is_authenticated(self) -> bool:
        """检查是否已认证"""
        return (
            self._auth_status == AuthStatus.AUTHENTICATED
            and self._microsoft_tokens is not None
            and self._xbox_tokens is not None
        )

    @property
    def auth_status(self) -> AuthStatus:
        """获取认证状态"""
        return self._auth_status

    @property
    def xbox_token(self) -> Optional[str]:
        """获取 Xbox Live Token"""
        return self._xbox_tokens.xbox_token if self._xbox_tokens else None

    @property
    def user_hash(self) -> Optional[str]:
        """获取用户哈希"""
        return self._xbox_tokens.user_hash if self._xbox_tokens else None

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建 HTTP 会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """关闭 HTTP 会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def login_with_credentials(
        self,
        email: str,
        password: str,
        encrypted_password: Optional[str] = None,
        aes_key: Optional[str] = None
    ) -> AuthenticationResult:
        """
        使用账号密码登录

        Args:
            email: 微软账号邮箱
            password: 明文密码（如果已加密传输则忽略）
            encrypted_password: 加密后的密码（可选，与aes_key配合使用）
            aes_key: AES解密密钥（可选）

        Returns:
            AuthenticationResult: 认证结果
        """
        self._auth_status = AuthStatus.AUTHENTICATING
        self._user_email = email

        try:
            # 如果提供了加密密码，先解密
            if encrypted_password and aes_key:
                from ..utils.crypto_util import decrypt_aes
                password = decrypt_aes(encrypted_password, aes_key)
                self.logger.info(f"已解密密码 for {email}")

            self.logger.info(f"开始认证: {email}")

            # Step 1: 获取设备代码
            device_code_data = await self._get_device_code()
            if not device_code_data:
                return AuthenticationResult(
                    success=False,
                    status=AuthStatus.FAILED,
                    message="获取设备代码失败"
                )

            device_code = device_code_data["device_code"]
            user_code = device_code_data["user_code"]
            verification_url = device_code_data["verification_uri"]

            self.logger.info(f"设备代码: {user_code}, 验证URL: {verification_url}")

            # Step 2: 使用账号密码模拟登录
            # 注意：标准的 OAuth2 不支持直接用密码获取 token
            # 这里使用 Resource Owner Password Credentials 流程
            microsoft_tokens = await self._get_token_with_password(
                email,
                password,
                device_code
            )

            if not microsoft_tokens:
                return AuthenticationResult(
                    success=False,
                    status=AuthStatus.FAILED,
                    message="微软账号认证失败，请检查账号密码"
                )

            self._microsoft_tokens = microsoft_tokens

            # Step 3: 获取 Xbox Live Tokens
            xbox_tokens = await self._get_xbox_tokens(microsoft_tokens.access_token)
            if not xbox_tokens:
                return AuthenticationResult(
                    success=False,
                    status=AuthStatus.FAILED,
                    message="获取Xbox Live Token失败"
                )

            self._xbox_tokens = xbox_tokens
            self._auth_status = AuthStatus.AUTHENTICATED

            self.logger.info(f"认证成功: {email}, uhs: {xbox_tokens.user_hash}")

            return AuthenticationResult(
                success=True,
                status=AuthStatus.AUTHENTICATED,
                message="认证成功",
                microsoft_tokens=microsoft_tokens,
                xbox_tokens=xbox_tokens
            )

        except AuthError as e:
            self._auth_status = AuthStatus.FAILED
            self.logger.error(f"认证失败: {e}")
            return AuthenticationResult(
                success=False,
                status=AuthStatus.FAILED,
                message=str(e),
                error_code="AUTH_ERROR"
            )

        except Exception as e:
            self._auth_status = AuthStatus.FAILED
            self.logger.error(f"认证异常: {e}")
            return AuthenticationResult(
                success=False,
                status=AuthStatus.FAILED,
                message=f"认证异常: {str(e)}",
                error_code="EXCEPTION",
                error_details=traceback.format_exc()
            )

    async def _get_device_code(self) -> Optional[Dict[str, Any]]:
        """获取设备代码（用于用户授权）"""
        data = {
            "client_id": self.CLIENT_ID,
            "scope": " ".join(self.SCOPES)
        }

        try:
            session = await self._get_session()
            async with session.post(self.DEVICE_CODE_URL, data=data) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    text = await resp.text()
                    self.logger.error(f"获取设备代码失败: {resp.status}, {text}")
                    return None
        except Exception as e:
            self.logger.error(f"获取设备代码异常: {e}")
            return None

    async def _get_token_with_password(
        self,
        email: str,
        password: str,
        device_code: str
    ) -> Optional[MicrosoftTokens]:
        """
        使用密码凭证获取 Token

        注意：微软已不再推荐使用 ROPC 流程，某些账号类型可能不支持
        """
        data = {
            "grant_type": "password",
            "client_id": self.CLIENT_ID,
            "username": email,
            "password": password,
            "scope": " ".join(self.SCOPES)
        }

        try:
            session = await self._get_session()
            async with session.post(self.TOKEN_URL, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    expires_at = time.time() + result.get("expires_in", 3600)

                    return MicrosoftTokens(
                        access_token=result["access_token"],
                        refresh_token=result.get("refresh_token", ""),
                        expires_in=result.get("expires_in", 3600),
                        expires_at=expires_at,
                        scope=result.get("scope", ""),
                        token_type=result.get("token_type", "Bearer")
                    )
                else:
                    text = await resp.text()
                    self.logger.error(f"获取Token失败: {resp.status}, {text}")
                    return None

        except Exception as e:
            self.logger.error(f"获取Token异常: {e}")
            return None

    async def _get_token_with_device_code(self, device_code: str) -> Optional[MicrosoftTokens]:
        """
        使用设备代码轮询获取 Token

        用户需要：
        1. 访问 https://microsoft.com/devicelogin
        2. 输入代码
        3. 完成授权
        """
        data = {
            "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
            "client_id": self.CLIENT_ID,
            "device_code": device_code
        }

        for attempt in range(60):  # 最多等待5分钟
            await asyncio.sleep(5)

            try:
                session = await self._get_session()
                async with session.post(self.TOKEN_URL, data=data) as resp:
                    result = await resp.json()

                    if resp.status == 200:
                        expires_at = time.time() + result.get("expires_in", 3600)
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
                        continue
                    elif error in ("slow_down", "expired_token", "invalid_grant"):
                        self.logger.error(f"设备代码认证失败: {error}")
                        return None
                    else:
                        self.logger.error(f"设备代码认证未知错误: {error}")
                        return None

            except Exception as e:
                self.logger.error(f"轮询Token异常: {e}")
                continue

        self.logger.warning("设备代码认证超时")
        return None

    async def _get_xbox_tokens(self, access_token: str) -> Optional[XboxLiveTokens]:
        """
        使用 Microsoft Access Token 获取 Xbox Live Tokens

        流程：
        1. 使用 Microsoft Token 认证 Xbox Live
        2. 获取 XSTS Token
        3. 用于 SmartGlass 连接
        """
        try:
            # Step 1: Xbox Live User Authentication
            user_auth_data = {
                "Properties": {
                    "AuthMethod": "RPS",
                    "SiteName": "user.auth.xboxlive.com",
                    "RpsTicket": f"d={access_token}"
                },
                "RelyingParty": "http://auth.xboxlive.com",
                "TokenType": "JWT"
            }

            session = await self._get_session()

            async with session.post(self.XBOX_AUTH_URL, json=user_auth_data) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    self.logger.error(f"Xbox用户认证失败: {resp.status}, {text}")
                    return None

                user_result = await resp.json()
                user_token = user_result.get("Token")
                user_hash = user_result.get("DisplayClaims", {}).get("xui", [{}])[0].get("uhs", "")

            if not user_token:
                self.logger.error("未获取到Xbox用户Token")
                return None

            # Step 2: XSTS Authorization
            xsts_data = {
                "Properties": {
                    "SandboxId": "RETAIL",
                    "UserTokens": [user_token]
                },
                "RelyingParty": "http://smartglass.com",
                "TokenType": "JWT"
            }

            async with session.post(self.XBOX_XSTS_URL, json=xsts_data) as resp:
                if resp.status != 200:
                    text = await resp.text()
                    self.logger.error(f"XSTS认证失败: {resp.status}, {text}")
                    return None

                xsts_result = await resp.json()
                xsts_token = xsts_result.get("Token")
                xsts_user_hash = xsts_result.get("DisplayClaims", {}).get("xui", [{}])[0].get("uhs", "")

            # 使用 XSTS Token 作为最终 token
            final_token = xsts_token or user_token
            final_uhs = xsts_user_hash or user_hash

            # Token 有效期约24小时
            expires_at = time.time() + 86400

            return XboxLiveTokens(
                xbox_token=final_token,
                user_hash=final_uhs,
                expires_at=expires_at
            )

        except Exception as e:
            self.logger.error(f"获取Xbox Tokens异常: {e}")
            return None

    async def refresh_tokens(self) -> bool:
        """
        刷新 Access Token

        Returns:
            True: 刷新成功
            False: 刷新失败
        """
        if not self._microsoft_tokens or not self._microsoft_tokens.refresh_token:
            self.logger.warning("没有Refresh Token，无法刷新")
            return False

        try:
            data = {
                "grant_type": "refresh_token",
                "refresh_token": self._microsoft_tokens.refresh_token,
                "client_id": self.CLIENT_ID,
                "scope": " ".join(self.SCOPES)
            }

            session = await self._get_session()
            async with session.post(self.TOKEN_URL, data=data) as resp:
                if resp.status == 200:
                    result = await resp.json()

                    self._microsoft_tokens = MicrosoftTokens(
                        access_token=result["access_token"],
                        refresh_token=result.get("refresh_token", self._microsoft_tokens.refresh_token),
                        expires_in=result.get("expires_in", 3600),
                        expires_at=time.time() + result.get("expires_in", 3600),
                        scope=result.get("scope", ""),
                        token_type=result.get("token_type", "Bearer")
                    )

                    self.logger.info("Token刷新成功")
                    return True
                else:
                    text = await resp.text()
                    self.logger.error(f"Token刷新失败: {resp.status}, {text}")
                    return False

        except Exception as e:
            self.logger.error(f"Token刷新异常: {e}")
            return False

    async def ensure_valid_tokens(self) -> bool:
        """
        确保拥有有效的 Tokens，必要时刷新

        Returns:
            True: 拥有有效 Tokens
            False: 无法获取有效 Tokens
        """
        if not self._microsoft_tokens:
            return False

        # 检查是否需要刷新
        if self._microsoft_tokens.needs_refresh:
            if not await self.refresh_tokens():
                return False

        # 检查 Xbox Tokens 是否过期
        if self._xbox_tokens and self._xbox_tokens.is_expired:
            # Xbox Tokens 过期，需要重新获取
            xbox_tokens = await self._get_xbox_tokens(self._microsoft_tokens.access_token)
            if xbox_tokens:
                self._xbox_tokens = xbox_tokens
            else:
                return False

        return True

    def get_auth_info(self) -> Dict[str, Any]:
        """
        获取认证信息（用于调试和日志）

        Returns:
            认证信息字典
        """
        return {
            "status": self._auth_status.value,
            "email": self._user_email,
            "user_id": self._user_id,
            "microsoft_token_expires_at": (
                self._microsoft_tokens.expires_at if self._microsoft_tokens else None
            ),
            "xbox_token_expires_at": (
                self._xbox_tokens.expires_at if self._xbox_tokens else None
            ),
            "is_authenticated": self.is_authenticated
        }

    async def logout(self):
        """登出，清除所有认证信息"""
        self._microsoft_tokens = None
        self._xbox_tokens = None
        self._auth_status = AuthStatus.PENDING
        self._user_email = None
        self._user_id = None
        self.logger.info("已登出")
