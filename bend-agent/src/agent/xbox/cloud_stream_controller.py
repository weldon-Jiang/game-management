"""GSSV 云端串流控制器 — 与 XboxStreamController 对齐的 Step3/Step4 接口。"""

from __future__ import annotations

from typing import Any, Dict, Optional

from ..gssv.cloud_webrtc import GssvWebRtcSession
from ..core.logger import get_logger
from .stream_state import StreamState


class CloudStreamController:
    """
    云端 WebRTC 串流会话包装。

    Step3/Step4 通过 context.xbox_session 调用 send_gamepad_state / start_video_receiver 等。
    """

    def __init__(self, webrtc: GssvWebRtcSession, *, server_name: str = "", server_id: str = ""):
        self.logger = get_logger("cloud_stream_controller")
        self._webrtc = webrtc
        self._state = StreamState.STREAMING
        self._current_xbox = server_name or server_id
        self._server_id = server_id
        self._video_mode = "cloud"
        self.is_busy = False
        self.current_task_id: Optional[str] = None
        self.current_streaming_account_id: Optional[str] = None

    @property
    def is_connected(self) -> bool:
        return self._webrtc.is_ready

    @property
    def input_channel_state(self) -> str:
        state = self._webrtc.get_input_channel_ready_state()
        if state:
            return state
        return "open" if self._webrtc.is_input_ready else "closed"

    @property
    def video_mode(self) -> str:
        return self._video_mode

    def is_input_channel_healthy(self) -> bool:
        return self._webrtc.is_input_ready and self._webrtc.is_input_channel_open()

    async def wait_for_input_channel(self, timeout: float = 5.0) -> bool:
        return await self._webrtc.wait_for_input_channel(timeout=timeout)

    async def send_keepalive(self) -> bool:
        return await self._webrtc.send_keepalive()

    async def send_gamepad_state(self, gamepad_data: Dict[str, Any]) -> bool:
        return await self._webrtc.send_gamepad(gamepad_data)

    async def send_gamepad_analog(self, gamepad_data: Dict[str, Any]) -> bool:
        return await self.send_gamepad_state(gamepad_data)

    async def send_input(self, input_type: str, data: Dict[str, Any]) -> None:
        if input_type == "gamepad":
            await self.send_gamepad_state(data)

    async def press_button(self, button: str, duration: float = 0.1) -> None:
        """Step4 兼容：简单按钮映射到 bitmask（仅常用键）。"""
        mapping = {
            "a": 0x1000,
            "b": 0x2000,
            "x": 0x4000,
            "y": 0x8000,
            "menu": 0x0010,
            "view": 0x0020,
            "nexus": 0x0400,
        }
        mask = mapping.get((button or "").lower(), 0)
        if not mask:
            return
        await self.send_gamepad_state({"buttons": mask})
        if duration > 0:
            import asyncio

            await asyncio.sleep(duration)
        await self.send_gamepad_state({"buttons": 0})

    async def start_video_receiver(
        self,
        mode: str = "cloud",
        port: int = 0,
        srtp_keys: Optional[Dict[str, bytes]] = None,
        video_callback=None,
        frame_callback=None,
        allow_fallback: bool = False,
    ) -> bool:
        """云端模式视频已在 WebRTC track 消费循环中，此处仅标记就绪。"""
        self._video_mode = "cloud"
        return self._webrtc.is_ready

    async def stop_video_receiver(self) -> None:
        return

    async def disconnect(self) -> None:
        await self._webrtc.close()
        self._state = StreamState.IDLE

    @property
    def webrtc_session(self) -> GssvWebRtcSession:
        return self._webrtc
