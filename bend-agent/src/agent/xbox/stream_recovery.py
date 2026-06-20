"""
GSSV 云端串流输入通道恢复 — WebRTC 异常时重新 play/握手。
"""

import asyncio
import time
from typing import Any, Callable, Optional

from ..core.config import config
from ..core.logger import get_logger
from ..task.task_timeline_events import (
    MSG_INPUT_CHANNEL_CLOSED,
    MSG_INPUT_RECONNECTING,
    MSG_INPUT_RESTORED,
    emit_input_reconnect_failed,
    schedule_task_timeline_event,
)

logger = get_logger("stream_recovery")

_RECONNECT_WINDOW_SEC = 60.0
_RECONNECT_MAX_IN_WINDOW = 4
_DEFAULT_RECONNECT_TIMEOUT_SEC = 45.0
_POST_RECONNECT_VIDEO_WAIT_SEC = 20.0


def invalidate_stream_video(context: Any, *, clear_sdl: bool = True) -> None:
    """
    Xbox 待机/断流后丢弃缓存帧，避免 SDL 继续展示断线前的静态画面。

    视频轨恢复前窗口会黑屏，直至 capture 泵收到新帧。
    """
    context._stream_video_stale = True
    context._stream_video_stale_at = time.time()
    runtime = getattr(context, "_stream_runtime", None)
    if runtime is not None and hasattr(runtime, "invalidate_latest_frame"):
        runtime.invalidate_latest_frame()
    elif runtime is not None:
        runtime._latest_frame = None
    if clear_sdl:
        sdl = getattr(context, "sdl_window", None)
        if sdl is not None and hasattr(sdl, "clear"):
            try:
                sdl.clear()
            except Exception:
                pass


async def _await_fresh_video_after_reconnect(
    context: Any,
    task_logger,
    *,
    timeout: float = _POST_RECONNECT_VIDEO_WAIT_SEC,
) -> bool:
    """重连 WebRTC 后等待新视频帧写入 StreamRuntime（非断线前的旧帧）。"""
    from ..runtime.stream_runtime import capture_task_frame, get_or_create_stream_runtime

    log = task_logger or logger
    runtime = get_or_create_stream_runtime(context)
    runtime.invalidate_latest_frame()
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        frame = await capture_task_frame(context, timeout=min(2.0, deadline - time.monotonic()))
        from ..vision.frame_utils import frame_to_bgr_ndarray

        img = frame_to_bgr_ndarray(frame) if frame is not None else None
        if img is not None and img.size > 0:
            if frame is not None and getattr(frame, "data", None) is not img:
                from ..vision.frame_capture import Frame

                frame = Frame(
                    data=img,
                    frame_id=frame.frame_id,
                    timestamp=frame.timestamp,
                    width=img.shape[1],
                    height=img.shape[0],
                    fps=getattr(frame, "fps", 0.0),
                )
            runtime.seed_latest_frame(frame)
            context._stream_video_stale = False
            log.info(
                "重连后视频帧已恢复 (%sx%s)",
                getattr(frame, "width", "?"),
                getattr(frame, "height", "?"),
            )
            logger.info(
                "重连后视频帧已恢复 (%sx%s)",
                getattr(frame, "width", "?"),
                getattr(frame, "height", "?"),
            )
            return True
        await asyncio.sleep(0.25)
    log.warning("重连后会话已建立，但 %ss 内未收到新视频帧", int(timeout))
    logger.warning("重连后 %ss 内未收到新视频帧", int(timeout))
    return False


async def _wake_xbox_after_reconnect(context: Any, task_logger) -> None:
    """待机/屏保态 Xbox 需 Guide 或 A 唤醒；重连成功后发 Nexus 脉冲。"""
    from .controller_write import XSRP_NEXUS, send_button_pulse

    session = getattr(context, "xbox_session", None)
    if session is None:
        return
    log = task_logger or logger
    ok = await send_button_pulse(session, XSRP_NEXUS, context=context)
    if ok:
        log.info("重连后已发送 Nexus 唤醒脉冲")
    else:
        log.warning("重连后 Nexus 唤醒脉冲失败（input 可能未就绪）")


async def _verify_input_after_reconnect(context: Any, task_logger) -> bool:
    from .stream_keepalive import is_input_channel_open

    session = getattr(context, "xbox_session", None)
    if session is None:
        return False
    webrtc = getattr(session, "_webrtc", None) or getattr(context, "_cloud_webrtc", None)
    open_ok = is_input_channel_open(session)
    ready = webrtc is not None and getattr(webrtc, "is_input_ready", False)
    log = task_logger or logger
    if open_ok and ready:
        log.info("重连后 input DataChannel 就绪 (open + input_ready)")
        return True
    log.warning(
        "重连后 input 未完全就绪 (open=%s input_ready=%s)；"
        "人工操作需先 F8，或再次点击平台「重连串流」",
        open_ok,
        ready,
    )
    return False


