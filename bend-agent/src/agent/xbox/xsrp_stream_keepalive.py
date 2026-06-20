"""xsrp 串流空闲保活：对齐 streaming/xsrpd access_stream 持续 WriteControllerData。"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..core.config import config
from ..core.logger import get_logger
from .controller_write import NEUTRAL_GAMEPAD, send_gssv_idle_pulse, write_controller_final

logger = get_logger("xsrp_keepalive")


async def start_xsrp_idle_keepalive(context: Any, task_logger=None) -> None:
    """
    后台周期性 neutral gamepad + 偶发 DPadUp/Nexus 脉冲。

    xsrpd 在 capture 环每帧 WriteControllerData（含 void）；GSSV 云端须同样保持
    input 活跃，不能只在 18s 发一次脉冲。
    """
    existing = getattr(context, "_xsrp_idle_keepalive_task", None)
    if existing and not existing.done():
        return

    log = task_logger or logger
    interval_sec = float(config.get("gssv.xsrp_idle_keepalive_sec", 3))
    pulse_every_sec = float(config.get("gssv.xsrp_idle_pulse_every_sec", 15))
    pulse_every = max(1, int(round(pulse_every_sec / max(interval_sec, 0.5))))

    async def _loop():
        log.info(
            "xsrp 空闲保活已启动（neutral 间隔 %ss，脉冲每 %ss）",
            interval_sec,
            pulse_every_sec,
        )
        tick = 0
        while True:
            session = getattr(context, "xbox_session", None)
            if session is None:
                break
            if not getattr(session, "is_connected", False):
                break

            try:
                webrtc = getattr(context, "_cloud_webrtc", None)
                if webrtc is not None and hasattr(webrtc, "try_restore_input"):
                    await webrtc.try_restore_input()

                ok = await write_controller_final(
                    session,
                    dict(NEUTRAL_GAMEPAD),
                    context=context,
                )
                if not ok:
                    log.debug("xsrp idle keepalive neutral 发送失败")

                if tick == 0 or tick % pulse_every == 0:
                    pulse_ok = await send_gssv_idle_pulse(session, context=context)
                    if not pulse_ok:
                        log.debug("xsrp idle keepalive DPadUp/Nexus 脉冲失败")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.debug("xsrp idle keepalive: %s", exc)

            tick += 1
            await asyncio.sleep(interval_sec)

        log.info("xsrp 空闲保活已停止")

    context._xsrp_idle_keepalive_task = asyncio.create_task(_loop())


async def stop_xsrp_idle_keepalive(context: Any) -> None:
    task: Optional[asyncio.Task] = getattr(context, "_xsrp_idle_keepalive_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    context._xsrp_idle_keepalive_task = None
