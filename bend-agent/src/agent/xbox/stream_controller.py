"""
Bend Agent Xbox 串流控制器

功能说明：
- 通过SmartGlass协议控制Xbox主机
- 建立TCP连接与Xbox通信
- 支持Xbox流媒体控制、按键输入、云游戏连接等
- 支持混合模式视频流接收（RTP/win32gui）

技术原理：
- SmartGlass是微软的远程控制协议
- 基于TCP Socket通信，使用JSON格式数据包
- 数据包包含4字节长度头 + JSON内容
- RTP用于接收视频流（可选）

主要功能：
- 与Xbox建立连接和握手
- 启动/停止流媒体
- 发送按键和摇杆输入
- 获取Xbox状态信息
- 混合模式视频流接收（方案3）

作者：技术团队
版本：3.0

版本历史：
- 2.0: 添加手柄状态发送
- 3.0: 添加混合模式视频流接收
"""
import asyncio
import json
import struct
from dataclasses import dataclass
from typing import Optional, Dict, Any, Callable, List, Tuple
from enum import Enum

from ..core.logger import get_logger

# RTP 相关导入（方案3）
try:
    from .rtp_session import RTPSession, H264RTPPacketAssemble, RTPPacket
    from .h264_parser import H264Parser, H264FrameAssembler, NALU
    from .srtp_handler import SRTPHandler, SRTPKeys
    from .dtls_handler import DTLSHandler, SimpleDTLSHandler
    RTP_AVAILABLE = True
