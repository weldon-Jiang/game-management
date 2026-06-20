"""
串流会话存活 — Step3 成功后至任务结束前，保证 capture/输入/活性监控持续运行。

适用：自动化失败 (automation_failed)、F8 人工接管、长时间空闲等待。
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..core.logger import get_logger

logger = get_logger("stream_survival")


async def ensure_stream_subsystems_alive(
    context: Any,
    task_logger=None,
    *,
    reason: str = "",
) -> None:
    """
    幂等重启/确认串流子系统：capture 泵、access 输入环、活性监控、InputPump、SDL 显示泵。

    Step4 失败或人工接管后调用，避免仅停 graph/play 却误杀保活协程。
    """
    log = task_logger or logger
    if not getattr(context, "_step3_init_completed", False):
        return

    session = getattr(context, "xbox_session", None)
    if session is None or not getattr(session, "is_connected", False):
        return

    tag = f" ({reason})" if reason else ""

    from ..runtime.stream_runtime import get_or_create_stream_runtime

    runtime = get_or_create_stream_runtime(context)
    if not runtime.is_capture_running:
        await runtime.start_long_lived(log)
        log.info("会话存活：已重启 capture 泵%s", tag)

    from .xsrp_access_input_loop import (
        is_xsrp_access_input_loop_running,
        start_xsrp_access_input_loop,
    )

    if not is_xsrp_access_input_loop_running(context):
        await start_xsrp_access_input_loop(context, log)
        log.info("会话存活：已重启 access 输入环%s", tag)

    from .stream_liveness_monitor import start_stream_liveness_monitor

    liveness = getattr(context, "_stream_liveness_task", None)
    if liveness is None or liveness.done():
        await start_stream_liveness_monitor(context, log)
        log.info("会话存活：已重启串流活性监控%s", tag)

    protocol = getattr(context, "_controller_protocol", None)
    pump = getattr(context, "_input_pump", None)
    if protocol is not None and (pump is None or not pump.running):
        from ..input.pump_scheduler import start_input_pump

        task_id = getattr(context, "task_id", "") or "unknown"
        await start_input_pump(context, task_id, protocol)
        log.info("会话存活：已重启 InputPump%s", tag)

    if getattr(context, "enable_window_display", False) and getattr(
        context, "sdl_window", None
    ):
        from ..automation.step3_display_helpers import _start_sdl_display_pump

        await _start_sdl_display_pump(context, log)

    webrtc = getattr(context, "_cloud_webrtc", None)
    if webrtc is not None and hasattr(webrtc, "try_restore_input"):
        try:
            await webrtc.try_restore_input()
        except Exception as exc:
            log.debug("会话存活 input handshake 刷新: %s", exc)

    last_video = float(getattr(context, "_last_video_frame_at", 0.0) or 0.0)
    webrtc_at = float(getattr(webrtc, "_latest_frame_at", 0.0) or 0.0) if webrtc else 0.0
    if max(last_video, webrtc_at) > 0 and getattr(context, "_stream_video_stale", False):
        import time

        fresh_age = time.time() - max(last_video, webrtc_at)
        if fresh_age < 15.0:
            context._stream_video_stale = False
            log.info("会话存活：视频帧已恢复 fresh (%.1fs)%s", fresh_age, tag)


def schedule_ensure_stream_subsystems_alive(
    context: Any,
    *,
    reason: str = "",
) -> None:
    """非阻塞调度存活检查（F8 / 失败回调等同步上下文可用）。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(
        ensure_stream_subsystems_alive(context, reason=reason),
        name=f"stream_survival:{reason or 'async'}",
    )
