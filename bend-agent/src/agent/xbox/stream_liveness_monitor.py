"""
串流活性监控 — READY/Step4 全程后台巡检 input 写入与视频帧 freshness。

目标：用户不操作时仍保持 GSSV input DataChannel 与视频轨活跃；异常时自动轻量恢复或调度全量重连。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from ..core.config import config
from ..core.logger import get_logger
from ..task.task_timeline_events import (
    MSG_INPUT_CHANNEL_CLOSED,
    schedule_task_timeline_event,
)
from .controller_write import (
    get_controller_written_timestamp,
    schedule_input_reconnect,
)
from .stream_recovery import (
    invalidate_stream_video,
    kick_input_recovery,
)

logger = get_logger("stream_liveness")


def _check_interval_sec() -> float:
    return float(config.get("gssv.liveness_check_sec", 10))


def _input_stale_sec() -> float:
    """GSSV input ~35s 无有效写入会断开，默认 28s 提前恢复。"""
    return float(config.get("gssv.input_stale_sec", 28))


def _video_stale_sec() -> float:
    return float(config.get("gssv.video_stale_sec", 45))


def _auto_reconnect_fail_threshold() -> int:
    return int(config.get("gssv.liveness_reconnect_after_failures", 3))


def get_last_video_frame_at(context: Any) -> float:
    webrtc = getattr(context, "_cloud_webrtc", None)
    if webrtc is not None:
        return float(getattr(webrtc, "_latest_frame_at", 0.0) or 0.0)
    return float(getattr(context, "_last_video_frame_at", 0.0) or 0.0)


def touch_video_frame_at(context: Any, when: Optional[float] = None) -> None:
    ts = time.time() if when is None else when
    context._last_video_frame_at = ts
    webrtc = getattr(context, "_cloud_webrtc", None)
    if webrtc is not None:
        webrtc._latest_frame_at = ts


async def start_stream_liveness_monitor(context: Any, task_logger=None) -> None:
    """Step3 完成后启动；同 task 仅一个监控协程。"""
    existing = getattr(context, "_stream_liveness_task", None)
    if existing and not existing.done():
        return

    log = task_logger or logger

    async def _loop() -> None:
        log.info(
            "串流活性监控已启动 (check=%ss input_stale=%ss video_stale=%ss)",
            _check_interval_sec(),
            _input_stale_sec(),
            _video_stale_sec(),
        )
        consecutive_input_stale = 0
        while True:
            await asyncio.sleep(_check_interval_sec())
            from ..core.agent_shutdown import is_agent_shutting_down

            if is_agent_shutting_down():
                break
            if not getattr(context, "_step3_init_completed", False):
                continue

            manual = bool(getattr(context, "_manual_takeover", False))
            paused = False
            if hasattr(context, "is_paused"):
                try:
                    paused = bool(context.is_paused())
                except Exception:
                    paused = False

            tick = int(getattr(context, "_survival_ensure_tick", 0) or 0) + 1
            context._survival_ensure_tick = tick
            if tick % 6 == 0:
                from .stream_session_survival import ensure_stream_subsystems_alive

                await ensure_stream_subsystems_alive(
                    context, log, reason="liveness_periodic"
                )

            session = getattr(context, "xbox_session", None)
            if session is None or not getattr(session, "is_connected", False):
                break

            bg = getattr(context, "_input_reconnect_bg_task", None)
            if bg is not None and not bg.done():
                continue

            now = time.time()
            last_write = get_controller_written_timestamp(context)
            write_age = now - last_write if last_write > 0 else 999.0
            last_video = get_last_video_frame_at(context)
            video_age = now - last_video if last_video > 0 else 0.0

            channel_dirty = bool(getattr(context, "_input_channel_dirty", False))
            input_stale = channel_dirty or (
                last_write > 0 and write_age > _input_stale_sec()
            )
            video_stale = last_video > 0 and video_age > _video_stale_sec()

            # 屏保变暗时视频轨可能仍在推静态暗帧，先尝试 Guide+A 唤醒
            if not video_stale:
                from .xbox_sleep_wake import try_wake_if_frame_dim

                if await try_wake_if_frame_dim(context, log):
                    await asyncio.sleep(3.0)
                    last_video = get_last_video_frame_at(context)
                    video_age = (
                        now - last_video if last_video > 0 else 0.0
                    )

            if video_stale:
                from .xbox_sleep_wake import try_wake_xbox_from_sleep

                await try_wake_xbox_from_sleep(context, log, reason="video_stale")
                await asyncio.sleep(5.0)
                last_video = get_last_video_frame_at(context)
                video_age = now - last_video if last_video > 0 else 999.0
                if last_video > 0 and video_age <= _video_stale_sec():
                    log.info(
                        "唤醒后视频帧已恢复 (age=%.1fs)，跳过重连",
                        video_age,
                    )
                    context._stream_video_stale = False
                    consecutive_input_stale = 0
                    continue

                log.warning(
                    "视频帧超时 %.0fs（阈值 %ss），丢弃缓存帧并调度重连",
                    video_age,
                    int(_video_stale_sec()),
                )
                invalidate_stream_video(context, clear_sdl=True)
                context._input_channel_dirty = True
                schedule_task_timeline_event(
                    context,
                    MSG_INPUT_CHANNEL_CLOSED,
                    event_key="video_track_stale",
                    throttle_sec=30.0,
                )
                schedule_input_reconnect(context, force=True)
                consecutive_input_stale = 0
                continue

            if manual or paused:
                if input_stale:
                    log.warning(
                        "人工/暂停期间 input 写入停滞 %.0fs，尝试恢复",
                        write_age,
                    )
                    recovered = await kick_input_recovery(context, log, force=False)
                    if not recovered:
                        consecutive_input_stale += 1
                        if consecutive_input_stale >= _auto_reconnect_fail_threshold():
                            schedule_input_reconnect(context, force=True)
                            consecutive_input_stale = 0
                else:
                    consecutive_input_stale = 0
                continue

            if input_stale:
                consecutive_input_stale += 1
                log.warning(
                    "input 写入超时 %.0fs（阈值 %ss，连续 %s 次）",
                    write_age,
                    int(_input_stale_sec()),
                    consecutive_input_stale,
                )
                force = consecutive_input_stale >= _auto_reconnect_fail_threshold()
                recovered = await kick_input_recovery(context, log, force=force)
                if not recovered and force:
                    log.warning("input 轻量恢复失败，调度全量重连")
                    schedule_input_reconnect(context, force=True)
                    consecutive_input_stale = 0
            else:
                consecutive_input_stale = 0

        log.info("串流活性监控已停止")

    context._stream_liveness_task = asyncio.create_task(_loop())


async def stop_stream_liveness_monitor(context: Any) -> None:
    task: Optional[asyncio.Task] = getattr(context, "_stream_liveness_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    context._stream_liveness_task = None
