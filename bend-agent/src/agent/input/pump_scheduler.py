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
        self._last_manual_input_log_at = 0.0
        self._last_gamepad_probe_at = 0.0
        self._last_manual_send_at = 0.0
        self._manual_nav_filter = None
        # 对齐 xsrpd access_stream WriteControllerData（默认 30Hz，勿 125Hz 刷爆 GSSV）
        capture_fps = float(app_config.get("gssv.xsrp_capture_fps", 30))
        self._manual_send_interval = 1.0 / max(1.0, capture_fps)

    def _is_manual_active(self) -> bool:
        manual = bool(getattr(self._context, "_manual_takeover", False))
        if not manual and hasattr(self._context, "is_paused"):
            try:
                manual = manual or bool(self._context.is_paused())
            except Exception:
                pass
        return manual

    def _format_signal_parts(self, signal: ControllerSignal) -> str:
        parts = []
        if signal.buttons:
            parts.append(f"buttons=0x{int(signal.buttons):X}")
        if signal.left_thumb_x or signal.left_thumb_y:
            parts.append(f"L=({signal.left_thumb_x},{signal.left_thumb_y})")
        if signal.right_thumb_x or signal.right_thumb_y:
            parts.append(f"R=({signal.right_thumb_x},{signal.right_thumb_y})")
        return " ".join(parts)

    async def _maybe_attach_gamepad(self) -> None:
        """Step3 未检测到手柄时，InputPump 周期重试热插拔。"""
        existing = getattr(self._context, "_gamepad_controller", None)
        if existing and getattr(existing, "is_initialized", False):
            return

        now = time.time()
        if now - self._last_gamepad_probe_at < 5.0:
            return
        self._last_gamepad_probe_at = now

        try:
            import pygame

            pygame.joystick.init()
            if pygame.joystick.get_count() <= 0:
                return

            from .xbox_gamepad import XboxGamepadController

            gamepad = XboxGamepadController(controller_id=0)
            if await gamepad.initialize():
                self._context._gamepad_controller = gamepad
                self.logger.info("手柄热插拔已连接: %s", gamepad.controller_name)
        except Exception as exc:
            self.logger.debug("手柄热插拔检测: %s", exc)

    def _is_stream_window_focused(self) -> bool:
        sdl = getattr(self._context, "sdl_window", None)
        if sdl is not None and hasattr(sdl, "is_foreground"):
            try:
                return bool(sdl.is_foreground())
            except Exception:
                pass
        return False

    def _prepare_keyboard_poll(self) -> None:
        """人工接管时刷新键盘 overlay；SDL 转发路径在窗口获焦时补 Win32 轮询。"""
        keyboard = getattr(self._context, "_keyboard_mapper", None)
        if keyboard is None:
            return
        if not self._is_manual_active():
            if hasattr(keyboard, "set_focused_win32_poll"):
                keyboard.set_focused_win32_poll(False)
            return
        if getattr(keyboard, "_external_event_pump", False):
            focused = self._is_stream_window_focused()
            if hasattr(keyboard, "set_focused_win32_poll"):
                keyboard.set_focused_win32_poll(focused)
            if not focused and not getattr(self._context, "_manual_focus_warned", False):
                self._context._manual_focus_warned = True
                self.logger.warning(
                    "[人工输入] 串流窗口未获焦，WASD 无效；请点击 Xbox 串流窗口后再按键"
                )
        else:
            self._context._manual_focus_warned = False
        if hasattr(keyboard, "sync_overlay_from_poll"):
            keyboard.sync_overlay_from_poll()

    def _maybe_log_manual_input(self, signal: ControllerSignal) -> None:
        if signal.is_void():
            return
        now = time.time()
        if now - self._last_manual_input_log_at < 2.0:
            return
        self._last_manual_input_log_at = now
        self.logger.info(
            "[人工输入] %s → DataChannel",
            self._format_signal_parts(signal),
        )

    def _maybe_log_manual_input_blocked(self, signal: ControllerSignal) -> None:
        if signal.is_void() or not self._is_manual_active():
            return
        now = time.time()
        if now - self._last_manual_input_log_at < 2.0:
            return
        self._last_manual_input_log_at = now
        self.logger.warning(
            "[人工输入] %s — DataChannel 未 open，正在恢复…",
            self._format_signal_parts(signal),
        )

    def _get_manual_nav_filter(self):
        if self._manual_nav_filter is None:
            from .manual_nav import ManualInputShaper

            self._manual_nav_filter = ManualInputShaper()
        return self._manual_nav_filter

    def _shape_manual_signal(self, signal: ControllerSignal) -> ControllerSignal:
        """F8 人工：导航短按/长按重复；面键持续按住透传。"""
        return self._get_manual_nav_filter().apply(signal, now=time.monotonic())

    def reset_manual_nav_filter(self) -> None:
        if self._manual_nav_filter is not None:
            self._manual_nav_filter.reset()

    async def _send_void_or_pulse(self) -> None:
        """
        人工输入转发；F8 期间以 xsrp capture FPS（默认 30Hz）写入，避免 125Hz 刷爆 GSSV。
        非人工时 void 保活由 xsrp access 输入环负责。
        """
        from ..xbox.controller_write import NEUTRAL_GAMEPAD, write_controller_final
        from ..xbox.stream_keepalive import is_input_channel_open
        from ..xbox.xsrp_access_input_loop import is_xsrp_access_input_loop_running

        manual_active = self._is_manual_active()
        signal = self._collect_signal()
        session = getattr(self._context, "xbox_session", None)
        channel_open = session is not None and is_input_channel_open(session)

        if not channel_open:
            if manual_active and not signal.is_void():
                self._maybe_log_manual_input_blocked(signal)
                if not getattr(self._context, "_manual_input_detected_reported", False):
                    self._context._manual_input_detected_reported = True
                    from ..task.task_timeline_events import (
                        MSG_MANUAL_INPUT_DETECTED,
                        schedule_task_timeline_event,
                    )

                    schedule_task_timeline_event(
                        self._context,
                        MSG_MANUAL_INPUT_DETECTED,
                        event_key="manual_input_detected",
                    )
            self._context._input_channel_dirty = True
            return

        if manual_active and not signal.is_void():
            if not getattr(self._context, "_manual_input_detected_reported", False):
                self._context._manual_input_detected_reported = True
                from ..task.task_timeline_events import (
                    MSG_MANUAL_INPUT_DETECTED,
                    schedule_task_timeline_event,
                )

                schedule_task_timeline_event(
                    self._context,
                    MSG_MANUAL_INPUT_DETECTED,
                    event_key="manual_input_detected",
                )

        # 所有 DataChannel 写入统一 30Hz（对齐 xsrpd WriteControllerData），
        # 避免 125Hz 采样 + Win32 误报导致菜单乱跳与刷爆通道。
        now = time.time()
        if now - self._last_manual_send_at < self._manual_send_interval:
            return
        self._last_manual_send_at = now

        if manual_active:
            if not signal.is_void():
                signal = self._shape_manual_signal(signal)
            if not signal.is_void():
                self._maybe_log_manual_input(signal)
                await self._protocol.send_manual_signal(signal)
                return
            await write_controller_final(
                session,
                dict(NEUTRAL_GAMEPAD),
                context=self._context,
            )
            return

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
        # SDL 转发路径在 feed_pygame_event 同步写入 _pressed_keys，overlay 靠异步回调可能滞后；
        # 始终合并 build_controller_signal，避免 F8 有效但 WASD 无输入。
        if keyboard and hasattr(keyboard, "build_controller_signal"):
            try:
                kb_sig = keyboard.build_controller_signal()
                signal.buttons |= kb_sig.buttons
                if kb_sig.left_trigger:
                    signal.left_trigger = max(signal.left_trigger, kb_sig.left_trigger)
                if kb_sig.right_trigger:
                    signal.right_trigger = max(signal.right_trigger, kb_sig.right_trigger)
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
                await self._maybe_attach_gamepad()
                self._prepare_keyboard_poll()

                runtime = getattr(self._context, "_stream_runtime", None)
                manual_allowed = (
                    runtime is None or runtime.is_manual_input_allowed()
                )
                if manual_allowed:
                    # F8 人工接管 / 平台暂停：始终 125Hz 采样键盘，避免背景 10Hz 手感发粘
                    manual_active = self._is_manual_active()
                    focused = self._focus.should_accept_physical_input(self._task_id)
                    interval = self._focus_interval if (
                        manual_active or focused
                    ) else self._background_interval
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
