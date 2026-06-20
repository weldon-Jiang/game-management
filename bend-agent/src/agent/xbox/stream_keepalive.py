"""
SmartGlass / GSSV 串流输入通道保活
==================================

在长耗时场景等待/小键盘输入期间周期性发送 keepalive，避免输入通道空闲关闭。
GSSV 云端 input 通道约 30–40s 无有效输入会被服务端关闭，需高于该频率保活。
"""

import asyncio
import time
from typing import Any, Callable, Dict, Optional, Union

from ..core.logger import get_logger

SessionSource = Union[Any, Callable[[], Any]]

logger = get_logger("stream_keepalive")

KEEPALIVE_INTERVAL_SEC = 8.0
_WARN_COOLDOWN_SEC = 60.0


def _gssv_keepalive_interval_sec() -> float:
    """GSSV input ~35s idle 断开，长操作期间须高频 DPadUp 脉冲。"""
    from ..core.config import config

    return float(config.get("gssv.gssv_keepalive_interval_sec", 3.0))

# session id → {refs, task}；嵌套 StreamKeepaliveLoop 共享单后台任务
_keepalive_registry: Dict[int, Dict[str, Any]] = {}


def _resolve_webrtc(session: Any) -> Any:
    """CloudStreamController → GssvWebRtcSession；否则返回 session 自身。"""
    if session is None:
        return None
    webrtc = getattr(session, "_webrtc", None)
    if webrtc is not None:
        return webrtc
    if hasattr(session, "try_restore_input"):
        return session
    return None


def get_input_channel_state(session: Any) -> Optional[str]:
    """读取 input DataChannel readyState；GSSV 封装层返回 open/closed。"""
    if session is None:
        return None
    if hasattr(session, "input_channel_state"):
        return session.input_channel_state
    webrtc = _resolve_webrtc(session)
    if webrtc is not None and hasattr(webrtc, "get_input_channel_ready_state"):
        state = webrtc.get_input_channel_ready_state()
        if state is not None:
            return state
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


async def try_restore_input_channel(session: Any) -> bool:
    """GSSV 轻量恢复：重发 handshake；SmartGlass 路径无操作。"""
    webrtc = _resolve_webrtc(session)
    if webrtc is not None and hasattr(webrtc, "try_restore_input"):
        return await webrtc.try_restore_input()
    return is_input_channel_open(session)


async def send_keepalive(session: Any, *, context: Optional[Any] = None) -> bool:
    """经 controller_write 统一出口；GSSV 发 DPadUp 脉冲。"""
    from .controller_write import send_stream_keepalive

    if session is None:
        return False
    if not is_input_channel_open(session):
        await try_restore_input_channel(session)
    return await send_stream_keepalive(session, context=context)


async def ensure_input_channel(session: Any, timeout: float = 5.0) -> bool:
    """等待 input DataChannel 进入 open；无 wait_for_input_channel 时轮询 readyState。"""
    if session is None:
        return True
    if hasattr(session, "wait_for_input_channel"):
        return await session.wait_for_input_channel(timeout=timeout)
    deadline = time.time() + timeout
    while time.time() < deadline:
        if await try_restore_input_channel(session):
            return True
        if is_input_channel_open(session):
            return True
        await asyncio.sleep(0.1)
    return is_input_channel_open(session)


def _resolve_session(source: SessionSource) -> Any:
    if callable(source):
        return source()
    return source


def _effective_interval(session: Any, interval: float) -> float:
    if _resolve_webrtc(session) is not None:
        return min(interval, _gssv_keepalive_interval_sec())
    return interval


class StreamKeepaliveLoop:
    """长耗时操作（场景等待/账号切换）期间的后台 keepalive；async with 自动启停。"""

    def __init__(
        self,
        session: SessionSource,
        interval: float = KEEPALIVE_INTERVAL_SEC,
        *,
        context: Optional[Any] = None,
    ):
        self._session_source = session
        self._interval = interval
        self._context = context
        self._registry_key: Optional[int] = None
        self._last_warn_at = 0.0

    def _current_session(self) -> Any:
        return _resolve_session(self._session_source)

    async def __aenter__(self):
        """进入上下文时启动/复用周期性 keepalive（同 session 嵌套引用计数）。"""
        session = self._current_session()
        if session is None:
            return self
        key = id(session)
        self._registry_key = key
        entry = _keepalive_registry.get(key)
        if entry is None:
            entry = {"refs": 0, "task": None, "loop": self}
            _keepalive_registry[key] = entry
        entry["refs"] += 1
        if entry["refs"] == 1:
            entry["task"] = asyncio.create_task(self._run(key))
        return self

    async def __aexit__(self, exc_type, exc, tb):
        key = self._registry_key
        if key is None:
            return
        entry = _keepalive_registry.get(key)
        if entry is None:
            return
        entry["refs"] -= 1
        if entry["refs"] <= 0:
            task = entry.get("task")
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            _keepalive_registry.pop(key, None)
        self._registry_key = None

    async def _tick(self, session: Any) -> None:
        sent = await send_keepalive(session, context=self._context)
        if sent:
            return
        state = get_input_channel_state(session)
        now = time.time()
        msg = "keepalive 检测到 input DataChannel 非 open 状态: %s"
        if now - self._last_warn_at >= _WARN_COOLDOWN_SEC:
            logger.warning(msg, state)
            self._last_warn_at = now
        else:
            logger.debug(msg, state)

    async def _run(self, key: int):
        """启动后立即发一次保活，再周期性发送（对齐 streaming 不等首个 sleep）。"""
        session = self._current_session()
        if session is not None:
            await self._tick(session)
        while True:
            session = self._current_session()
            interval = _effective_interval(session, self._interval)
            await asyncio.sleep(interval)
            session = self._current_session()
            if session is None:
                entry = _keepalive_registry.get(key)
                if entry is None or entry.get("refs", 0) <= 0:
                    break
                continue
            await self._tick(session)