def _get_reconnect_lock(context: Any) -> asyncio.Lock:
    lock = getattr(context, "_stream_reconnect_lock", None)
    if lock is None:
        lock = asyncio.Lock()
        context._stream_reconnect_lock = lock
    return lock


def bind_input_close_handler(context: Any, task_logger=None) -> None:
    """
    WebRTC input 通道关闭时标记 NOT_READY（对齐 streaming/libxsrp）。

    libxsrp 在 channel closed 时仅清除 IsReady，WriteControllerData 返回
    ERRXS_RTC_CHANNELS_NOT_READY，不自动 teardown 全量会话。
    全量重连仅由平台 reconnect_stream 或用户 F8 显式 force 触发。
    """
    log = task_logger or logger
    webrtc = getattr(context, "_cloud_webrtc", None)
    if webrtc is None or not hasattr(webrtc, "on_input_channel_close"):
        return
    if getattr(webrtc, "_bend_input_close_handler_bound", False):
        return

    def _on_close() -> None:
        context._input_channel_dirty = True
        invalidate_stream_video(context, clear_sdl=True)
        log.warning("xsrp input 通道 closed，已标记 NOT_READY 并丢弃缓存视频帧")
        logger.warning("WebRTC input DataChannel closed（handler）")
        schedule_task_timeline_event(
            context,
            MSG_INPUT_CHANNEL_CLOSED,
            event_key="input_channel_closed",
            throttle_sec=15.0,
        )
        from .controller_write import schedule_input_reconnect

        schedule_input_reconnect(context, force=False)

    webrtc.on_input_channel_close(_on_close)
    webrtc._bend_input_close_handler_bound = True


def bind_video_track_close_handler(context: Any, task_logger=None) -> None:
    """video track 结束（Xbox 待机/断流）时清帧并调度重连。"""
    log = task_logger or logger
    webrtc = getattr(context, "_cloud_webrtc", None)
    if webrtc is None or not hasattr(webrtc, "on_video_track_close"):
        return
    if getattr(webrtc, "_bend_video_close_handler_bound", False):
        return

    def _on_video_end() -> None:
        context._input_channel_dirty = True
        invalidate_stream_video(context, clear_sdl=True)
        log.warning("xsrp video track 结束，已丢弃缓存帧并调度重连")
        logger.warning("WebRTC video track closed（handler）")
        schedule_task_timeline_event(
            context,
            MSG_INPUT_CHANNEL_CLOSED,
            event_key="video_track_closed",
            throttle_sec=15.0,
        )
        from .controller_write import schedule_input_reconnect

        schedule_input_reconnect(context, force=False)

    webrtc.on_video_track_close(_on_video_end)
    webrtc._bend_video_close_handler_bound = True


def bind_stream_health_handlers(context: Any, task_logger=None) -> None:
    """注册 input / video 通道异常回调（Step3 与重连成功后调用）。"""
    bind_input_close_handler(context, task_logger)
    bind_video_track_close_handler(context, task_logger)


