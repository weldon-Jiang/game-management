"""
F8 人工接管 — 输入整形。

- 左摇杆（含键盘 WASD→stick）：持续透传，供比赛内带球/跑动。
- 物理 DPad：短按一格 + 长按连滚，供 Xbox/UT 菜单导航。
- 面键 A/B/X/Y：按住持续发送。
"""

from __future__ import annotations

import time
from typing import Dict, FrozenSet, Optional, Set

from ..core.config import config as app_config
from .controller_protocol import ControllerSignal, XboxButtonFlag

_STICK_AXIS_THRESHOLD = 0.45
_STICK_VALUE_THRESHOLD = int(_STICK_AXIS_THRESHOLD * 32767)

_NAV_MASK = int(
    XboxButtonFlag.DPAD_UP
    | XboxButtonFlag.DPAD_DOWN
    | XboxButtonFlag.DPAD_LEFT
    | XboxButtonFlag.DPAD_RIGHT
)

_DIR_TO_BUTTON = {
    "up": XboxButtonFlag.DPAD_UP,
    "down": XboxButtonFlag.DPAD_DOWN,
    "left": XboxButtonFlag.DPAD_LEFT,
    "right": XboxButtonFlag.DPAD_RIGHT,
}


def manual_keyboard_uses_stick() -> bool:
    """stick=比赛 WASD 走左摇杆；dpad=键盘也发十字键（仅菜单）。"""
    mode = str(app_config.get("debug.manual_keyboard_movement", "stick")).lower().strip()
    return mode != "dpad"


def _nav_repeat_delay_sec() -> float:
    return float(app_config.get("debug.manual_nav_repeat_delay_sec", 0.45))


def _nav_repeat_interval_sec() -> float:
    return float(app_config.get("debug.manual_nav_repeat_interval_sec", 0.12))


class ManualInputShaper:
    """人工输入：摇杆透传 + DPad 菜单脉冲 + 面键长按。"""

    def __init__(self) -> None:
        self._next_repeat_at: Dict[str, float] = {}

    def reset(self) -> None:
        self._next_repeat_at.clear()

    def _dpad_directions(self, signal: ControllerSignal) -> FrozenSet[str]:
        """仅物理/键盘 DPad 位，不含左摇杆 analog。"""
        dirs: Set[str] = set()
        buttons = int(signal.buttons)
        if buttons & XboxButtonFlag.DPAD_UP:
            dirs.add("up")
        if buttons & XboxButtonFlag.DPAD_DOWN:
            dirs.add("down")
        if buttons & XboxButtonFlag.DPAD_LEFT:
            dirs.add("left")
        if buttons & XboxButtonFlag.DPAD_RIGHT:
            dirs.add("right")
        return frozenset(dirs)

    def _nav_pulse_mask(self, current: FrozenSet[str], now: float) -> int:
        delay = _nav_repeat_delay_sec()
        interval = _nav_repeat_interval_sec()
        pulse = 0

        for direction in current:
            next_at = self._next_repeat_at.get(direction)
            if next_at is None:
                pulse |= int(_DIR_TO_BUTTON[direction])
                self._next_repeat_at[direction] = now + delay
            elif now >= next_at:
                pulse |= int(_DIR_TO_BUTTON[direction])
                self._next_repeat_at[direction] = now + interval

        for direction in list(self._next_repeat_at.keys()):
            if direction not in current:
                del self._next_repeat_at[direction]

        return pulse

    def apply(self, raw: ControllerSignal, *, now: Optional[float] = None) -> ControllerSignal:
        if now is None:
            now = time.monotonic()

        dpad_dirs = self._dpad_directions(raw)
        nav_pulse = self._nav_pulse_mask(dpad_dirs, now)

        out = ControllerSignal()
        out.left_trigger = raw.left_trigger
        out.right_trigger = raw.right_trigger
        out.right_thumb_x = raw.right_thumb_x
        out.right_thumb_y = raw.right_thumb_y
        # 左摇杆（手柄 / 键盘 WASD stick 模式）原样透传，比赛内移动依赖此项
        out.left_thumb_x = raw.left_thumb_x
        out.left_thumb_y = raw.left_thumb_y

        out.buttons = int(raw.buttons) & ~_NAV_MASK
        out.buttons |= nav_pulse
        return out


ManualNavPulseFilter = ManualInputShaper
