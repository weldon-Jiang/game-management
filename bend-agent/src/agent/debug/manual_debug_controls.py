"""
SDL 串流窗口调试快捷键：人工接管 + 截图。

默认（configs/agent.yaml debug.*）：
  F8  切换人工接管（暂停自动化按键，启用键盘/手柄）
  F9  保存 960×540 调试截图 → logs/manual_capture/{task_id}/
  F10 打印快捷键帮助

须先 **点击 Xbox 串流窗口** 使其获得焦点，快捷键才生效。
"""

from __future__ import annotations

from typing import Any, Optional

from ..core.config import config
from ..core.logger import get_logger
from ..task.task_timeline_events import (
    MSG_MANUAL_TAKEOVER_OFF,
    MSG_MANUAL_TAKEOVER_ON,
    schedule_task_timeline_event,
)
from .manual_capture import save_manual_capture

_logger = get_logger("manual_debug")

HELP_TEXT = """
=== Bend Agent 调试快捷键（须先点击串流窗口）===
  F8  人工接管 开/关（开=键盘/手柄可用；关=仅自动化可发键，F8/F9/F10 仍可用）
  F9  保存调试截图 960×540 → logs/manual_capture/{task_id}/
  F10 显示本帮助

  键盘映射: W/S/A/D=左摇杆  ↑↓←→=十字键  I/J/K/L=Y/X/A/B  Shift=LT  Space=RT  T/F/G/H=右摇杆  C/V=L3/R3  Ctrl=Xbox键  Enter=Start  Esc=View  Q/E=LB/RB
  截图后把 template/search 坐标发开发者，或自行裁 templates/{{scene}}.{{tpl}}.png
"""


def is_manual_takeover(context: Any) -> bool:
    return bool(getattr(context, "_manual_takeover", False))


def set_manual_takeover(context: Any, enabled: bool, *, reason: str = "") -> None:
    context._manual_takeover = bool(enabled)
    state = "ON" if enabled else "OFF"
    extra = f" ({reason})" if reason else ""
    _logger.info(
        "[人工接管] %s%s — 自动化按键已%s，键盘/手柄 %s",
        state,
        extra,
        "拦截" if enabled else "恢复",
        "可用" if enabled else "已禁用（仅自动化可发键；平台暂停仍可人工）",
    )
    if enabled:
        import time as _time

        context._manual_takeover_on_at = _time.time()
        context._manual_no_input_warn_at = 0.0
        context._manual_idle_pulse_at = 0.0
        from ..input.controller_protocol import ControllerSignal

        context._keyboard_overlay_signal = ControllerSignal.zero()
        pump = getattr(context, "_input_pump", None)
        if pump is not None and hasattr(pump, "reset_manual_nav_filter"):
            pump.reset_manual_nav_filter()
        from ..xbox.stream_session_survival import (
            schedule_ensure_stream_subsystems_alive,
        )

        schedule_ensure_stream_subsystems_alive(context, reason="manual_takeover_on")
        _logger.info(
            "[人工接管] 请点击串流窗口；键盘建议切英文输入法；"
            "WASD 左摇杆、方向键十字键、I/J/K/L 面键、Shift/Space 扳机、T/F/G/H 右摇杆、C/V L3/R3；已插手柄可直接按"
        )
        schedule_task_timeline_event(
            context,
            MSG_MANUAL_TAKEOVER_ON,
            event_key="manual_takeover_on",
        )
        context._manual_focus_warned = False
        keyboard = getattr(context, "_keyboard_mapper", None)
        if keyboard is not None and hasattr(keyboard, "set_manual_face_hold"):
            keyboard.set_manual_face_hold(True)
            from ..input.manual_nav import wire_manual_in_match_checker

            wire_manual_in_match_checker(context, keyboard)
            if hasattr(keyboard, "set_physical_mapping_enabled"):
                keyboard.set_physical_mapping_enabled(True)
            if hasattr(keyboard, "set_focused_win32_poll"):
                keyboard.set_focused_win32_poll(True)
        sdl = getattr(context, "sdl_window", None)
        if sdl is not None and hasattr(sdl, "is_foreground"):
            try:
                fg = bool(sdl.is_foreground())
                _logger.info(
                    "[人工接管] 串流窗口前台=%s hwnd=%s",
                    fg,
                    getattr(sdl, "_get_hwnd", lambda: None)(),
                )
            except Exception as exc:
                _logger.debug("人工接管前台检测: %s", exc)
        if sdl is not None:
            try:
                if hasattr(sdl, "show"):
                    sdl.show()
                elif hasattr(sdl, "_bring_to_front"):
                    sdl._bring_to_front()
            except Exception as exc:
                _logger.warning("人工接管前置串流窗口失败: %s", exc)
        try:
            from ..xbox.stream_keepalive import is_input_channel_open

            session = getattr(context, "xbox_session", None)
            video_stale = bool(getattr(context, "_stream_video_stale", False))
            if video_stale:
                from ..xbox.stream_recovery import (
                    invalidate_stream_video,
                    request_input_recovery,
                )

                _logger.warning(
                    "[人工接管] 视频帧已过期，将触发全量重连 Xbox 串流"
                )
                invalidate_stream_video(context, clear_sdl=True)
                request_input_recovery(context, force=True)
            elif session is not None and is_input_channel_open(session):
                webrtc = getattr(session, "_webrtc", None) or getattr(
                    context, "_cloud_webrtc", None
                )
                if webrtc is not None and getattr(webrtc, "is_input_ready", False):
                    pass
                else:
                    from ..xbox.stream_recovery import request_input_recovery

                    request_input_recovery(context, force=False)
            else:
                from ..xbox.stream_recovery import request_input_recovery

                request_input_recovery(context, force=True)
        except Exception as exc:
            _logger.warning("人工接管 input 恢复请求失败: %s", exc)
    else:
        schedule_task_timeline_event(
            context,
            MSG_MANUAL_TAKEOVER_OFF,
            event_key="manual_takeover_off",
        )
        context._manual_input_detected_reported = False
        context._manual_focus_warned = False
        keyboard = getattr(context, "_keyboard_mapper", None)
        if keyboard is not None:
            keyboard._pressed_keys.clear()
            if hasattr(keyboard, "set_focused_win32_poll"):
                keyboard.set_focused_win32_poll(False)
            if hasattr(keyboard, "set_manual_face_hold"):
                keyboard.set_manual_face_hold(False)
            if hasattr(keyboard, "set_physical_mapping_enabled"):
                keyboard.set_physical_mapping_enabled(False)
        pump = getattr(context, "_input_pump", None)
        if pump is not None and hasattr(pump, "reset_manual_nav_filter"):
            pump.reset_manual_nav_filter()
        from ..input.controller_protocol import ControllerSignal

        protocol = getattr(context, "_controller_protocol", None)
        if protocol is not None:
            try:
                import asyncio

                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(
                        protocol.send_manual_signal(ControllerSignal.zero())
                    )
            except Exception as exc:
                _logger.debug("F8 关闭释键: %s", exc)

        context._keyboard_overlay_signal = ControllerSignal.zero()


