"""
任务事件时间线上报 — 人工接管 / Input DataChannel 状态（摘要、节流）。

经 report_progress → TaskEventService.record，前端 TaskEventTimeline 展示。
不传 phase，避免篡改 streaming_session 阶段。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from ..core.logger import get_logger

logger = get_logger("task_timeline")

# 与 bend-platform-web TASK_EVENT_MESSAGE_MAP 键一致
MSG_MANUAL_TAKEOVER_ON = "Manual takeover ON"
MSG_MANUAL_TAKEOVER_OFF = "Manual takeover OFF"
MSG_INPUT_CHANNEL_CLOSED = "Input channel closed"
MSG_INPUT_RECONNECTING = "Input channel reconnecting"
MSG_INPUT_RESTORED = "Input channel restored"
MSG_MANUAL_INPUT_DETECTED = "Manual input detected"

TIMELINE_EVENT_MESSAGES = frozenset({
    MSG_MANUAL_TAKEOVER_ON,
    MSG_MANUAL_TAKEOVER_OFF,
    MSG_INPUT_CHANNEL_CLOSED,
    MSG_INPUT_RECONNECTING,
    MSG_INPUT_RESTORED,
    MSG_MANUAL_INPUT_DETECTED,
})


def is_timeline_event_message(message: str) -> bool:
    if not message:
        return False
    if message in TIMELINE_EVENT_MESSAGES:
        return True
    return message.startswith("Input channel reconnect failed:")


def _throttle_key(event_key: str) -> str:
    return f"_timeline_event_at_{event_key}"


def _should_emit(context: Any, event_key: str, throttle_sec: float) -> bool:
    if throttle_sec <= 0:
        return True
    attr = _throttle_key(event_key)
    now = time.time()
    last = float(getattr(context, attr, 0.0) or 0.0)
    if now - last < throttle_sec:
        return False
    setattr(context, attr, now)
    return True


def _resolve_platform_client(context: Any):
    client = getattr(context, "_platform_client", None)
    if client is not None:
        return client
    try:
        from ..task.automation_scheduler import get_active_scheduler

        scheduler = get_active_scheduler()
        if scheduler is not None:
            return getattr(scheduler, "_platform_client", None)
    except Exception:
        pass
    return None


async def emit_task_timeline_event(
    context: Any,
    message: str,
    *,
    status: str = "RUNNING",
    event_key: Optional[str] = None,
    throttle_sec: float = 0.0,
) -> None:
    """
    上报一条任务事件时间线摘要。

    - scope=session 且不带 phase，仅写入 task_event + progressMessage，不改 sessionPhase。
    - event_key + throttle_sec 在 Agent 侧节流，避免 125Hz 轮询刷屏。
    """
    if context is None or not message:
        return

    task_id = getattr(context, "task_id", None)
    if not task_id:
        return

    key = event_key or message
    if not _should_emit(context, key, throttle_sec):
        return

    client = _resolve_platform_client(context)
    if client is None:
        logger.debug("时间线事件跳过（无 PlatformApiClient）: %s", message)
        return

    try:
        await client.report_progress(
            task_id,
            "SESSION",
            status,
            message,
            scope="session",
            timelineEvent=True,
        )
        logger.info("时间线事件已上报: %s", message)
    except Exception as exc:
        logger.debug("时间线事件上报失败 (%s): %s", message, exc)


def schedule_task_timeline_event(
    context: Any,
    message: str,
    *,
    status: str = "RUNNING",
    event_key: Optional[str] = None,
    throttle_sec: float = 0.0,
) -> None:
    """同步上下文（F8 热键 / DataChannel close 回调）中安全调度上报。"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        return
    loop.create_task(
        emit_task_timeline_event(
            context,
            message,
            status=status,
            event_key=event_key,
            throttle_sec=throttle_sec,
        )
    )


async def emit_input_reconnect_failed(context: Any, reason: str) -> None:
    msg = f"Input channel reconnect failed: {reason}"
    await emit_task_timeline_event(
        context,
        msg,
        status="FAILED",
        event_key="input_reconnect_failed",
        throttle_sec=30.0,
    )
