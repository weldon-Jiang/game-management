"""
Xbox PlaySession 管理器
======================

功能说明：
- 管理Xbox流播放会话的创建和生命周期
- 实现与Xbox Live服务器的HTTP API交互
- 支持创建播放会话、SDP握手等核心功能

技术实现参考（streaming项目）：
- Xbox Live PlaySession API
- WebRTC SDP交换协议

API端点：
- 服务器发现: /v6/servers/home
- 会话创建: /v6/sessions/home/play
- SDP交换: /v6/sessions/{sessionId}/sdp

作者：技术团队
版本：1.0
"""

import asyncio
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from enum import Enum

from ..core.logger import get_logger


class SessionState(Enum):
    """会话状态枚举"""
    IDLE = "idle"
    CREATING = "creating"
    WAITING_SDP = "waiting_sdp"
    CONNECTED = "connected"
    STREAMING = "streaming"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class PlaySessionConfig:
    """播放会话配置"""
    client_session_id: str = ""
    title_id: str = ""
    server_id: str = ""
    nano_version: str = "V3;WebrtcTransport.dll"
    os_name: str = "windows"
    sdk_type: str = "web"
    use_ice_connection: bool = False


@dataclass
class SDPConfiguration:
    """SDP配置"""
    chat_codec: str = "opus"
    control_min_version: int = 1
    control_max_version: int = 3
    input_min_version: int = 1
    input_max_version: int = 8


@dataclass
class PlaySession:
    """播放会话信息"""
    session_id: str = ""
    client_session_id: str = ""
    server_id: str = ""
    state: SessionState = SessionState.IDLE
    created_at: float = 0
    sdp_offer: Optional[str] = None
    sdp_answer: Optional[str] = None


