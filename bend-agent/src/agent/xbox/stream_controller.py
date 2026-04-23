"""
Xbox streaming controller for Bend Agent

功能说明：
- 通过SmartGlass协议控制Xbox主机
- 建立TCP连接与Xbox通信
- 支持Xbox流媒体控制、按键输入、云游戏连接等

技术原理：
- SmartGlass是微软的远程控制协议
- 基于TCP Socket通信，使用JSON格式数据包
- 数据包包含4字节长度头 + JSON内容

主要功能：
- 与Xbox建立连接和握手
- 启动/停止流媒体
- 发送按键和摇杆输入
- 获取Xbox状态信息
"""
import asyncio
import json
import struct
from dataclasses import dataclass
from typing import Optional, Dict, Any
from enum import Enum

from ..core.logger import get_logger


class StreamState(Enum):
    """
    流媒体状态枚举

    状态流转：
    IDLE（空闲）→ CONNECTING（连接中）→ CONNECTED（已连接）
                                            ↓
                                      STREAMING（流媒体中）
                                            ↓
                                    DISCONNECTING（断开中）
                                       ↓            ↓
                                   ERROR（错误）  IDLE（空闲）
    """
    IDLE = "idle"                 # 空闲状态
    CONNECTING = "connecting"     # 连接中
    CONNECTED = "connected"       # 已连接
    STREAMING = "streaming"       # 流媒体进行中
    DISCONNECTING = "disconnecting"  # 断开中
    ERROR = "error"              # 错误状态


@dataclass
class StreamConfig:
    """
    流媒体配置数据类

    属性说明：
    - xbox_ip: Xbox主机IP地址
    - xbox_port: SmartGlass端口，默认5050
    - video_width: 视频宽度，默认1280
    - video_height: 视频高度，默认720
    - video_framerate: 视频帧率，默认30fps
    - video_bitrate: 视频码率，默认5Mbps
    - audio_enabled: 是否启用音频，默认True
    """
    xbox_ip: str                          # Xbox IP地址
    xbox_port: int = 5050                # SmartGlass端口
    video_width: int = 1280              # 视频宽度
    video_height: int = 720              # 视频高度
    video_framerate: int = 30            # 视频帧率
    video_bitrate: int = 5000000          # 视频码率（5Mbps）
    audio_enabled: bool = True           # 是否启用音频


