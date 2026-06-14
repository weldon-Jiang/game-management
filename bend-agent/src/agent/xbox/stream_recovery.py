"""
GSSV 云端串流输入通道恢复 — WebRTC 异常时重新 play/握手。
"""

import asyncio
import time
from typing import Any, Callable, Optional

from ..core.config import config
from ..core.logger import get_logger

logger = get_logger("stream_recovery")

_RECONNECT_WINDOW_SEC = 60.0
_RECONNECT_MAX_IN_WINDOW = 2
_DEFAULT_RECONNECT_TIMEOUT_SEC = 45.0


def _get_reconnect_lock(context: Any) -> asyncio.Lock:
    lock = getattr(context, "_stream_reconnect_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        context._stream_reconnect_lock = lock
    return lock


async def reconnect_input_channel(context: Any, task_logger=None) -> bool:
    """重连 GSSV 云端串流（重新 play/WebRTC 握手）。"""
    log = task_logger or logger
    lock = _get_reconnect_lock(context)

    if lock.locked():
        log.info("输入通道重连已在进行中，等待完成...")

    async with lock:
        try:
            now = time.time()
            attempts = getattr(context, "_reconnect_attempt_times", None)
            if attempts is None:
                attempts = []
                context._reconnect_attempt_times = attempts
            attempts[:] = [t for t in attempts if now - t < _RECONNECT_WINDOW_SEC]
            if len(attempts) >= _RECONNECT_MAX_IN_WINDOW:
                log.error(
                    "60s 内重连次数已达上限 (%d)，跳过重连",
                    _RECONNECT_MAX_IN_WINDOW,
                )
                return False
            attempts.append(now)

            from ..xbox.stream_keepalive import is_input_channel_open

            session = getattr(context, "xbox_session", None)
            if session is not None and is_input_channel_open(session):
                log.info("input 通道已恢复 open，跳过重连")
                return True

            from ..core.account_logger import get_stream_logger
            from .streaming_credentials import attach_streaming_credentials
            from .xsrp_cloud_connect import cleanup_xsrp_cloud_attempt, connect_xsrp_cloud

            email = getattr(context, "streaming_account_email", "") or ""
            stream_logger = get_stream_logger(email) if email else log
            reconnect_timeout = float(
                config.get("gssv.cloud_reconnect_timeout_sec", _DEFAULT_RECONNECT_TIMEOUT_SEC)
            )

            log.info("开始重连 GSSV 云端串流")
            await cleanup_xsrp_cloud_attempt(context, log)
            creds = attach_streaming_credentials(context)
            ok, details = await asyncio.wait_for(
                connect_xsrp_cloud(context, creds, log, stream_logger),
                timeout=reconnect_timeout,
            )
            if not ok:
                log.error("云端串流重连失败: %s", details.get("errorMessage", details))
                return False

            rebind_stream_bindings(
                context,
                executor=getattr(context, "_input_recovery_executor", None),
                switcher=getattr(context, "_input_recovery_switcher", None),
                engine=getattr(context, "_input_recovery_engine", None),
            )
            from .xsrp_access_input_loop import restart_xsrp_access_input_loop
            from .xsrp_stream_keepalive import stop_xsrp_idle_keepalive

            await stop_xsrp_idle_keepalive(context)
            await restart_xsrp_access_input_loop(context, log)
            log.info("云端串流重连成功，会话引用已回绑")
            return True
        except asyncio.TimeoutError:
            log.error("云端串流重连超时 (%ss)", reconnect_timeout)
            return False
        except Exception as exc:
            log.error("云端串流重连异常: %s", exc)
            return False


def rebind_stream_bindings(
    context: Any,
    executor: Any = None,
    switcher: Any = None,
    engine: Any = None,
) -> None:
    """重连成功后将会话引用同步到截帧、手柄、切换器与 Step4 引擎。"""
    session = getattr(context, "xbox_session", None)
    if session is None:
        return

    webrtc = getattr(session, "_webrtc", None) or getattr(session, "webrtc_session", None)
    if webrtc is not None:
        context._cloud_webrtc = webrtc

    direct_capture = getattr(context, "_direct_capture", None)
    frame_capture = getattr(context, "frame_capture", None)
    if frame_capture is not None and direct_capture is not None:
        if hasattr(frame_capture, "set_direct_capture"):
            frame_capture.set_direct_capture(direct_capture)
        elif hasattr(frame_capture, "_source"):
            frame_capture._source = direct_capture

    protocol = getattr(context, "_controller_protocol", None)
    if protocol is not None and hasattr(protocol, "set_stream_controller"):
        protocol.set_stream_controller(session)
    if protocol is not None and hasattr(protocol, "set_task_context"):
        protocol.set_task_context(context)

    if executor is not None and hasattr(executor, "set_xbox_session"):
        executor.set_xbox_session(session)
    if executor is not None and hasattr(executor, "set_task_context"):
        executor.set_task_context(context)
    if switcher is not None and hasattr(switcher, "set_stream_session"):
        switcher.set_stream_session(session)
    if engine is not None and hasattr(engine, "_action_executor"):
        action_executor = engine._action_executor
        if action_executor is not None and hasattr(action_executor, "set_xbox_session"):
            action_executor.set_xbox_session(session)


def make_reconnect_callback(context: Any, task_logger=None) -> Callable[[], Any]:
    """构建供 AccountSwitcher 调用的异步重连回调。"""

    async def _callback() -> bool:
        return await reconnect_input_channel(context, task_logger)

    return _callback


def install_task_input_recovery(
    context: Any,
    task_logger=None,
    *,
    executor: Any = None,
    switcher: Any = None,
    engine: Any = None,
) -> None:
    """
    Step3 起注册 input 重连回调（Step4 可传入 switcher/engine 扩展 rebind）。

    此前仅在 Step4 注册，导致 READY 等待期 channel closed 时 schedule_input_reconnect 无效果。
    """
    if executor is not None:
        context._input_recovery_executor = executor
    if switcher is not None:
        context._input_recovery_switcher = switcher
    if engine is not None:
        context._input_recovery_engine = engine

    if getattr(context, "_input_recovery_installed", False):
        return

    log = task_logger or logger

    async def _reconnect() -> bool:
        return await reconnect_input_channel(context, log)

    context._input_reconnect_base = _reconnect
    context._input_reconnect_callback = _reconnect
    context._input_recovery_installed = True
    log.info("GSSV input 重连回调已注册（Step3）")
