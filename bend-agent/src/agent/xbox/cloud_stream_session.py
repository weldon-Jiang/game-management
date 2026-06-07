"""
Xbox 云端串流会话
================

功能说明：
- 基于 aiortc 建立 WebRTC 媒体连接（对齐 streaming/xsplayer.py）
- 通过 input DataChannel 发送手柄信号（对齐 xsrp.WriteControllerData）
- 从 video track 接收解码帧供模板匹配使用

作者：技术团队
版本：1.0
"""

import asyncio
import struct
import threading
import time
from typing import Any, Callable, Dict, List, Optional

import numpy as np

from ..core.logger import get_logger

try:
    from aiortc import (
        RTCConfiguration,
        RTCIceServer,
        RTCPeerConnection,
        RTCSessionDescription,
    )
    from aiortc.mediastreams import MediaStreamTrack
    from av import VideoFrame

    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    RTCPeerConnection = None
    RTCSessionDescription = None
    MediaStreamTrack = None
    VideoFrame = None


class _DummyVideoTrack(MediaStreamTrack if AIORTC_AVAILABLE else object):
    """Placeholder outbound video track required for Xbox SDP offer."""

    kind = "video"

    async def recv(self):
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc is not available")
        pts, time_base = await self.next_timestamp()
        frame = VideoFrame(width=640, height=480)
        frame.pts = pts
        frame.time_base = time_base
        return frame


class GamepadInputEncoder:
    """Encode controller state for Xbox input DataChannel (protocol 1.0)."""

    TRIGGER_MAX = 32767

    @staticmethod
    def _scale_trigger(value: int) -> int:
        return int(max(0, min(GamepadInputEncoder.TRIGGER_MAX, value * 128)))

    @staticmethod
    def encode(gamepad_index: int, gamepad_data: Dict[str, Any]) -> bytes:
        buttons = int(gamepad_data.get("buttons", 0))
        left_trigger = GamepadInputEncoder._scale_trigger(int(gamepad_data.get("left_trigger", 0)))
        right_trigger = GamepadInputEncoder._scale_trigger(int(gamepad_data.get("right_trigger", 0)))
        left_thumb_x = int(gamepad_data.get("left_thumb_x", 0))
        left_thumb_y = int(gamepad_data.get("left_thumb_y", 0))
        right_thumb_x = int(gamepad_data.get("right_thumb_x", 0))
        right_thumb_y = int(gamepad_data.get("right_thumb_y", 0))

        return struct.pack(
            "<BHIHHhhhh",
            0,
            gamepad_index,
            buttons,
            left_trigger,
            right_trigger,
            left_thumb_x,
            left_thumb_y,
            right_thumb_x,
            right_thumb_y,
        )