class XboxPlaySessionManager:
    """
    Xbox PlaySession 会话管理器

    功能说明：
    - 创建和管理Xbox流播放会话
    - 与Xbox Live API交互
    - 处理SDP握手

    使用方式：
    - 创建实例后调用 create_session() 创建会话
    - 调用 exchange_sdp() 完成SDP交换
    - 使用完毕后调用 close_session() 关闭会话
    """

    BASE_URL = "https://uks.core.gssv-play-prodxhome.xboxlive.com"

    def __init__(self):
        self.logger = get_logger('xbox_play_session')
        self._current_session: Optional[PlaySession] = None
        self._access_token: Optional[str] = None
        self._aiohttp_session: Optional[Any] = None

    async def _get_http_session(self):
        """获取或创建aiohttp会话"""
        if self._aiohttp_session is None or self._aiohttp_session.closed:
            import aiohttp
            self._aiohttp_session = aiohttp.ClientSession()
        return self._aiohttp_session

    async def close(self):
        """关闭HTTP会话"""
        if self._aiohttp_session and not self._aiohttp_session.closed:
            await self._aiohttp_session.close()

    def set_access_token(self, token: str):
        """
        设置访问令牌

        参数：
        - token: Xbox Live访问令牌
        """
        self._access_token = token
        self.logger.debug("Access token set for PlaySession manager")

    async def discover_servers(self) -> List[Dict[str, Any]]:
        """
        发现可用的Xbox服务器

        返回：
        - 服务器列表
        """
        if not self._access_token:
            self.logger.error("No access token available for server discovery")
            return []

        try:
            import aiohttp
            session = await self._get_http_session()
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'x-xbl-contract-version': '1'
            }

            url = f"{self.BASE_URL}/v6/servers/home"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    servers = data.get('results', [])
                    self.logger.info(f"Discovered {len(servers)} Xbox servers")
                    return servers
                else:
                    text = await resp.text()
                    self.logger.error(f"Server discovery failed: {resp.status} - {text}")
                    return []

        except asyncio.TimeoutError:
            self.logger.error("Server discovery timeout")
        except Exception as e:
            self.logger.error(f"Server discovery error: {e}")

        return []

    async def create_session(
        self,
        server_id: str,
        title_id: str = "",
        config: Optional[PlaySessionConfig] = None
    ) -> Optional[PlaySession]:
        """
        创建播放会话

        参数：
        - server_id: Xbox服务器ID
        - title_id: 游戏Title ID
        - config: 会话配置

        返回：
        - PlaySession对象或None
        """
        if not self._access_token:
            self.logger.error("No access token available for session creation")
            return None

        if config is None:
            config = PlaySessionConfig(
                server_id=server_id,
                title_id=title_id
            )
        else:
            config.server_id = server_id
            if title_id:
                config.title_id = title_id

        try:
            import aiohttp
            session = await self._get_http_session()
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self.BASE_URL}/v6/servers/home"
            data = {
                "clientSessionId": config.client_session_id or "",
                "titleId": config.title_id or "",
                "serverId": server_id,
                "settings": {
                    "nanoVersion": config.nano_version,
                    "osName": config.os_name,
                    "sdkType": config.sdk_type,
                    "useIceConnection": config.use_ice_connection
                }
            }

            async with session.post(
                url,
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status in (200, 201):
                    response_data = await resp.json()
                    self.logger.info(f"PlaySession created: {server_id}")

                    self._current_session = PlaySession(
                        session_id=response_data.get('sessionId', ''),
                        client_session_id=response_data.get('clientSessionId', ''),
                        server_id=server_id,
                        state=SessionState.WAITING_SDP,
                        created_at=asyncio.get_event_loop().time()
                    )
                    return self._current_session
                else:
                    text = await resp.text()
                    self.logger.error(f"Session creation failed: {resp.status} - {text}")
                    return None

        except asyncio.TimeoutError:
            self.logger.error("Session creation timeout")
        except Exception as e:
            self.logger.error(f"Session creation error: {e}")

        return None

    async def exchange_sdp(
        self,
        session_id: str,
        sdp_offer: str,
        sdp_config: Optional[SDPConfiguration] = None
    ) -> Optional[str]:
        """
        交换SDP建立WebRTC连接

        参数：
        - session_id: 会话ID
        - sdp_offer: WebRTC Offer SDP
        - sdp_config: SDP配置

        返回：
        - Answer SDP或None
        """
        if not self._access_token:
            self.logger.error("No access token for SDP exchange")
            return None

        if sdp_config is None:
            sdp_config = SDPConfiguration()

        try:
            import aiohttp
            session = await self._get_http_session()
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self.BASE_URL}/v6/servers/home/sdp"
            data = {
                "messageType": "offer",
                "sdp": sdp_offer,
                "configuration": {
                    "chatConfiguration": {"codec": sdp_config.chat_codec},
                    "control": {
                        "minVersion": sdp_config.control_min_version,
                        "maxVersion": sdp_config.control_max_version
                    },
                    "input": {
                        "minVersion": sdp_config.input_min_version,
                        "maxVersion": sdp_config.input_max_version
                    }
                }
            }

            async with session.post(
                url,
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    sdp_answer = response_data.get('sdp', '')
                    self.logger.info("SDP exchange successful")

                    if self._current_session:
                        self._current_session.sdp_offer = sdp_offer
                        self._current_session.sdp_answer = sdp_answer
                        self._current_session.state = SessionState.CONNECTED

                    return sdp_answer
                else:
                    text = await resp.text()
                    self.logger.error(f"SDP exchange failed: {resp.status} - {text}")
                    return None

        except asyncio.TimeoutError:
            self.logger.error("SDP exchange timeout")
        except Exception as e:
            self.logger.error(f"SDP exchange error: {e}")

        return None

    async def close_session(self, session_id: str = None) -> bool:
        """
        关闭播放会话

        参数：
        - session_id: 会话ID（可选，默认关闭当前会话）

        返回：
        - 是否成功
        """
        sid = session_id or (self._current_session.session_id if self._current_session else None)
        if not sid:
            self.logger.warning("No session to close")
            return False

        try:
            import aiohttp
            session = await self._get_http_session()
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'x-xbl-contract-version': '1'
            }

            url = f"{self.BASE_URL}/v6/servers/home"
            async with session.delete(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status in (200, 204):
                    self.logger.info(f"Session closed: {sid}")
                    if self._current_session:
                        self._current_session.state = SessionState.DISCONNECTED
                    return True
                else:
                    self.logger.warning(f"Session close returned: {resp.status}")
                    return False

        except Exception as e:
            self.logger.error(f"Session close error: {e}")
            return False

    @property
    def current_session(self) -> Optional[PlaySession]:
        """获取当前会话"""
        return self._current_session

    @property
    def is_session_active(self) -> bool:
        """检查会话是否活跃"""
        return (
            self._current_session is not None
            and self._current_session.state in (
                SessionState.WAITING_SDP,
                SessionState.CONNECTED,
                SessionState.STREAMING
            )
        )


xbox_play_session_manager = XboxPlaySessionManager()
