"""
InputPump — 物理输入 DataChannel 泵。

焦点任务 125Hz，背景 10Hz，持续发送 neutral gamepad 保持 input DataChannel。
"""

import asyncio
import time
from typing import Any, Optional

from ..core.config import config as app_config
from ..core.logger import get_logger
from ..runtime.input_focus import InputFocusManager
from ..xbox.controller_write import (
    get_controller_written_timestamp,
    send_gssv_idle_pulse,
)
from .controller_protocol import ControllerProtocol, ControllerSignal


class InputPump:
    """按 InputFocus 切换频率，轮询手柄/键盘并发送 manual 信号。"""

    def __init__(
        self,
        context: Any,
        task_id: str,
        protocol: ControllerProtocol,
        focus_manager: Optional[InputFocusManager] = None,
    ):
        self._context = context
        self._task_id = task_id
        self._protocol = protocol
        self._focus = focus_manager or InputFocusManager.get_instance()
        self.logger = get_logger("input_pump")
        focus_hz = float(app_config.get("input.pump_focus_hz", 125))
        bg_hz = float(app_config.get("input.pump_background_hz", 10))
        self._focus_interval = 1.0 / max(1.0, focus_hz)
        self._background_interval = 1.0 / max(1.0, bg_hz)
        self._task: Optional[asyncio.Task] = None

    async def _send_void_or_pulse(self) -> None:
        """
        人工输入转发；void 保活由 xsrp access 输入环负责（对齐 xsrpd WriteControllerData）。

        非 xsrp 栈或无 access 环时回退为本地 neutral 写入。
        """
        from ..xbox.controller_write import NEUTRAL_GAMEPAD, schedule_input_reconnect, write_controller_final
        from ..xbox.stream_keepalive import is_input_channel_open
        from ..xbox.xsrp_access_input_loop import is_xsrp_access_input_loop_running

        session = getattr(self._context, "xbox_session", None)
        if session is None or not is_input_channel_open(session):
            schedule_input_reconnect(self._context)
            return

        signal = self._collect_signal()
        if not signal.is_void():
            await self._protocol.send_manual_signal(signal)
            return

        if is_xsrp_access_input_loop_running(self._context):
            return

        await write_controller_final(
            session,
            dict(NEUTRAL_GAMEPAD),
            context=self._context,
        )

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._run())
        self.logger.info(
            "InputPump 已启动 task=%s (focus=%.3fs bg=%.3fs)",
            self._task_id[:8],
            self._focus_interval,
            self._background_interval,
        )

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self.logger.info("InputPump 已停止 task=%s", self._task_id[:8])

    def _collect_signal(self) -> ControllerSignal:
        """合并物理手柄与键盘映射为单帧 ControllerSignal。"""
        signal = ControllerSignal()
        gamepad = getattr(self._context, "_gamepad_controller", None)
        if gamepad and getattr(gamepad, "is_initialized", False):
            try:
                gp_sig = gamepad.get_signals()
                signal = ControllerSignal.from_gamepad_signal(gp_sig)
            except Exception:
                pass

        keyboard = getattr(self._context, "_keyboard_mapper", None)
        overlay = getattr(self._context, "_keyboard_overlay_signal", None)
        if overlay is not None:
            signal.buttons |= overlay.buttons
            signal.left_trigger = max(signal.left_trigger, overlay.left_trigger)
            signal.right_trigger = max(signal.right_trigger, overlay.right_trigger)
            if overlay.left_thumb_x:
                signal.left_thumb_x = overlay.left_thumb_x
            if overlay.left_thumb_y:
                signal.left_thumb_y = overlay.left_thumb_y
            if overlay.right_thumb_x:
                signal.right_thumb_x = overlay.right_thumb_x
            if overlay.right_thumb_y:
                signal.right_thumb_y = overlay.right_thumb_y
        elif keyboard and hasattr(keyboard, "build_controller_signal"):
            try:
                kb_sig = keyboard.build_controller_signal()
                signal.buttons |= kb_sig.buttons
                if kb_sig.left_trigger:
                    signal.left_trigger = kb_sig.left_trigger
                if kb_sig.right_trigger:
                    signal.right_trigger = kb_sig.right_trigger
                signal.left_thumb_x = kb_sig.left_thumb_x or signal.left_thumb_x
                signal.left_thumb_y = kb_sig.left_thumb_y or signal.left_thumb_y
                signal.right_thumb_x = kb_sig.right_thumb_x or signal.right_thumb_x
                signal.right_thumb_y = kb_sig.right_thumb_y or signal.right_thumb_y
            except Exception:
                pass
        return signal

    async def _run(self) -> None:
        while True:
            try:
                runtime = getattr(self._context, "_stream_runtime", None)
                manual_allowed = (
                    runtime is None or runtime.is_manual_input_allowed()
                )
                if manual_allowed:
                    focused = self._focus.should_accept_physical_input(self._task_id)
                    interval = (
                        self._focus_interval if focused else self._background_interval
                    )
                    await self._send_void_or_pulse()
                else:
                    # Step4 graph/play：自动化按键为主；无输入时补 DPadUp。
                    interval = self._background_interval
                    await self._send_void_or_pulse()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.logger.debug("InputPump: %s", exc)
                await asyncio.sleep(self._background_interval)


async def start_input_pump(context: Any, task_id: str, protocol: ControllerProtocol) -> InputPump:
    existing = getattr(context, "_input_pump", None)
    if existing and existing.running:
        return existing
    pump = InputPump(context, task_id, protocol)
    context._input_pump = pump
    await pump.start()
    return pump


async def stop_input_pump(context: Any) -> None:
    pump = getattr(context, "_input_pump", None)
    if pump:
        await pump.stop()
    context._input_pump = None