def request_input_recovery(context: Any, *, force: bool = False) -> None:
    """同步上下文（F8 热键）触发 input 恢复，不阻塞 SDL 事件线程。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(kick_input_recovery(context, force=force))


async def kick_input_recovery(
    context: Any,
    task_logger=None,
    *,
    force: bool = False,
) -> bool:
    """
    人工接管 / 按键无效时恢复 input：先轻量 handshake，失败则调度全量重连。
    """
    log = task_logger or logger
    from .stream_keepalive import is_input_channel_open, try_restore_input_channel

    session = getattr(context, "xbox_session", None)
    if session is not None:
        await try_restore_input_channel(session)
        webrtc = getattr(session, "_webrtc", None)
        ready = webrtc is not None and getattr(webrtc, "is_input_ready", False)
        if is_input_channel_open(session) and ready:
            context._input_channel_dirty = False
            logger.info("GSSV input 轻量恢复成功（DataChannel open + input_ready）")
            log.info("GSSV input 轻量恢复成功")
            schedule_task_timeline_event(
                context,
                MSG_INPUT_RESTORED,
                event_key="input_channel_restored",
                throttle_sec=0.0,
            )
            return True

    if force:
        context._reconnect_manual_override = True
        bg = getattr(context, "_input_reconnect_bg_task", None)
        if bg is not None and bg.done():
            context._input_reconnect_bg_task = None

        from .controller_write import schedule_input_reconnect

        schedule_input_reconnect(context, force=True)
        logger.info("GSSV input 恢复：已请求后台全量重连（force=True）")
        schedule_task_timeline_event(
            context,
            MSG_INPUT_RECONNECTING,
            event_key="input_channel_reconnecting",
            throttle_sec=20.0,
        )
        return False

    # 对齐 streaming：channel closed 时不自动全量重连，仅标记 dirty
    context._input_channel_dirty = True
    logger.info("GSSV input 不可用，已标记 NOT_READY（需平台 reconnect_stream 或 F8 force）")
    return False


async def reconnect_input_channel(context: Any, task_logger=None) -> bool:
    """重连 GSSV 云端串流（重新 play/WebRTC 握手）。"""
    log = task_logger or logger
    lock = _get_reconnect_lock(context)

    if lock.locked():
        now = time.time()
        last_wait_log = float(
            getattr(context, "_reconnect_wait_log_at", 0.0) or 0.0
        )
        if now - last_wait_log >= 5.0:
            context._reconnect_wait_log_at = now
            msg = "输入通道重连已在进行中，等待完成..."
            log.info(msg)
            logger.info(msg)
        return False

    async with lock:
        try:
            now = time.time()
            attempts = getattr(context, "_reconnect_attempt_times", None)
            if attempts is None:
                attempts = []
                context._reconnect_attempt_times = attempts
            attempts[:] = [t for t in attempts if now - t < _RECONNECT_WINDOW_SEC]
            manual_override = bool(getattr(context, "_reconnect_manual_override", False))
            if manual_override:
                context._reconnect_manual_override = False
            elif len(attempts) >= _RECONNECT_MAX_IN_WINDOW:
                msg = f"60s 内重连次数已达上限 ({_RECONNECT_MAX_IN_WINDOW})，跳过重连"
                log.error(msg)
                logger.error(msg)
                await emit_input_reconnect_failed(context, "rate limit exceeded")
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
            logger.info("开始重连 GSSV 云端串流")
            invalidate_stream_video(context, clear_sdl=True)
            schedule_task_timeline_event(
                context,
                MSG_INPUT_RECONNECTING,
                event_key="input_channel_reconnecting",
                throttle_sec=0.0,
            )
            await cleanup_xsrp_cloud_attempt(context, log)
            creds = attach_streaming_credentials(context)
            ok, details = await asyncio.wait_for(
                connect_xsrp_cloud(context, creds, log, stream_logger),
                timeout=reconnect_timeout,
            )
            if not ok:
                err = details.get("errorMessage", details)
                log.error("云端串流重连失败: %s", err)
                logger.error("云端串流重连失败: %s", err)
                await emit_input_reconnect_failed(context, str(err))
                return False

            rebind_stream_bindings(
                context,
                executor=getattr(context, "_input_recovery_executor", None),
                switcher=getattr(context, "_input_recovery_switcher", None),
                engine=getattr(context, "_input_recovery_engine", None),
            )
            bind_stream_health_handlers(context, log)
            from .xsrp_access_input_loop import (
                reset_controller_write_stats,
                restart_xsrp_access_input_loop,
            )
            from .xsrp_stream_keepalive import stop_xsrp_idle_keepalive

            await stop_xsrp_idle_keepalive(context)
            reset_controller_write_stats(context)
            await restart_xsrp_access_input_loop(context, log)
            context._input_channel_dirty = False
            from ..runtime.stream_runtime import get_or_create_stream_runtime

            runtime = get_or_create_stream_runtime(context)
            if not runtime.is_capture_running:
                await runtime.start_long_lived(log)
            video_ok = await _await_fresh_video_after_reconnect(context, log)
            input_ok = await _verify_input_after_reconnect(context, log)
            if input_ok:
                await _wake_xbox_after_reconnect(context, log)
            log.info(
                "云端串流重连成功，会话引用已回绑 (video=%s input=%s)",
                video_ok,
                input_ok,
            )
            logger.info(
                "云端串流重连成功 (video=%s input=%s)",
                video_ok,
                input_ok,
            )
            schedule_task_timeline_event(
                context,
                MSG_INPUT_RESTORED,
                event_key="input_channel_restored",
                throttle_sec=0.0,
            )
            from .stream_session_survival import ensure_stream_subsystems_alive

            await ensure_stream_subsystems_alive(context, log, reason="reconnect_ok")
            return True
        except asyncio.TimeoutError:
            log.error("云端串流重连超时 (%ss)", reconnect_timeout)
            logger.error("云端串流重连超时 (%ss)", reconnect_timeout)
            await emit_input_reconnect_failed(context, "timeout")
            return False
        except Exception as exc:
            log.error("云端串流重连异常: %s", exc)
            logger.error("云端串流重连异常: %s", exc)
            await emit_input_reconnect_failed(context, str(exc))
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
