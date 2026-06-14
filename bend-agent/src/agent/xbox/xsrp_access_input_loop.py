"""
xsrp 截图环手柄写入 — 对齐 streaming/xsrpd.py access_stream。

xsrpd 在 capture 循环内每帧 WriteControllerData（含 void）；空闲 >60s 附加 Nexus。
GSSV 云端无 C++ xsrp，用 WebRTC input DataChannel + 相同节奏（默认 30Hz）。
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from ..core.config import config
from ..core.logger import get_logger
from .controller_write import NEUTRAL_GAMEPAD, XSRP_NEXUS, write_controller_final

logger = get_logger("xsrp_access_input")


def reset_controller_write_stats(context: Any) -> None:
    """新 WebRTC 会话开始时清零写入统计。"""
    if context is None:
        return
    context._controller_write_stats = {"ok": 0, "fail": 0}
    context._controller_written_timestamp = 0.0


async def start_xsrp_access_input_loop(context: Any, task_logger=None) -> None:
    """启动与 capture FPS 对齐的单写循环（streaming access_stream 等价）。"""
    await stop_xsrp_access_input_loop(context)

    log = task_logger or logger
    fps = float(config.get("gssv.xsrp_capture_fps", 30))
    interval = 1.0 / max(1.0, fps)
    idle_pulse_sec = float(config.get("gssv.xsrp_streaming_idle_pulse_sec", 25))
    metadata_every_sec = float(config.get("gssv.input_metadata_refresh_sec", 30))

    async def _loop() -> None:
        log.info(
            "xsrp access 输入环已启动（%.1f Hz，idle Nexus>%ss，对齐 xsrpd WriteControllerData）",
            fps,
            idle_pulse_sec,
        )
        last_nexus_pulse = time.time()
        last_metadata = time.time()

        while True:
            session = getattr(context, "xbox_session", None)
            if session is None or not getattr(session, "is_connected", False):
                break

            # xsrpd：auto_play/auto_graph 期间不在 access 环写手柄
            runtime = getattr(context, "_stream_runtime", None)
            if runtime is not None and not runtime.is_manual_input_allowed():
                await asyncio.sleep(interval)
                continue

            gamepad = dict(NEUTRAL_GAMEPAD)
            now = time.time()

            # 对齐 xsrpd：持续 void + 空闲超阈值附加 Nexus（不随 neutral 刷新计时）
            if now - last_nexus_pulse >= idle_pulse_sec:
                gamepad["buttons"] = int(XSRP_NEXUS)
                last_nexus_pulse = now

            await write_controller_final(session, gamepad, context=context)

            if now - last_metadata >= metadata_every_sec:
                webrtc = getattr(context, "_cloud_webrtc", None)
                if webrtc is not None and hasattr(webrtc, "try_restore_input"):
                    await webrtc.try_restore_input()
                last_metadata = now

            await asyncio.sleep(interval)

        log.info("xsrp access 输入环已停止")

    context._xsrp_access_input_loop_task = asyncio.create_task(_loop())


async def restart_xsrp_access_input_loop(context: Any, task_logger=None) -> None:
    """重连后重启 access 输入环。"""
    await stop_xsrp_access_input_loop(context)
    reset_controller_write_stats(context)
    await start_xsrp_access_input_loop(context, task_logger)


async def stop_xsrp_access_input_loop(context: Any) -> None:
    task: Optional[asyncio.Task] = getattr(context, "_xsrp_access_input_loop_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    context._xsrp_access_input_loop_task = None


def is_xsrp_access_input_loop_running(context: Any) -> bool:
    task = getattr(context, "_xsrp_access_input_loop_task", None)
    return task is not None and not task.done()