class CloudStreamSession:
    """
    Xbox 云端 WebRTC 串流会话。

    对外接口与 XboxStreamController 子集兼容：
    - send_gamepad_state()
    - start_video_receiver()
    - disconnect()
    - video_mode / is_connected / is_rtp_active
    """

    def __init__(self, peer_connection: Any, gamepad_index: int = 0):
        self.logger = get_logger("cloud_stream_session")
        self._pc = peer_connection
        self._gamepad_index = gamepad_index
        self._input_channel = None
        self._video_mode = "webrtc"
        self._connected = False
        self.is_connected = False
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._frame_event = asyncio.Event()
        self._video_consumer_task: Optional[asyncio.Task] = None
        self._last_input_time = 0.0
        self._rtp_session = None
        self._input_channel_closed = False
        self._on_input_channel_close_callbacks: List[Callable[[], None]] = []
        self._input_handlers_bound = False

    @staticmethod
    async def create_peer_connection() -> Any:
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc is required for cloud streaming")

        ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        ]
        pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))
        get_logger("cloud_stream_session").info(
            "WebRTC ICE configuration: stun_servers=%s, dataChannels=chat/control/input/message",
            len(ice_servers),
        )

        pc.createDataChannel("chat", ordered=False, protocol="chatV1")
        pc.createDataChannel("control", ordered=False, protocol="controlV1")
        input_channel = pc.createDataChannel("input", ordered=True, protocol="1.0")
        pc.createDataChannel("message", ordered=False, protocol="messageV1")

        # Xbox cloud client receives A/V from console; do not publish a send track.
        pc.addTransceiver("audio", direction="recvonly")
        pc.addTransceiver("video", direction="recvonly")
        return pc, input_channel

    @classmethod
    async def from_sdp_exchange(
        cls,
        offer_sdp: str,
        answer_sdp: str,
        gamepad_index: int = 0,
        connection_timeout: float = 30.0,
    ) -> Optional["CloudStreamSession"]:
        if not AIORTC_AVAILABLE:
            return None

        logger = get_logger("cloud_stream_session")
        try:
            pc, input_channel = await cls.create_peer_connection()

            await pc.setLocalDescription(RTCSessionDescription(sdp=offer_sdp, type="offer"))
            await pc.setRemoteDescription(RTCSessionDescription(sdp=answer_sdp, type="answer"))

            session = cls(pc, gamepad_index=gamepad_index)
            session._input_channel = input_channel
            session.bind_input_channel_handlers()

            @pc.on("track")
            async def on_track(track):
                session.attach_incoming_video_track(track)

            session.attach_existing_tracks()

            @pc.on("connectionstatechange")
            async def on_connectionstatechange():
                state = pc.connectionState
                logger.info(f"WebRTC connection state: {state}")
                if state == "connected":
                    session._connected = True
                    session.is_connected = True
                elif state in ("failed", "closed", "disconnected"):
                    session._connected = False
                    session.is_connected = False

            deadline = time.time() + connection_timeout
            while time.time() < deadline:
                if pc.connectionState == "connected":
                    session._connected = True
                    session.is_connected = True
                    break
                if pc.connectionState == "failed":
                    logger.error("WebRTC connection failed")
                    await session.disconnect()
                    return None
                await asyncio.sleep(0.2)

            if not session.is_connected:
                logger.warning(
                    f"WebRTC not fully connected (state={pc.connectionState}), continuing with partial session"
                )
                session.is_connected = pc.connectionState not in ("failed", "closed")

            return session

        except Exception as exc:
            logger.error(f"Failed to create cloud stream session: {exc}")
            return None

    async def _consume_video_track(self, track) -> None:
        while True:
            try:
                frame = await track.recv()
                image = frame.to_ndarray(format="bgr24")
                with self._frame_lock:
                    self._latest_frame = image
                self._frame_event.set()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self.logger.debug(f"Video track consume ended: {exc}")
                break

    def attach_incoming_video_track(self, track) -> None:
        """Start consuming an inbound WebRTC video track."""
        if track is None or getattr(track, "kind", None) != "video":
            return
        if self._video_consumer_task and not self._video_consumer_task.done():
            return
        self.logger.info("WebRTC video track received")
        self._video_consumer_task = asyncio.create_task(self._consume_video_track(track))

    def attach_existing_tracks(self) -> None:
        """Attach already-negotiated inbound tracks (on_track may have fired earlier)."""
        if not self._pc:
            return
        get_transceivers = getattr(self._pc, "getTransceivers", None)
        if not callable(get_transceivers):
            return
        for transceiver in get_transceivers():
            receiver = getattr(transceiver, "receiver", None)
            track = getattr(receiver, "track", None) if receiver else None
            if track and track.kind == "video":
                self.attach_incoming_video_track(track)

    async def start_video_receiver(
        self,
        mode: str = "auto",
        port: int = 50500,
        srtp_keys: Optional[Dict[str, bytes]] = None,
        video_callback: Optional[Callable[[bytes], None]] = None,
        frame_callback: Optional[Callable[[np.ndarray], None]] = None,
    ) -> bool:
        self._video_mode = "webrtc"
        self.logger.info("Cloud stream video receiver active (WebRTC track)")
        return True

    @property
    def input_channel_state(self) -> Optional[str]:
        if self._input_channel is None:
            return None
        return getattr(self._input_channel, "readyState", None)

    def is_input_channel_healthy(self) -> bool:
        return self.input_channel_state == "open" and not self._input_channel_closed

    def on_input_channel_close(self, callback: Callable[[], None]) -> None:
        """Register callback invoked when input DataChannel closes."""
        self._on_input_channel_close_callbacks.append(callback)

    def bind_input_channel_handlers(self) -> None:
        """Attach open/close listeners to the negotiated input DataChannel."""
        if self._input_handlers_bound or self._input_channel is None:
            return

        channel = self._input_channel
        self._input_handlers_bound = True
        self._input_channel_closed = False

        @channel.on("open")
        def on_input_open():
            self._input_channel_closed = False
            self.logger.info("input DataChannel opened (state=open)")

        @channel.on("close")
        def on_input_close():
            self._input_channel_closed = True
            state = getattr(channel, "readyState", "closed")
            self.logger.warning("input DataChannel FAILED: closed (state=%s)", state)
            for callback in list(self._on_input_channel_close_callbacks):
                try:
                    callback()
                except Exception as exc:
                    self.logger.debug(f"input channel close callback error: {exc}")

    async def wait_for_input_channel(self, timeout: float = 10.0) -> bool:
        if self._input_channel is None:
            return False
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._input_channel.readyState == "open":
                return True
            await asyncio.sleep(0.1)
        self.logger.warning(
            f"input DataChannel FAILED: not open after {timeout}s "
            f"(state={self._input_channel.readyState})"
        )
        return False

    async def send_gamepad_state(self, gamepad_data: Dict[str, Any]) -> bool:
        if not self.is_input_channel_healthy():
            self.logger.warning(
                f"input DataChannel not open, cannot send gamepad state "
                f"(state={getattr(self._input_channel, 'readyState', None)})"
            )
            return False

        try:
            payload = GamepadInputEncoder.encode(self._gamepad_index, gamepad_data)
            self._input_channel.send(payload)
            self._last_input_time = time.time()
            return True
        except Exception as exc:
            self.logger.error(f"Failed to send gamepad state via DataChannel: {exc}")
            return False

    async def send_keepalive(self) -> bool:
        signal = {
            "buttons": 0x1000,
            "left_trigger": 0,
            "right_trigger": 0,
            "left_thumb_x": 0,
            "left_thumb_y": 0,
            "right_thumb_x": 0,
            "right_thumb_y": 0,
        }
        ok = await self.send_gamepad_state(signal)
        await asyncio.sleep(0.05)
        return await self.send_gamepad_state(
            {**signal, "buttons": 0}
        ) if ok else False

    async def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return self._latest_frame.copy()
            try:
                await asyncio.wait_for(self._frame_event.wait(), timeout=0.05)
                self._frame_event.clear()
            except asyncio.TimeoutError:
                await asyncio.sleep(0.01)
        return None

    @property
    def video_mode(self) -> str:
        return self._video_mode

    @property
    def is_rtp_active(self) -> bool:
        return self._video_mode == "webrtc" and self._latest_frame is not None

    def get_video_stats(self) -> Dict[str, Any]:
        return {
            "mode": self._video_mode,
            "connected": self.is_connected,
            "has_frame": self._latest_frame is not None,
        }

    async def disconnect(self) -> None:
        if self._video_consumer_task:
            self._video_consumer_task.cancel()
            try:
                await self._video_consumer_task
            except asyncio.CancelledError:
                pass
            self._video_consumer_task = None

        if self._pc:
            try:
                await self._pc.close()
            except Exception as exc:
                self.logger.debug(f"Peer connection close: {exc}")

        self._connected = False
        self.is_connected = False
        self.logger.info("Cloud stream session disconnected")
