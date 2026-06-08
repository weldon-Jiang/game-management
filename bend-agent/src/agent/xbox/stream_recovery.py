"""
WebRTC 输入通道恢复
==================

在 input DataChannel 关闭后，复用既有 PlaySession 重新执行 SDP 握手，
重建 CloudStreamSession 并回绑步骤三/四依赖的会话引用。
"""

import asyncio
import time
from typing import Any, Callable, Optional

from ..core.logger import get_logger

logger = get_logger("stream_recovery")

_RECONNECT_WINDOW_SEC = 60.0
_RECONNECT_MAX_IN_WINDOW = 2


def _get_reconnect_lock(context: Any) -> asyncio.Lock:
    lock = getattr(context, "_stream_reconnect_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        context._stream_reconnect_lock = lock
    return lock


async def reconnect_input_channel(context: Any, task_logger=None) -> bool:
    """
    重连 WebRTC 输入通道（保留 PlaySession，重新 SDP 交换）。

    返回：
    - bool: 是否成功重建 input DataChannel
    """
    log = task_logger or logger
    lock = _get_reconnect_lock(context)

    if lock.locked():
        log.info("输入通道重连已在进行中，等待完成...")
    # 同 task 串行重连，避免并发 SDP 交换；60s 内最多 2 次
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

            from ..automation.step2_xbox_streaming import reconnect_cloud_stream_session

            log.info("开始重连 WebRTC 输入通道（复用 PlaySession + SDP）")
            ok = await reconnect_cloud_stream_session(context, log, None)
            if not ok:
                log.error("WebRTC 输入通道重连失败")
                return False

            rebind_stream_bindings(context)
            log.info("WebRTC 输入通道重连成功，会话引用已回绑")
            return True
        except Exception as exc:
            log.error(f"WebRTC 输入通道重连异常: {exc}")
            return False


def rebind_stream_bindings(
    context: Any,
    executor: Any = None,
    switcher: Any = None,
    engine: Any = None,
) -> None:
    """重连成功后将会话引用同步到截帧、手柄、切换器与 Step4 引擎（避免仍指向旧 session）。"""
    session = getattr(context, "xbox_session", None)
    if session is None:
        return

    webrtc_controller = getattr(context, "_webrtc_frame_controller", None)
    if webrtc_controller is not None and hasattr(webrtc_controller, "update_session"):
        webrtc_controller.update_session(session)

    frame_capture = getattr(context, "frame_capture", None)
    if frame_capture is not None and hasattr(frame_capture, "set_webrtc_controller"):
        frame_capture.set_webrtc_controller(webrtc_controller)

    protocol = getattr(context, "_controller_protocol", None)
    if protocol is not None and hasattr(protocol, "set_stream_controller"):
        protocol.set_stream_controller(session)

    if executor is not None and hasattr(executor, "set_xbox_session"):
        executor.set_xbox_session(session)
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
