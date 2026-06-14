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
from .manual_capture import save_manual_capture

_logger = get_logger("manual_debug")

HELP_TEXT = """
=== Bend Agent 调试快捷键（须先点击串流窗口）===
  F8  人工接管 开/关（开=自动化不发键，键盘 WASD/ABXY 可用）
  F9  保存调试截图 960×540 → logs/manual_capture/{task_id}/
  F10 显示本帮助

  键盘映射: W/S/A/D=方向  J/B/X/Y=手柄面键  Enter=Start  Esc=View  Q/E=LB/RB
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
        "可用" if enabled else "随自动化/暂停策略",
    )
    if enabled:
        _logger.info("[人工接管] 请点击串流窗口，用 WASD/ABXY 操作 Xbox")


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
