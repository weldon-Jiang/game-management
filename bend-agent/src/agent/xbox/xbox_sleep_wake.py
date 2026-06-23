"""
Xbox 串流空闲变暗 / 待机检测与主动唤醒。

GSSV 视频轨在主机屏保变暗时可能仍推送帧（静态暗画面），仅靠 video_stale 无法发现。
通过画面亮度相对峰值下降判断，并发送 Guide(Nexus) + A 尝试唤醒。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional, Tuple

import cv2
import numpy as np

from ..core.config import config
from ..core.logger import get_logger
from ..vision.frame_utils import frame_to_bgr_ndarray

logger = get_logger("xbox_sleep_wake")

# 与 account_switcher 按 A 启动 FC 一致
_XSRP_A = 16


def _wake_cooldown_sec() -> float:
    return float(config.get("gssv.xbox_wake_cooldown_sec", 45))


def _dim_ratio_threshold() -> float:
    return float(config.get("gssv.xbox_idle_dim_ratio", 0.55))


def _dim_mean_threshold() -> float:
    return float(config.get("gssv.xbox_idle_dim_mean", 32))


def _min_peak_brightness() -> float:
    return float(config.get("gssv.xbox_idle_dim_min_peak", 50))


def is_likely_xbox_idle_dim(
    image: Any,
    context: Any,
) -> Tuple[bool, float, float]:
    """
    相对会话内亮度峰值，判断是否为 Xbox 主页空闲变暗/屏保。

    返回 (是否变暗, 当前均值, 会话峰值)。
    """
    img = frame_to_bgr_ndarray(image) if image is not None else None
    if img is None or not isinstance(img, np.ndarray) or img.size == 0:
        return False, 0.0, 0.0

    if img.ndim == 2:
        gray = img
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    mean = float(gray.mean())
    peak = float(getattr(context, "_xbox_brightness_peak", 0.0) or 0.0)
    if mean > peak:
        context._xbox_brightness_peak = mean
        peak = mean

    if peak < _min_peak_brightness():
        return False, mean, peak

    ratio = mean / peak if peak > 0 else 1.0
    dim = ratio < _dim_ratio_threshold() or mean < _dim_mean_threshold()
    return dim, mean, peak


def _wake_allowed(context: Any) -> bool:
    last = float(getattr(context, "_xbox_wake_last_at", 0.0) or 0.0)
    return time.time() - last >= _wake_cooldown_sec()


async def try_wake_xbox_from_sleep(
    context: Any,
    task_logger=None,
    *,
    reason: str = "",
) -> bool:
    """
    向 Xbox 发送 Guide(Nexus) + A 脉冲，尝试退出空闲变暗/待机 UI。

    冷却期内不重复发送，避免菜单乱跳。
    """
    log = task_logger or logger
    if not _wake_allowed(context):
        log.debug("Xbox 唤醒冷却中，跳过 (%s)", reason or "dim")
        return False

    session = getattr(context, "xbox_session", None)
    if session is None or not getattr(session, "is_connected", False):
        return False

    from .controller_write import send_button_pulse, XSRP_NEXUS
    from .stream_keepalive import is_input_channel_open, try_restore_input_channel

    if not is_input_channel_open(session):
        await try_restore_input_channel(session)

    context._xbox_wake_last_at = time.time()
    label = reason or "idle_dim"
    log.info("Xbox 可能睡眠/屏保，主动唤醒 (%s): Nexus → A", label)
    logger.info("Xbox sleep wake attempt (%s)", label)

    pulse = float(config.get("gssv.xsrp_idle_pulse_sec", 0.08))
    nexus_ok = await send_button_pulse(
        session, XSRP_NEXUS, context=context, pulse_sec=pulse
    )
    await asyncio.sleep(0.65)
    a_ok = await send_button_pulse(session, _XSRP_A, context=context, pulse_sec=pulse)
    await asyncio.sleep(0.35)
    await send_button_pulse(session, XSRP_NEXUS, context=context, pulse_sec=0.05)
    return bool(nexus_ok or a_ok)


async def try_wake_if_frame_dim(
    context: Any,
    task_logger=None,
) -> bool:
    """若最新帧变暗则唤醒；供活性监控周期调用。"""
    try:
        from ..runtime.stream_runtime import get_or_create_stream_runtime

        runtime = get_or_create_stream_runtime(context)
        img = runtime.get_latest_image()
    except Exception:
        img = None

    if img is None:
        return False

    dim, mean, peak = is_likely_xbox_idle_dim(img, context)
    if not dim:
        return False

    log = task_logger or logger
    log.warning(
        "Xbox 画面变暗 (mean=%.1f peak=%.1f ratio=%.2f)，触发主动唤醒",
        mean,
        peak,
        mean / peak if peak > 0 else 0.0,
    )
    return await try_wake_xbox_from_sleep(context, log, reason="idle_dim")
