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
- Provisioned 状态轮询机制

API端点：
- 服务器发现: /v6/servers/home
- 会话创建: /{playPath}
- 状态查询: /{sessionPath}/state
- SDP交换: /{sessionPath}/sdp

作者：技术团队
版本：2.0

版本历史：
- 1.0: 初始版本
- 2.0: 参考streaming项目修复SDP API路径和响应解析
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
    PROVISIONING = "provisioning"
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
    enable_text_to_speech: bool = False
    high_contrast: int = 0
    locale: str = "en-US"
    timezone_offset_minutes: int = 120


@dataclass
class SDPConfiguration:
    """SDP配置"""
    chat_codec: str = "opus"
    chat_sample_rate: int = 24000
    chat_channels: int = 1
    bytes_per_sample: int = 2
    expected_clip_duration_ms: int = 20
    container: str = "webm"
    control_min_version: int = 1
    control_max_version: int = 3
    input_min_version: int = 1
    input_max_version: int = 8


@dataclass
class PlaySession:
    """播放会话信息"""
    session_id: str = ""
    session_path: str = ""
    client_session_id: str = ""
    server_id: str = ""
    play_path: str = ""
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

    参考 streaming 项目实现：
    - 使用 playPath 动态构建会话创建URL
    - 轮询等待 Provisioned 状态
    - SDP交换使用 sessionPath 而非固定路径
    - SDP响应从 exchangeResponse.sdp 字段提取

    使用方式：
    - 创建实例后调用 discover_servers() 发现主机
    - 调用 create_session() 创建会话（会自动轮询 Provisioned）
    - 调用 exchange_sdp() 完成SDP交换
    - 使用完毕后调用 close_session() 关闭会话
    """

    BASE_URL = "https://uks.core.gssv-play-prodxhome.xboxlive.com"
    PROVISION_TIMEOUT = 30
    PROVISION_POLL_INTERVAL = 1
    SDP_POLL_TIMEOUT = 10
    SDP_POLL_INTERVAL = 1

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

        参考 streaming 项目返回完整的服务器信息，包括：
        - serverId: Xbox服务器ID
        - playPath: 播放路径（用于创建会话）
        - powerState: 电源状态
        - consoleType: 主机类型

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
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self.BASE_URL}/v6/servers/home"
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    servers = data.get('results', [])
                    total_items = data.get('totalItems', 0)

                    self.logger.info(f"Discovered {len(servers)} Xbox servers (total: {total_items})")

                    for server in servers:
                        self.logger.debug(f"  - Server: {server.get('serverId')}, "
                                        f"Type: {server.get('consoleType')}, "
                                        f"Power: {server.get('powerState')}, "
                                        f"PlayPath: {server.get('playPath')}")

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
        play_path: str,
        title_id: str = "",
        config: Optional[PlaySessionConfig] = None
    ) -> Optional[PlaySession]:
        """
        创建播放会话

        参考 streaming 项目实现：
        1. POST 到 /{playPath} 创建会话
        2. 响应包含 sessionId 和 sessionPath
        3. 轮询 /{sessionPath}/state 直到状态变为 Provisioned

        参数：
        - server_id: Xbox服务器ID
        - play_path: 播放路径（从 discover_servers 获取）
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

        try:
            import aiohttp
            session = await self._get_http_session()
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self.BASE_URL}/{play_path}"
            data = {
                "clientSessionId": config.client_session_id or "",
                "titleId": config.title_id or "",
                "systemUpdateGroup": "",
                "settings": {
                    "enableTextToSpeech": config.enable_text_to_speech,
                    "highContrast": config.high_contrast,
                    "locale": config.locale,
                    "nanoVersion": config.nano_version,
                    "osName": config.os_name,
                    "sdkType": config.sdk_type,
                    "timezoneOffsetMinutes": config.timezone_offset_minutes,
                    "useIceConnection": config.use_ice_connection,
                },
                "serverId": server_id,
                "fallbackRegionNames": [None]
            }

            self.logger.info(f"Creating PlaySession for server {server_id}...")
            async with session.post(
                url,
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                response_data = await resp.json()

                if resp.status in (200, 201):
                    session_id = response_data.get('sessionId', '')
                    session_path = response_data.get('sessionPath', '')
                    state = response_data.get('state', '')

                    self.logger.info(f"PlaySession created: {session_id}, state: {state}")

                    self._current_session = PlaySession(
                        session_id=session_id,
                        session_path=session_path,
                        client_session_id=response_data.get('clientSessionId', ''),
                        server_id=server_id,
                        play_path=play_path,
                        state=SessionState.PROVISIONING,
                        created_at=asyncio.get_event_loop().time()
                    )

                    if state == "Provisioned":
                        self.logger.info("Session already provisioned")
                        self._current_session.state = SessionState.WAITING_SDP
                        return self._current_session

                    provisioned = await self._wait_for_provision(
                        session_path, headers, session
                    )

                    if provisioned:
                        self._current_session.state = SessionState.WAITING_SDP
                        self.logger.info("Session provisioned successfully")
                        return self._current_session
                    else:
                        self.logger.error("Session provisioning timeout or failed")
                        self._current_session.state = SessionState.ERROR
                        return None
                else:
                    text = await resp.text()
                    self.logger.error(f"Session creation failed: {resp.status} - {text}")
                    return None

        except asyncio.TimeoutError:
            self.logger.error("Session creation timeout")
        except Exception as e:
            self.logger.error(f"Session creation error: {e}")

        return None

    async def _wait_for_provision(
        self,
        session_path: str,
        headers: Dict[str, str],
        http_session
    ) -> bool:
        """
        轮询等待会话 Provisioned 状态

        参考 streaming 项目实现：
        - 轮询 /{sessionPath}/state
        - 超时时间 30 秒
        - 轮询间隔 1 秒

        参数：
        - session_path: 会话路径
        - headers: HTTP 请求头
        - http_session: aiohttp 会话

        返回：
        - 是否成功 Provisioned
        """
        self.logger.info(f"Waiting for session provisioning: {session_path}")

        for attempt in range(self.PROVISION_TIMEOUT):
            await asyncio.sleep(self.PROVISION_POLL_INTERVAL)

            try:
                state_url = f"{self.BASE_URL}/{session_path}/state"
                async with http_session.get(
                    state_url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        state_data = await resp.json()
                        state = state_data.get('state', '')

                        self.logger.debug(f"Provisioning attempt {attempt + 1}: state={state}")

                        if state == "Provisioned":
                            return True
                        elif state in ("Failed", "Error", "Cancelled"):
                            self.logger.error(f"Session provisioning failed: {state}")
                            return False
            except Exception as e:
                self.logger.warning(f"State poll error (attempt {attempt + 1}): {e}")

        self.logger.error(f"Session provisioning timeout after {self.PROVISION_TIMEOUT}s")
        return False

    async def exchange_sdp(
        self,
        session_id: str = None,
        sdp_offer: str = None,
        sdp_config: Optional[SDPConfiguration] = None
    ) -> Optional[str]:
        """
        交换SDP建立WebRTC连接

        参考 streaming 项目实现：
        1. POST 到 /{sessionPath}/sdp 发送 Offer
        2. 可能返回 200 (直接返回) 或 202 (异步，需要轮询)
        3. SDP Answer 从 exchangeResponse.sdp 字段提取

        参数：
        - session_id: 会话ID（可选，默认使用当前会话）
        - sdp_offer: WebRTC Offer SDP（可选，默认使用当前会话的）
        - sdp_config: SDP配置

        返回：
        - Answer SDP或None
        """
        if not self._access_token:
            self.logger.error("No access token for SDP exchange")
            return None

        session = self._current_session
        if session_id and not session:
            self.logger.warning("No current session, SDP exchange requires active session")
            return None

        use_session = session or self._current_session
        if not use_session or not use_session.session_path:
            self.logger.error("No session path available for SDP exchange")
            return None

        if sdp_config is None:
            sdp_config = SDPConfiguration()

        actual_sdp_offer = sdp_offer or use_session.sdp_offer
        if not actual_sdp_offer:
            self.logger.error("No SDP offer available")
            return None

        try:
            import aiohttp
            http_session = await self._get_http_session()
            headers = {
                'Authorization': f'Bearer {self._access_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self.BASE_URL}/{use_session.session_path}/sdp"
            data = {
                "messageType": "offer",
                "sdp": actual_sdp_offer,
                "configuration": {
                    "chatConfiguration": {
                        "codec": sdp_config.chat_codec,
                        "container": sdp_config.container,
                        "numChannels": sdp_config.chat_channels,
                        "sampleFrequencyHz": sdp_config.chat_sample_rate,
                        "bytesPerSample": sdp_config.bytes_per_sample,
                        "expectedClipDurationMs": sdp_config.expected_clip_duration_ms
                    },
                    "chat": {
                        "minVersion": 1,
                        "maxVersion": 1
                    },
                    "control": {
                        "minVersion": sdp_config.control_min_version,
                        "maxVersion": sdp_config.control_max_version
                    },
                    "input": {
                        "minVersion": sdp_config.input_min_version,
                        "maxVersion": sdp_config.input_max_version
                    },
                    "message": {
                        "minVersion": 1,
                        "maxVersion": 1
                    }
                }
            }

            self.logger.info("Starting SDP exchange...")
            async with http_session.post(
                url,
                json=data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    sdp_answer = self._extract_sdp_from_response(response_data)

                    if sdp_answer:
                        self.logger.info("SDP exchange successful (direct response)")
                        if use_session:
                            use_session.sdp_offer = actual_sdp_offer
                            use_session.sdp_answer = sdp_answer
                            use_session.state = SessionState.CONNECTED
                        return sdp_answer
                    else:
                        self.logger.error("Failed to extract SDP from response")
                        return None

                elif resp.status == 202:
                    self.logger.info("SDP exchange async (202), polling for answer...")
                    sdp_answer = await self._poll_sdp_answer(
                        url, headers, http_session
                    )

                    if sdp_answer:
                        self.logger.info("SDP exchange successful (polled response)")
                        if use_session:
                            use_session.sdp_offer = actual_sdp_offer
                            use_session.sdp_answer = sdp_answer
                            use_session.state = SessionState.CONNECTED
                        return sdp_answer
                    else:
                        self.logger.error("Failed to get SDP answer after polling")
                        return None

                else:
                    text = await resp.text()
                    self.logger.error(f"SDP exchange failed: {resp.status} - {text}")
                    return None

        except asyncio.TimeoutError:
            self.logger.error("SDP exchange timeout")
        except Exception as e:
            self.logger.error(f"SDP exchange error: {e}")

        return None

    def _extract_sdp_from_response(self, response_data: Dict[str, Any]) -> Optional[str]:
        """
        从SDP响应中提取Answer SDP

        参考 streaming 项目实现：
        - 响应格式: {"exchangeResponse": "{\"sdp\": \"...\"}"}
        - 需要解析 JSON 字符串中的 sdp 字段

        参数：
        - response_data: API 响应数据

        返回：
        - SDP字符串或None
        """
        try:
            if 'sdp' in response_data:
                return response_data['sdp']

            if 'exchangeResponse' in response_data:
                exchange_response = response_data['exchangeResponse']
                if isinstance(exchange_response, str):
                    exchange_data = json.loads(exchange_response)
                    return exchange_data.get('sdp')
                elif isinstance(exchange_response, dict):
                    return exchange_response.get('sdp')

            self.logger.warning(f"Unexpected SDP response format: {response_data}")
            return None

        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse exchangeResponse: {e}")
            return None
        except Exception as e:
            self.logger.error(f"Failed to extract SDP: {e}")
            return None

    async def _poll_sdp_answer(
        self,
        url: str,
        headers: Dict[str, str],
        http_session
    ) -> Optional[str]:
        """
        轮询获取SDP Answer

        参考 streaming 项目实现：
        - GET /{sessionPath}/sdp
        - 轮询超时 10 秒
        - 轮询间隔 1 秒

        参数：
        - url: SDP 端点URL
        - headers: HTTP 请求头
        - http_session: aiohttp 会话

        返回：
        - Answer SDP或None
        """
        for attempt in range(self.SDP_POLL_TIMEOUT):
            await asyncio.sleep(self.SDP_POLL_INTERVAL)

            try:
                async with http_session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        response_data = await resp.json()
                        sdp_answer = self._extract_sdp_from_response(response_data)

                        if sdp_answer:
                            self.logger.info(f"SDP answer received after {attempt + 1} polls")
                            return sdp_answer

                        self.logger.debug(f"SDP poll {attempt + 1}: waiting for answer...")

                    elif resp.status == 202:
                        self.logger.debug(f"SDP poll {attempt + 1}: still processing...")

                    else:
                        self.logger.warning(f"SDP poll returned unexpected status: {resp.status}")
                        break

            except Exception as e:
                self.logger.warning(f"SDP poll error (attempt {attempt + 1}): {e}")

        self.logger.error(f"SDP polling timeout after {self.SDP_POLL_TIMEOUT}s")
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