class XboxStreamController:
    """
    Xbox SmartGlass 流媒体控制器

    功能说明：
    - 与Xbox主机建立TCP连接
    - 通过SmartGlass协议进行通信
    - 控制流媒体会话的启动和停止
    - 发送游戏手柄输入指令

    使用方式：
    - 创建实例后调用 connect() 连接Xbox
    - 连接成功后调用 start_stream() 开始流媒体
    - 使用 press_button()、move_stick() 等方法控制
    - 不使用时调用 disconnect() 断开连接
    """

    SMARTGLASS_PORT = 5050  # SmartGlass协议默认端口
    PROTOCOL_VERSION = "1.0"  # 协议版本号

    def __init__(self):
        """初始化流媒体控制器"""
        self.logger = get_logger('xbox_stream')  # 日志记录器
        self._state = StreamState.IDLE  # 当前流媒体状态
        self._reader: Optional[asyncio.StreamReader] = None  # TCP读取流
        self._writer: Optional[asyncio.StreamWriter] = None  # TCP写入流
        self._current_xbox: Optional[str] = None  # 当前连接的Xbox IP
        self._stream_config: Optional[StreamConfig] = None  # 流媒体配置

    @property
    def state(self) -> StreamState:
        """
        获取当前流媒体状态

        返回值：StreamState枚举值
        """
        return self._state

    @property
    def is_connected(self) -> bool:
        """
        检查是否已连接到Xbox

        返回值：
        - True: 已连接（状态为CONNECTED或STREAMING）
        - False: 未连接
        """
        return self._state in [StreamState.CONNECTED, StreamState.STREAMING]

    async def connect(self, xbox_ip: str, port: int = None) -> bool:
        """
        连接到Xbox主机

        参数说明：
        - xbox_ip: Xbox主机IP地址
        - port: SmartGlass端口（可选，默认5050）

        返回值：
        - True: 连接成功
        - False: 连接失败

        连接流程：
        1. 如果已连接到其他Xbox，先断开
        2. 建立TCP连接
        3. 进行SmartGlass握手
        4. 握手成功则状态变为CONNECTED
        """
        # 如果已连接到同一Xbox，直接返回成功
        if self.is_connected:
            self.logger.warning(f"Already connected to {self._current_xbox}")
            if self._current_xbox == xbox_ip:
                return True
            await self.disconnect()

        port = port or self.SMARTGLASS_PORT
        self._state = StreamState.CONNECTING
        self._current_xbox = xbox_ip

        try:
            self.logger.info(f"Connecting to Xbox at {xbox_ip}:{port}...")
            # 建立TCP连接，10秒超时
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(xbox_ip, port),
                timeout=10
            )

            # 进行握手
            if await self._handshake():
                self._state = StreamState.CONNECTED
                self.logger.info(f"Connected to Xbox: {xbox_ip}")
                return True
            else:
                raise Exception("Handshake failed")

        except asyncio.TimeoutError:
            self.logger.error(f"Connection timeout to Xbox: {xbox_ip}")
            self._state = StreamState.ERROR
        except Exception as e:
            self.logger.error(f"Failed to connect to Xbox: {e}")
            self._state = StreamState.ERROR
            self._reader = None
            self._writer = None

        return False

    async def disconnect(self):
        """
        断开与Xbox的连接

        功能说明：
        - 关闭TCP连接
        - 重置所有状态
        - 状态变为IDLE
        """
        if self._state == StreamState.IDLE:
            return

        self._state = StreamState.DISCONNECTING

        try:
            if self._writer:
                self._writer.close()
                await asyncio.wait_for(self._writer.wait_closed(), timeout=5)
        except Exception as e:
            self.logger.error(f"Error closing connection: {e}")
        finally:
            self._reader = None
            self._writer = None
            self._current_xbox = None
            self._state = StreamState.IDLE
            self.logger.info("Disconnected from Xbox")

    async def _handshake(self) -> bool:
        """
        执行SmartGlass握手

        返回值：
        - True: 握手成功
        - False: 握手失败

        握手流程：
        1. 发送握手请求（包含协议版本等信息）
        2. 等待并验证响应
        """
        try:
            # 构建并发送握手请求
            handshake_request = self._build_handshake_request()
            self._writer.write(handshake_request)
            await asyncio.wait_for(self._writer.drain(), timeout=5)

            # 接收响应
            response = await asyncio.wait_for(self._reader.read(1024), timeout=10)
            if response:
                self.logger.debug(f"Handshake response received: {len(response)} bytes")
                return True

        except Exception as e:
            self.logger.error(f"Handshake error: {e}")

        return False

    def _build_handshake_request(self) -> bytes:
        """
        构建SmartGlass握手请求

        返回值：握手请求的字节数据

        数据格式：
        - 4字节长度头（大端序）
        - JSON内容（UTF-8编码）
        """
        content = json.dumps({
            "protocol": "xbox.smartglass",
            "version": self.PROTOCOL_VERSION,
            "transport": "ws"
        })

        # 4字节长度头 + JSON内容
        header = struct.pack('>I', len(content))
        return header + content.encode('utf-8')

    async def start_stream(self, config: StreamConfig) -> bool:
        """
        启动流媒体

        参数说明：
        - config: 流媒体配置（分辨率、帧率、码率等）

        返回值：
        - True: 启动成功
        - False: 启动失败

        前置条件：
        - 必须已成功连接到Xbox
        """
        if not self.is_connected:
            self.logger.error("Not connected to Xbox")
            return False

        if self._state == StreamState.STREAMING:
            self.logger.warning("Already streaming")
            return True

        self._stream_config = config
        self._state = StreamState.STREAMING

        try:
            await self._send_stream_start(config)
            self.logger.info(f"Streaming started: {config.video_width}x{config.video_height}@{config.video_framerate}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to start streaming: {e}")
            self._state = StreamState.ERROR
            return False

    async def stop_stream(self):
        """
        停止流媒体

        功能说明：
        - 发送停止流媒体命令
        - 状态从STREAMING变为CONNECTED
        """
        if self._state != StreamState.STREAMING:
            return

        try:
            await self._send_stream_stop()
            self._state = StreamState.CONNECTED
            self.logger.info("Streaming stopped")
        except Exception as e:
            self.logger.error(f"Error stopping stream: {e}")
            self._state = StreamState.ERROR

    async def _send_stream_start(self, config: StreamConfig):
        """
        发送启动流媒体命令

        参数说明：
        - config: 流媒体配置
        """
        command = {
            "type": "start_stream",
            "config": {
                "width": config.video_width,
                "height": config.video_height,
                "framerate": config.video_framerate,
                "bitrate": config.video_bitrate,
                "audio": config.audio_enabled
            }
        }
        await self._send_command(command)

    async def _send_stream_stop(self):
        """发送停止流媒体命令"""
        command = {"type": "stop_stream"}
        await self._send_command(command)

    async def _send_command(self, command: Dict[str, Any]):
        """
        发送命令到Xbox

        参数说明：
        - command: 命令字典

        数据格式：
        - 4字节长度头（大端序）
        - JSON内容（UTF-8编码）
        """
        if not self._writer:
            raise Exception("Not connected")

        try:
            content = json.dumps(command)
            header = struct.pack('>I', len(content))
            self._writer.write(header + content.encode('utf-8'))
            await asyncio.wait_for(self._writer.drain(), timeout=5)
        except Exception as e:
            self.logger.error(f"Failed to send command: {e}")
            raise

    async def send_input(self, input_type: str, data: Dict[str, Any]):
        """
        发送输入命令到Xbox

        参数说明：
        - input_type: 输入类型（button/stick/trigger）
        - data: 输入数据

        示例：
        - send_input("button", {"button": "a", "press": True})
        - send_input("stick", {"stick": "left", "x": 0.5, "y": -0.5})
        """
        if not self.is_connected:
            raise Exception("Not connected to Xbox")

        command = {
            "type": "input",
            "input_type": input_type,
            **data
        }
        await self._send_command(command)

    async def press_button(self, button: str, duration: float = 0.1):
        """
        按下Xbox手柄按钮

        参数说明：
        - button: 按钮名称（a, b, x, y, start, guide, etc.）
        - duration: 按下持续时间（秒）

        实现说明：
        - 先发送按下事件
        - 等待指定时间
        - 再发送释放事件
        """
        await self.send_input("button", {"button": button, "press": True})
        await asyncio.sleep(duration)
        await self.send_input("button", {"button": button, "press": False})

    async def move_stick(self, stick: str, x: float, y: float):
        """
        移动模拟摇杆

        参数说明：
        - stick: 摇杆名称（left/right）
        - x: X轴值（-1.0 到 1.0）
        - y: Y轴值（-1.0 到 1.0）

        摇杆布局（左手为例）：
        - x=0, y=-1: 向上推
        - x=1, y=0: 向右推
        - x=0, y=1: 向下推
        - x=-1, y=0: 向左推
        """
        await self.send_input("stick", {"stick": stick, "x": x, "y": y})

    async def connect_with_token(
        self,
        xbox_ip: str,
        xbox_token: str,
        user_hash: str,
        port: int = None
    ) -> bool:
        """
        使用 Xbox Live Token 连接到 Xbox 主机

        Args:
            xbox_ip: Xbox IP 地址
            xbox_token: Xbox Live Token
            user_hash: 用户哈希 (uhs)
            port: SmartGlass 端口（可选，默认5050）

        Returns:
            True: 连接成功
            False: 连接失败
        """
        if self.is_connected:
            if self._current_xbox == xbox_ip:
                return True
            await self.disconnect()

        port = port or self.SMARTGLASS_PORT
        self._state = StreamState.CONNECTING
        self._current_xbox = xbox_ip

        try:
            self.logger.info(f"Connecting to Xbox with token: {xbox_ip}:{port}")

            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(xbox_ip, port),
                timeout=10
            )

            # 使用 token 进行握手
            if await self._token_handshake(xbox_token, user_hash):
                self._state = StreamState.CONNECTED
                self.logger.info(f"Connected to Xbox with token: {xbox_ip}")
                return True
            else:
                raise Exception("Token handshake failed")

        except asyncio.TimeoutError:
            self.logger.error(f"Connection timeout: {xbox_ip}")
            self._state = StreamState.ERROR
        except Exception as e:
            self.logger.error(f"Failed to connect with token: {e}")
            self._state = StreamState.ERROR
            self._reader = None
            self._writer = None

        return False

    async def _token_handshake(self, xbox_token: str, user_hash: str) -> bool:
        """
        使用 Xbox Live Token 执行握手

        Args:
            xbox_token: Xbox Live Token
            user_hash: 用户哈希

        Returns:
            True: 握手成功
            False: 握手失败
        """
        try:
            handshake_request = self._build_token_handshake_request(xbox_token, user_hash)
            self._writer.write(handshake_request)
            await asyncio.wait_for(self._writer.drain(), timeout=5)

            response = await asyncio.wait_for(self._reader.read(1024), timeout=10)
            if response:
                self.logger.debug(f"Token handshake response: {len(response)} bytes")
                return True

        except Exception as e:
            self.logger.error(f"Token handshake error: {e}")

        return False

    def _build_token_handshake_request(self, xbox_token: str, user_hash: str) -> bytes:
        """
        构建带 Token 的握手请求

        Args:
            xbox_token: Xbox Live Token
            user_hash: 用户哈希

        Returns:
            握手请求字节数据
        """
        content = json.dumps({
            "protocol": "xbox.smartglass",
            "version": self.PROTOCOL_VERSION,
            "transport": "ws",
            "auth": {
                "token": xbox_token,
                "uhs": user_hash
            }
        })

        header = struct.pack('>I', len(content))
        return header + content.encode('utf-8')

    async def bind_streaming_account(
        self,
        streaming_account_id: str,
        email: str
    ) -> bool:
        """
        绑定流媒体账号到当前 Xbox 会话

        Args:
            streaming_account_id: 流媒体账号ID
            email: 微软账号邮箱

        Returns:
            True: 绑定成功
            False: 绑定失败
        """
        if not self.is_connected:
            self.logger.error("Not connected, cannot bind streaming account")
            return False

        try:
            command = {
                "type": "bind_account",
                "account": {
                    "streaming_id": streaming_account_id,
                    "email": email
                }
            }
            await self._send_command(command)
            self.logger.info(f"Streaming account bound: {streaming_account_id}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to bind streaming account: {e}")
            return False

    async def get_xbox_status(self) -> Optional[Dict[str, Any]]:
        """
        获取Xbox状态信息

        返回值：
        - 包含连接状态的字典
        - None: 未连接到Xbox
        """
        if not self.is_connected:
            return None

        try:
            command = {"type": "get_status"}
            await self._send_command(command)
            return {"connected": True, "ip": self._current_xbox}
        except Exception as e:
            self.logger.error(f"Failed to get status: {e}")
            return None


# 全局流媒体控制器实例
xbox_stream_controller = XboxStreamController()