def toggle_manual_takeover(context: Any) -> None:
    set_manual_takeover(context, not is_manual_takeover(context), reason="F8")


def _hotkey_enabled(key: str, config_key: str, default: str) -> bool:
    configured = str(config.get(config_key, default)).lower()
    return key.lower() == configured


def attach_manual_debug_controls(
    context: Any,
    keyboard_mapper: Any,
    task_logger: Optional[Any] = None,
) -> None:
    """注册 F8/F9/F10；同一 context 仅注册一次。"""
    if getattr(context, "_manual_debug_attached", False):
        return
    if not config.get("debug.manual_input_enabled", True):
        return
    if keyboard_mapper is None or not hasattr(keyboard_mapper, "register_hotkey"):
        return

    takeover_key = str(config.get("debug.manual_takeover_hotkey", "f8")).lower()
    shot_key = str(config.get("debug.manual_screenshot_hotkey", "f9")).lower()
    help_key = str(config.get("debug.manual_help_hotkey", "f10")).lower()

    def _log(msg: str) -> None:
        if task_logger is not None:
            task_logger.info(msg)
        _logger.info(msg)

    def on_takeover() -> None:
        toggle_manual_takeover(context)

    def on_screenshot() -> None:
        path, msg = save_manual_capture(context, note="hotkey")
        _log(msg)
        if path:
            context._last_manual_capture_path = path
        else:
            _log(f"F9 截图失败: {msg}")

    def on_help() -> None:
        task_id = getattr(context, "task_id", "") or ""
        _log(HELP_TEXT.replace("{task_id}", str(task_id)))

    keyboard_mapper.register_hotkey(takeover_key, on_takeover)
    keyboard_mapper.register_hotkey(shot_key, on_screenshot)
    keyboard_mapper.register_hotkey(help_key, on_help)

    context._manual_debug_attached = True
    context._manual_takeover = False
    context._manual_capture_seq = getattr(context, "_manual_capture_seq", 0)

    _log(
        f"调试快捷键已启用: {takeover_key.upper()}=人工接管 "
        f"{shot_key.upper()}=截图 {help_key.upper()}=帮助 "
        f"(截图目录 logs/manual_capture/{{task_id}}/)"
    )
