"""
统一手柄 DataChannel 写入 — 对齐 streaming/xsrp.py write_controller_final。

所有经 DataChannel 的手柄包应走 write_controller_final / send_stream_keepalive，
成功写入后更新 context._controller_written_timestamp。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional

from ..core.config import config
from ..core.logger import get_logger

logger = get_logger("controller_write")

# xsrp.XSGamepadButtons
XSRP_DPAD_UP = 4096
XSRP_NEXUS = 2

NEUTRAL_GAMEPAD: Dict[str, int] = {
    "buttons": 0,
    "left_trigger": 0,
    "right_trigger": 0,
    "left_thumb_x": 0,
    "left_thumb_y": 0,
    "right_thumb_x": 0,
    "right_thumb_y": 0,
}

_FAIL_LOG_COOLDOWN_SEC = 10.0
_CHANNEL_CLOSED_LOG_COOLDOWN_SEC = 10.0
_OK_LOG_COOLDOWN_SEC = 30.0
_RECONNECT_LOG_COOLDOWN_SEC = 10.0
_RECONNECT_SCHEDULE_COOLDOWN_SEC = 10.0


def get_controller_written_timestamp(context: Any) -> float:
    """上次成功写入 DataChannel 的时间戳（streaming controller_written_timestamp）。"""
    if context is None:
        return 0.0
    return float(getattr(context, "_controller_written_timestamp", 0.0) or 0.0)


def mark_controller_written(context: Any) -> None:
    if context is not None:
        context._controller_written_timestamp = time.time()


def _bump_write_stat(context: Optional[Any], *, ok: bool) -> Dict[str, int]:
    if context is None:
        return {"ok": 0, "fail": 0}
    stats = getattr(context, "_controller_write_stats", None)
    if not isinstance(stats, dict):
        stats = {"ok": 0, "fail": 0}
        context._controller_write_stats = stats
    key = "ok" if ok else "fail"
    stats[key] = int(stats.get(key, 0)) + 1
    return stats


def _log_write_failure_throttled(
    context: Optional[Any],
    session: Any,
    stats: Dict[str, int],
) -> None:
    now = time.time()
    last_at = float(getattr(context, "_controller_write_fail_log_at", 0.0) or 0.0)
    if now - last_at < _FAIL_LOG_COOLDOWN_SEC:
        return
    if context is not None:
        context._controller_write_fail_log_at = now

    from .stream_keepalive import get_input_channel_state

    state = get_input_channel_state(session)
    logger.info(
        "手柄 DataChannel 写入失败 (ok=%d fail=%d state=%s)",
        stats.get("ok", 0),
        stats.get("fail", 0),
        state,
    )


def _maybe_log_write_success(context: Optional[Any]) -> None:
    if context is None:
        return
    now = time.time()
    last_at = float(getattr(context, "_controller_write_ok_log_at", 0.0) or 0.0)
    if now - last_at < _OK_LOG_COOLDOWN_SEC:
        return
    context._controller_write_ok_log_at = now
    stats = getattr(context, "_controller_write_stats", {}) or {}
    logger.info(
        "手柄 DataChannel 写入正常 (ok=%d fail=%d)",
        stats.get("ok", 0),
        stats.get("fail", 0),
    )


async def ensure_channel_writable(
    session: Any,
    context: Optional[Any] = None,
) -> bool:
    """
    写入前检查 input DataChannel；open 但 _input_ready 丢失时轻量 restore；
    closed 时调度后台重连，避免对 dead 通道刷屏 send。
    """
    from .stream_keepalive import (
        is_input_channel_open,
        try_restore_input_channel,
    )

    if session is None:
        return False

    webrtc = None
    if hasattr(session, "_webrtc"):
        webrtc = session._webrtc
    elif hasattr(session, "try_restore_input"):
        webrtc = session

    if is_input_channel_open(session):
        if webrtc is not None and hasattr(webrtc, "is_input_ready"):
            if not webrtc.is_input_ready and hasattr(webrtc, "try_restore_input"):
                await webrtc.try_restore_input()
        elif hasattr(session, "is_input_channel_healthy"):
            if not session.is_input_channel_healthy():
                await try_restore_input_channel(session)
        if is_input_channel_open(session):
            if webrtc is not None and hasattr(webrtc, "is_input_ready"):
                return bool(webrtc.is_input_ready)
            if hasattr(session, "is_input_channel_healthy"):
                return bool(session.is_input_channel_healthy())
            return True

    await try_restore_input_channel(session)
    if is_input_channel_open(session):
        if webrtc is not None and hasattr(webrtc, "try_restore_input"):
            await webrtc.try_restore_input()
        if webrtc is not None and hasattr(webrtc, "is_input_ready"):
            return bool(webrtc.is_input_ready)
        return True

    if context is not None:
        context._input_channel_dirty = True
    schedule_input_reconnect(context)
    _log_channel_closed_throttled(context, session)
    return False


def _log_channel_closed_throttled(context: Optional[Any], session: Any) -> None:
    now = time.time()
    last_at = float(getattr(context, "_channel_closed_log_at", 0.0) or 0.0)
    if now - last_at < _CHANNEL_CLOSED_LOG_COOLDOWN_SEC:
        return
    if context is not None:
        context._channel_closed_log_at = now
    from .stream_keepalive import get_input_channel_state

    state = get_input_channel_state(session)
    logger.info(
        "input DataChannel 非 open (state=%s)，跳过写入并已调度重连",
        state,
    )


def _log_reconnect_scheduled_throttled(context: Optional[Any]) -> None:
    """InputPump 125Hz 轮询时避免同一秒内刷屏。"""
    now = time.time()
    last_at = float(getattr(context, "_input_reconnect_log_at", 0.0) or 0.0)
    if now - last_at < _RECONNECT_LOG_COOLDOWN_SEC:
        return
    if context is not None:
        context._input_reconnect_log_at = now
    logger.info("已调度后台 GSSV input 重连")


def _log_reconnect_callback_missing_throttled(context: Optional[Any]) -> None:
    now = time.time()
    last_at = float(
        getattr(context, "_input_reconnect_missing_log_at", 0.0) or 0.0
    )
    if now - last_at < _RECONNECT_LOG_COOLDOWN_SEC:
        return
    if context is not None:
        context._input_reconnect_missing_log_at = now
    logger.warning(
        "input 重连回调未注册，无法后台重连（需 Step3 install_task_input_recovery）"
    )


def schedule_input_reconnect(context: Any) -> None:
    """调度后台全量重连，不阻塞调用方（AccountSwitcher / keepalive 共用）。"""
    if context is None:
        return

    bg = getattr(context, "_input_reconnect_bg_task", None)
    if bg is not None and not bg.done():
        return

    now = time.time()
    last_at = float(getattr(context, "_input_reconnect_scheduled_at", 0.0) or 0.0)
    if now - last_at < _RECONNECT_SCHEDULE_COOLDOWN_SEC:
        return

    callback = getattr(context, "_input_reconnect_callback", None)
    if callback is None:
        _log_reconnect_callback_missing_throttled(context)
        return

    context._input_reconnect_scheduled_at = now

    async def _run() -> None:
        try:
            await callback()
        except Exception as exc:
            logger.warning("后台 input 重连失败: %s", exc)
        finally:
            context._input_reconnect_bg_task = None

    context._input_reconnect_bg_task = asyncio.create_task(_run())
    _log_reconnect_scheduled_throttled(context)


async def write_controller_final(
    session: Any,
    gamepad_data: Dict[str, Any],
    *,
    context: Optional[Any] = None,
) -> bool:
    """streaming write_controller_final 等价：成功则更新 last_write_ts，失败触发恢复。"""
    if session is None:
        stats = _bump_write_stat(context, ok=False)
        _log_write_failure_throttled(context, session, stats)
        return False
    send = getattr(session, "send_gamepad_state", None)
    if send is None:
        stats = _bump_write_stat(context, ok=False)
        _log_write_failure_throttled(context, session, stats)
        return False
    if not await ensure_channel_writable(session, context):
        return False
    ok = await send(gamepad_data)
    stats = _bump_write_stat(context, ok=ok)
    if ok:
        mark_controller_written(context)
        _maybe_log_write_success(context)
        return True
    _log_write_failure_throttled(context, session, stats)
    if context is not None:
        await handle_write_failure(context, session)
    return False


async def send_button_pulse(
    session: Any,
    button_mask: int,
    *,
    context: Optional[Any] = None,
    pulse_sec: Optional[float] = None,
) -> bool:
    """单键按下 → 短等待 → 释放。"""
    if pulse_sec is None:
        pulse_sec = float(config.get("gssv.xsrp_idle_pulse_sec", 0.05))

    from .stream_keepalive import is_input_channel_open, try_restore_input_channel

    if not is_input_channel_open(session):
        await try_restore_input_channel(session)

    press_ok = await write_controller_final(
        session,
        {**NEUTRAL_GAMEPAD, "buttons": int(button_mask) & 0xFFFF},
        context=context,
    )
    if not press_ok:
        return False
    await asyncio.sleep(pulse_sec)
    return await write_controller_final(session, dict(NEUTRAL_GAMEPAD), context=context)


async def send_dpad_up_pulse(
    session: Any,
    *,
    context: Optional[Any] = None,
    pulse_sec: Optional[float] = None,
) -> bool:
    """DPadUp 按下 → 短等待 → 释放（对齐 streaming hid_controller 空闲保活）。"""
    return await send_button_pulse(
        session, XSRP_DPAD_UP, context=context, pulse_sec=pulse_sec
    )


async def send_gssv_idle_pulse(
    session: Any,
    *,
    context: Optional[Any] = None,
    pulse_sec: Optional[float] = None,
) -> bool:
    """
    GSSV 空闲保活：DPadUp / Nexus 交替（xsrp.py hid 用 DPadUp，xsrpd 捕获环用 Nexus）。
    """
    tick = 0
    if context is not None:
        tick = int(getattr(context, "_gssv_idle_pulse_tick", 0) or 0)
        context._gssv_idle_pulse_tick = tick + 1
    mask = XSRP_DPAD_UP if tick % 2 == 0 else XSRP_NEXUS
    return await send_button_pulse(session, mask, context=context, pulse_sec=pulse_sec)


def _is_gssv_session(session: Any) -> bool:
    from .stream_keepalive import _resolve_webrtc

    return _resolve_webrtc(session) is not None


async def send_stream_keepalive(
    session: Any,
    *,
    context: Optional[Any] = None,
) -> bool:
    """GSSV 路径发 DPadUp 脉冲；非 GSSV 发 neutral 包。"""
    if session is None:
        return False
    if not await ensure_channel_writable(session, context):
        return False
    if _is_gssv_session(session):
        # 常规 tick 发 neutral（对齐 xsrpd 持续 WriteControllerData）；脉冲由 idle 循环负责
        return await write_controller_final(
            session, dict(NEUTRAL_GAMEPAD), context=context
        )
    if hasattr(session, "send_keepalive"):
        ok = await session.send_keepalive()
        if ok:
            mark_controller_written(context)
            _bump_write_stat(context, ok=True)
        elif context is not None:
            _bump_write_stat(context, ok=False)
            await handle_write_failure(context, session)
        return ok
    return await write_controller_final(session, dict(NEUTRAL_GAMEPAD), context=context)


async def handle_write_failure(context: Any, session: Any) -> None:
    """发送失败：先轻量 restore；通道仍不可用则调度后台重连。"""
    from .stream_keepalive import is_input_channel_open, try_restore_input_channel

    if session is not None and is_input_channel_open(session):
        webrtc = getattr(session, "_webrtc", None)
        if webrtc is not None and hasattr(webrtc, "try_restore_input"):
            if not webrtc.is_input_ready:
                await webrtc.try_restore_input()
                if webrtc.is_input_ready:
                    return
        elif hasattr(session, "is_input_channel_healthy") and session.is_input_channel_healthy():
            return
        await try_restore_input_channel(session)
        if hasattr(session, "is_input_channel_healthy") and session.is_input_channel_healthy():
            return

    if session is not None:
        await try_restore_input_channel(session)
        if is_input_channel_open(session):
            webrtc = getattr(session, "_webrtc", None)
            if webrtc is not None and hasattr(webrtc, "try_restore_input"):
                await webrtc.try_restore_input()
            if hasattr(session, "is_input_channel_healthy") and session.is_input_channel_healthy():
                return

    if context is not None:
        context._input_channel_dirty = True
    schedule_input_reconnect(context)
