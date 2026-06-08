"""
WebRTC 串流输入通道保活
======================

在长耗时场景等待/小键盘输入期间周期性发送 keepalive，避免 DataChannel 空闲关闭。
"""

import asyncio
import time
from typing import Any, Callable, Optional, Union

from ..core.logger import get_logger

SessionSource = Union[Any, Callable[[], Any]]

logger = get_logger("stream_keepalive")

KEEPALIVE_INTERVAL_SEC = 8.0


def get_input_channel_state(session: Any) -> Optional[str]:
    channel = getattr(session, "_input_channel", None)
    if channel is None:
        return None
    return getattr(channel, "readyState", None)


def is_input_channel_open(session: Any) -> bool:
    if session is None:
        return False
    if hasattr(session, "is_input_channel_healthy"):
        return session.is_input_channel_healthy()
    return get_input_channel_state(session) == "open"


async def send_keepalive(session: Any) -> bool:
    if session is None:
        return False
    if hasattr(session, "send_keepalive"):
        return await session.send_keepalive()
    if hasattr(session, "send_gamepad_state"):
        neutral = {
            "buttons": 0,
            "left_trigger": 0,
            "right_trigger": 0,
            "left_thumb_x": 0,
            "left_thumb_y": 0,
            "right_thumb_x": 0,
            "right_thumb_y": 0,
        }
        return await session.send_gamepad_state(neutral)
    return False


async def ensure_input_channel(session: Any, timeout: float = 5.0) -> bool:
    """等待 input DataChannel 进入 open；无 wait_for_input_channel 时轮询 readyState。"""
    if session is None:
        return True
    if hasattr(session, "wait_for_input_channel"):
        return await session.wait_for_input_channel(timeout=timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_input_channel_open(session):
            return True
        await asyncio.sleep(0.1)
    return is_input_channel_open(session)


def _resolve_session(source: SessionSource) -> Any:
    if callable(source):
        return source()
    return source


class StreamKeepaliveLoop:
    """长耗时操作（场景等待/账号切换）期间的后台 keepalive；async with 自动启停。"""

    def __init__(self, session: SessionSource, interval: float = KEEPALIVE_INTERVAL_SEC):
        self._session_source = session
        self._interval = interval
        self._task: Optional[asyncio.Task] = None

    def _current_session(self) -> Any:
        return _resolve_session(self._session_source)

    async def __aenter__(self):
        """进入上下文时启动周期性 keepalive 任务。"""
        if self._current_session() is not None:
            self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _run(self):
        """每 interval 秒发送一次 keepalive；通道非 open 时仅告警不发送。"""
        while True:
            await asyncio.sleep(self._interval)
            session = self._current_session()
            if session is None:
                continue
            if not is_input_channel_open(session):
                logger.warning(
                    "keepalive 检测到 input DataChannel 非 open 状态: %s",
                    get_input_channel_state(session),
                )
                continue
            await send_keepalive(session)