except ImportError as e:
    RTP_AVAILABLE = False
    logger = get_logger('xbox_stream')
    logger.warning(f"RTP模块不可用，视频流接收功能将使用win32gui: {e}")


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

    SMARTGLASS_UDP_PORT = 5050  # UDP 发现/握手专用，非 TCP 控制端口
    DEFAULT_TCP_FALLBACK_PORTS = [9002, 5555, 3074]
    PROTOCOL_VERSION = "1.0"  # 协议版本号

    def __init__(self):
        """初始化流媒体控制器"""
        self.logger = get_logger('xbox_stream')  # 日志记录器
        self._state = StreamState.IDLE  # 当前流媒体状态
        self._reader: Optional[asyncio.StreamReader] = None  # TCP读取流
        self._writer: Optional[asyncio.StreamWriter] = None  # TCP写入流
        self._current_xbox: Optional[str] = None  # 当前连接的Xbox IP
        self._stream_config: Optional[StreamConfig] = None  # 流媒体配置
        
        # 视频流接收相关（方案3：混合模式）
        self._video_mode: str = "win32gui"  # 当前视频模式: "rtp" | "win32gui"
        self._rtp_session: Optional[RTPSession] = None  # RTP会话
        self._srtp_handler: Optional[SRTPHandler] = None  # SRTP处理器
        self._h264_parser: Optional[H264Parser] = None  # H.264解析器
        self._frame_assembler: Optional[H264FrameAssembler] = None  # 帧组装器
        self._packet_assembler: Optional[H264RTPPacketAssemble] = None  # RTP分片组装器
        self._video_callback: Optional[Callable[[bytes], None]] = None  # 视频帧回调
        self._frame_callback: Optional[Callable[[Any], None]] = None  # 解码后帧回调
        self._rtp_receive_task: Optional[asyncio.Task] = None  # RTP接收任务
        self._rtp_port: int = 50500  # RTP接收端口
        self._srtp_enabled: bool = False  # SRTP是否启用
        self._lan_tcp_port: Optional[int] = None
        self._lan_udp_port: Optional[int] = None
        self._gamestream_session_id: Optional[str] = None
        self._smartglass_protocol: Optional[Any] = None

    def attach_smartglass_protocol(self, protocol: Any) -> None:
        """绑定 UDP SmartGlass 控制协议（LAN 模式唯一控制通道）。"""
        self._smartglass_protocol = protocol

    @property
    def smartglass_protocol(self) -> Optional[Any]:
        return self._smartglass_protocol

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
        if self._smartglass_protocol and getattr(self._smartglass_protocol, "is_alive", False):
            return self._state in [StreamState.CONNECTED, StreamState.STREAMING]
        return self._state in [StreamState.CONNECTED, StreamState.STREAMING]

    @property
    def input_channel_state(self) -> str:
        """LAN SmartGlass 输入通道状态（与 WebRTC DataChannel 语义对齐）。"""
        return "open" if self.is_connected else "closed"

    def is_input_channel_healthy(self) -> bool:
        """InputPump / keepalive 用：UDP SmartGlass 会话存活即视为 input 可用。"""
        if self._smartglass_protocol and getattr(self._smartglass_protocol, "is_alive", False):
            return True
        return self.is_connected

    async def send_keepalive(self) -> bool:
        """发送 SmartGlass UDP 心跳或中性手柄状态。"""
        if self._smartglass_protocol and getattr(self._smartglass_protocol, "is_alive", False):
            try:
                self._smartglass_protocol.send_heartbeat()
                return True
            except OSError as exc:
                self.logger.debug("SmartGlass heartbeat 失败: %s", exc)
                return False
        neutral = {
            "buttons": 0,
            "left_trigger": 0,
            "right_trigger": 0,
            "left_thumb_x": 0,
            "left_thumb_y": 0,
            "right_thumb_x": 0,
            "right_thumb_y": 0,
        }
        return await self.send_gamepad_state(neutral)

    async def connect(self, xbox_ip: str, port: int = None) -> bool:
        """
        @deprecated LAN 模式请使用 SmartGlass UDP 控制协议，勿再调用 TCP connect。
        """
        self.logger.warning(
            "connect() 已废弃：SmartGlass 控制通道为 UDP 5050，请走 lan_connect + SmartGlassProtocol"
        )
        return False

    async def _connect_tcp_legacy(self, xbox_ip: str, port: int = None) -> bool:
        """旧版 TCP JSON 握手（非 SmartGlass 规范，仅保留供排查）。"""
        # 如果已连接到同一Xbox，直接返回成功
        if self.is_connected:
            self.logger.warning(f"Already connected to {self._current_xbox}")
            if self._current_xbox == xbox_ip:
                return True
            await self.disconnect()

        port = port or self.SMARTGLASS_UDP_PORT
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
        - 停止RTP接收（如果启用）
        - 重置所有状态
        - 状态变为IDLE
        """
        if self._state == StreamState.IDLE:
            return

        self._state = StreamState.DISCONNECTING

        try:
            await self.stop_video_receiver()

            protocol = self._smartglass_protocol
            if protocol and hasattr(protocol, "stop"):
                try:
                    await protocol.stop()
                except Exception as exc:
                    self.logger.warning("SmartGlass protocol stop: %s", exc)
            self._smartglass_protocol = None
            
            if self._writer:
                try:
                    self._writer.close()
                    await asyncio.wait_for(self._writer.wait_closed(), timeout=5)
                except Exception as e:
                    self.logger.warning(f"Error closing writer: {e}")
            
            if self._reader:
                try:
                    self._reader.feed_eof()
                    self._reader.close()
                except Exception as e:
                    self.logger.warning(f"Error closing reader: {e}")
                    
        except Exception as e:
            self.logger.error(f"Error disconnecting: {e}")
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
        - input_type: 输入类型（button/stick/trigger/gamepad）
        - data: 输入数据

        示例：
        - send_input("button", {"button": "a", "press": True})
        - send_input("stick", {"stick": "left", "x": 0.5, "y": -0.5})
        - send_input("gamepad", {"buttons": 0x0001, "left_trigger": 128, ...})
        """
        if not self.is_connected:
            raise Exception("Not connected to Xbox")

        command = {
            "type": "input",
            "input_type": input_type,
            **data
        }
        await self._send_command(command)

    async def send_gamepad_state(self, gamepad_data: Dict[str, Any]) -> bool:
        """
        发送完整手柄状态到Xbox（优化三）

        功能说明：
        - 发送完整的手柄状态数据
        - 包括所有按钮、扳机、摇杆
        - 参考streaming项目的xsrp.WriteControllerData

        参数：
        - gamepad_data: 手柄状态字典
            - buttons: 按钮位掩码
            - left_trigger: 左扳机 (0-255)
            - right_trigger: 右扳机 (0-255)
            - left_thumb_x: 左摇杆X (-32768 到 32767)
            - left_thumb_y: 左摇杆Y (-32768 到 32767)
            - right_thumb_x: 右摇杆X (-32768 到 32767)
            - right_thumb_y: 右摇杆Y (-32768 到 32767)

        返回：
        - True: 发送成功
        - False: 发送失败
        """
        if not self.is_connected:
            self.logger.error("Not connected to Xbox, cannot send gamepad state")
            return False

        protocol = self._smartglass_protocol
        input_ch = getattr(protocol, "input_channel_id", 0) if protocol else 0
        session = getattr(protocol, "_session", None) if protocol else None
        if protocol and input_ch > 0 and session is not None:
            self.logger.debug("SmartGlass 输入通道已移除，跳过 UDP gamepad 发送")
            return False

        try:
            command = {
                "type": "input",
                "input_type": "gamepad",
                "buttons": gamepad_data.get("buttons", 0),
                "left_trigger": gamepad_data.get("left_trigger", 0),
                "right_trigger": gamepad_data.get("right_trigger", 0),
                "left_thumb_x": gamepad_data.get("left_thumb_x", 0),
                "left_thumb_y": gamepad_data.get("left_thumb_y", 0),
                "right_thumb_x": gamepad_data.get("right_thumb_x", 0),
                "right_thumb_y": gamepad_data.get("right_thumb_y", 0)
            }

            await self._send_command(command)

            self.logger.debug(
                f"Gamepad state sent: buttons={command['buttons']:04x}, "
                f"LT={command['left_trigger']}, RT={command['right_trigger']}"
            )

            return True

        except Exception as e:
            self.logger.error(f"Failed to send gamepad state: {e}")
            return False

    async def send_gamepad_analog(self, gamepad_data: Dict[str, Any]) -> bool:
        """
        发送手柄模拟输入（优化三）

        功能说明：
        - 发送手柄模拟输入数据
        - 支持摇杆和扳机的连续值
        - 用于精确控制

        参数：
        - gamepad_data: 手柄模拟输入数据

        返回：
        - True: 发送成功
        - False: 发送失败
        """
        if not self.is_connected:
            return False

        try:
            analog_input = {
                "type": "input",
                "input_type": "gamepad_analog",
                "version": 2,
                "packet_num": getattr(self, '_packet_num', 0) + 1,
                **gamepad_data
            }

            self._packet_num = analog_input["packet_num"]

            await self._send_command(analog_input)
            return True

        except Exception as e:
            self.logger.error(f"Failed to send gamepad analog: {e}")
            return False

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
        """@deprecated 请使用 UDP SmartGlass Connect + SmartGlassProtocol。"""
        self.logger.warning("connect_with_token() 已废弃，SmartGlass 控制通道为 UDP 5050")
        return False

    async def _connect_with_token_tcp_legacy(
        self,
        xbox_ip: str,
        xbox_token: str,
        user_hash: str,
        port: int = None
    ) -> bool:
        if self.is_connected:
            if self._current_xbox == xbox_ip:
                return True
            await self.disconnect()

        port = port or self.SMARTGLASS_UDP_PORT
        self._state = StreamState.CONNECTING
        self._current_xbox = xbox_ip

        try:
            self.logger.info(f"Connecting to Xbox with token: {xbox_ip}:{port}")

            self.logger.debug(f"Opening TCP connection to {xbox_ip}:{port}...")
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(xbox_ip, port),
                timeout=10
            )
            self.logger.info(f"TCP connection established to {xbox_ip}:{port}")

            # 使用 token 进行握手
            self.logger.debug(f"Starting token handshake...")
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

    async def try_tcp_connect(self, xbox_ip: str, port: int, timeout: float = 5.0) -> bool:
        """@deprecated SmartGlass 控制不使用 TCP。"""
        self.logger.debug("try_tcp_connect 已禁用 (port=%s)", port)
        return False

    async def connect_tcp_with_fallback(
        self,
        xbox_ip: str,
        ports: List[int],
        timeout: float = 5.0,
    ) -> Tuple[bool, int]:
        """@deprecated SmartGlass 控制不使用 TCP 兜底端口。"""
        self.logger.debug("connect_tcp_with_fallback 已禁用 ports=%s", ports)
        return False, 0

    async def _try_tcp_connect_legacy(self, xbox_ip: str, port: int, timeout: float = 5.0) -> bool:
        """探测 TCP 端口是否可达（不做 JSON 握手）。"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(xbox_ip, port),
                timeout=timeout,
            )
            writer.close()
            try:
                await asyncio.wait_for(writer.wait_closed(), timeout=2)
            except Exception:
                pass
            reader.feed_eof()
            self.logger.info("TCP 端口可达: %s:%s", xbox_ip, port)
            return True
        except Exception as exc:
            self.logger.debug("TCP 端口不可达 %s:%s — %s", xbox_ip, port, exc)
            return False

    async def mark_lan_session_ready(
        self,
        xbox_ip: str,
        tcp_port: int,
        udp_port: int,
        session_id: str = "",
    ) -> bool:
        """
        UDP SmartGlass + Broadcast 协商完成后标记会话就绪。

        跳过错误的 JSON-over-TCP:5050 握手；媒体走协商 udpPort。
        """
        self._state = StreamState.STREAMING
        self._current_xbox = xbox_ip
        self._lan_tcp_port = tcp_port
        self._lan_udp_port = udp_port
        self._gamestream_session_id = session_id or None
        self._stream_config = StreamConfig(xbox_ip=xbox_ip, xbox_port=tcp_port)
        self.logger.info(
            "LAN SmartGlass 会话就绪 %s tcp=%s udp=%s session=%s",
            xbox_ip,
            tcp_port,
            udp_port,
            session_id or "-",
        )
        return True

    async def _token_handshake(self, xbox_token: str, user_hash: str) -> bool:
        """
        使用 Xbox Live Token 执行握手

        参数:
            xbox_token: Xbox Live Token
            user_hash: 用户哈希

        返回:
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

        参数:
            xbox_token: Xbox Live Token
            user_hash: 用户哈希

        返回:
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

        参数:
            streaming_account_id: 流媒体账号ID
            email: 微软账号邮箱

        返回:
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

    # ==================== 混合模式视频流接收（方案3） ====================

    async def start_video_receiver(
        self,
        mode: str = "rtp",
        port: int = 50500,
        srtp_keys: Optional[Dict[str, bytes]] = None,
        video_callback: Optional[Callable[[bytes], None]] = None,
        frame_callback: Optional[Callable[[Any], None]] = None,
        allow_fallback: bool = True,
    ) -> bool:
        """
        启动视频流接收器（方案3：混合模式）

        功能说明：
        - 支持两种视频流接收模式：RTP 和 win32gui
        - RTP模式：直接接收Xbox视频流，性能更好
        - win32gui模式：从Xbox Streaming窗口截图，兼容性更好
        - 优先尝试RTP，失败时自动降级到win32gui

        参数：
        - mode: 视频模式 ("rtp" | "win32gui" | "auto")
        - port: RTP接收端口
        - srtp_keys: SRTP密钥（可选）
        - video_callback: 视频帧回调（原始H.264数据）
        - frame_callback: 解码后帧回调
        - allow_fallback: RTP 失败时是否降级 win32gui（LAN 模式应设为 False）

        返回：
        - True: 启动成功
        - False: 启动失败
        """
        self._video_callback = video_callback
        self._frame_callback = frame_callback
        self._rtp_port = port

        if mode == "win32gui":
            self._video_mode = "win32gui"
            self.logger.info("视频流接收模式: win32gui")
            return True

        if mode == "auto" or mode == "rtp":
            if not RTP_AVAILABLE:
                self.logger.warning("RTP模块不可用，降级到win32gui模式")
                self._video_mode = "win32gui"
                return True

            rtp_success = await self._start_rtp_receiver(srtp_keys)
            if rtp_success:
                self._video_mode = "rtp"
                self.logger.info(f"视频流接收模式: RTP (端口 {port})")
                return True
            if allow_fallback:
                self.logger.warning("RTP模式启动失败，降级到win32gui模式")
                self._video_mode = "win32gui"
                return True
            self.logger.error("RTP模式启动失败（未启用降级）")
            return False

        return False

    async def _start_rtp_receiver(self, srtp_keys: Optional[Dict[str, bytes]] = None) -> bool:
        """
        启动RTP接收器

        参数：
        - srtp_keys: SRTP密钥

        返回：
        - True: 启动成功
        - False: 启动失败
        """
        try:
            self._rtp_session = RTPSession()
            self._packet_assembler = H264RTPPacketAssemble()
            self._h264_parser = H264Parser()
            self._frame_assembler = H264FrameAssembler()

            if srtp_keys and RTP_AVAILABLE:
                self._srtp_handler = SRTPHandler()
                self._srtp_handler.set_keys(
                    send_master_key=srtp_keys.get('send_key', b'\x00' * 16),
                    send_master_salt=srtp_keys.get('send_salt', b'\x00' * 14),
                    recv_master_key=srtp_keys.get('recv_key', b'\x00' * 16),
                    recv_master_salt=srtp_keys.get('recv_salt', b'\x00' * 14)
                )
                self._srtp_enabled = True

            bound = await self._rtp_session.bind('0.0.0.0', self._rtp_port)
            if not bound:
                self.logger.error("RTP端口绑定失败")
                return False

            self._rtp_receive_task = asyncio.create_task(self._rtp_receive_loop())
            self.logger.info(f"RTP接收器已启动，端口: {self._rtp_port}")
            return True

        except Exception as e:
            self.logger.error(f"RTP接收器启动失败: {e}")
            return False

    async def _rtp_receive_loop(self):
        """
        RTP接收循环

        功能：
        - 接收RTP数据包
        - 解密SRTP（如果启用）
        - 解析H.264
        - 组装帧
        """
        if not self._rtp_session:
            return

        try:
            async for packet in self._rtp_session.packets():
                try:
                    raw_payload = packet.payload
                    
                    if self._srtp_handler and self._srtp_enabled:
                        decrypted = self._srtp_handler.decrypt_rtp(
                            raw_payload,
                            packet.header.sequence_number,
                            packet.header.timestamp,
                            packet.header.ssrc,
                            is_incoming=True,
                        )
                        if decrypted is None:
                            continue
                        raw_payload = decrypted
                        packet = RTPPacket(
                            header=packet.header,
                            payload=raw_payload,
                            payload_offset=packet.payload_offset,
                            raw_data=packet.raw_data[: packet.payload_offset] + raw_payload,
                        )

                    nalu_list = self._packet_assembler.assemble(packet)
                    
                    for nalu_data in nalu_list:
                        self._h264_parser.feed(nalu_data, packet.header.timestamp, packet.header.marker)

                        if self._video_callback:
                            self._video_callback(nalu_data)

                    frame_data = self._frame_assembler.add_nalu(
                        NALU(
                            type=NALUType.NON_IDR,
                            data=nalu_list[-1] if nalu_list else b'',
                            timestamp=packet.header.timestamp,
                            marker=packet.header.marker,
                            size=len(nalu_list[-1]) if nalu_list else 0
                        )
                    )

                    if frame_data and self._frame_callback:
                        self._frame_callback(frame_data)

                except Exception as e:
                    self.logger.error(f"RTP包处理错误: {e}")

        except asyncio.CancelledError:
            self.logger.info("RTP接收循环已取消")
        except Exception as e:
            self.logger.error(f"RTP接收循环异常: {e}")

    async def stop_video_receiver(self):
        """
        停止视频流接收器
        """
        if self._rtp_receive_task:
            self._rtp_receive_task.cancel()
            try:
                await self._rtp_receive_task
            except asyncio.CancelledError:
                pass
            self._rtp_receive_task = None

        if self._rtp_session:
            self._rtp_session.close()
            self._rtp_session = None

        if self._srtp_handler:
            self._srtp_handler = None

        if self._h264_parser:
            self._h264_parser.reset()
            self._h264_parser = None

        if self._frame_assembler:
            self._frame_assembler.reset()
            self._frame_assembler = None

        self._video_mode = "win32gui"
        self.logger.info("视频流接收器已停止")

    def get_video_stats(self) -> Dict[str, Any]:
        """
        获取视频流统计信息

        返回：
        - 统计信息字典
        """
        stats = {
            'mode': self._video_mode,
            'rtp_enabled': self._video_mode == "rtp"
        }

        if self._rtp_session:
            stats['rtp'] = self._rtp_session.get_stats()

        if self._h264_parser:
            stats['h264'] = self._h264_parser.get_stats()

        if self._srtp_handler:
            stats['srtp'] = self._srtp_handler.get_stats()

        return stats

    @property
    def video_mode(self) -> str:
        """获取当前视频模式"""
        return self._video_mode

    @property
    def is_rtp_active(self) -> bool:
        """检查RTP是否激活"""
        return self._video_mode == "rtp" and self._rtp_session is not None


class NALUType(Enum):
    """H.264 NALU类型（简化版，避免导入）"""
    NON_IDR = 1
    IDR = 5
    SPS = 7
    PPS = 8


# 全局流媒体控制器实例
xbox_stream_controller = XboxStreamController()
