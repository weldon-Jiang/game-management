"""xsrp 串流空闲保活：对齐 streaming/xsrp.py hid_controller 60s DPadUp 防 idle-off。"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from ..core.config import config
from ..core.logger import get_logger

# xsrp.XSGamepadButtons.DPadUp
_XSRP_DPAD_UP = 4096


async def start_xsrp_idle_keepalive(context: Any, task_logger=None) -> None:
    """
    后台发送周期性 neutral/DPadUp 输入，防止云端串流因长时间无输入断开。

    对照 streaming StreamWindow.hid_controller：60s 无写入则 DPadUp 脉冲。
    """
    existing = getattr(context, "_xsrp_idle_keepalive_task", None)
    if existing and not existing.done():
        return

    log = task_logger or get_logger("xsrp_keepalive")
    interval_sec = float(config.get("gssv.xsrp_idle_keepalive_sec", 60))
    pulse_sec = float(config.get("gssv.xsrp_idle_pulse_sec", 0.05))

    async def _loop():
        log.info("xsrp 空闲保活已启动（间隔 %ss）", interval_sec)
        while True:
            session = getattr(context, "xbox_session", None)
            if session is None:
                break
            if not getattr(session, "is_connected", False):
                break
            await asyncio.sleep(interval_sec)
            try:
                await session.send_gamepad_state({"buttons": _XSRP_DPAD_UP})
                await asyncio.sleep(pulse_sec)
                await session.send_gamepad_state({"buttons": 0})
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.debug("xsrp idle keepalive: %s", exc)
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
