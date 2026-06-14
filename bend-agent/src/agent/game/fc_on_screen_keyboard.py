"""
FC / EA 登录页 On-Screen 小键盘（网格导航）
============================================

对齐 ttt/test_xsrp.py 的 keyboard_layout + move_to_char，用于 scene 230 等 EA 账号输入。
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, Tuple

from ..core.logger import get_logger
from ..input.controller_protocol import XboxButtonFlag

# (col, row) 网格坐标，与 ttt keyboard_layout 一致
FC_KEYBOARD_LAYOUT: Dict[str, Tuple[int, int]] = {
    "+": (-6, 1),
    "1": (-5, 1),
    "2": (-4, 1),
    "3": (-3, 1),
    "4": (-2, 1),
    "5": (-1, 1),
    "6": (0, 1),
    "7": (1, 1),
    "8": (2, 1),
    "9": (3, 1),
    "0": (4, 1),
    "q": (-5, 0),
    "w": (-4, 0),
    "e": (-3, 0),
    "r": (-2, 0),
    "t": (-1, 0),
    "y": (0, 0),
    "u": (1, 0),
    "i": (2, 0),
    "o": (3, 0),
    "p": (4, 0),
    "a": (-5, -1),
    "s": (-4, -1),
    "d": (-3, -1),
    "f": (-2, -1),
    "g": (-1, -1),
    "h": (0, -1),
    "j": (1, -1),
    "k": (2, -1),
    "l": (3, -1),
    "z": (-5, -2),
    "x": (-4, -2),
    "c": (-3, -2),
    "v": (-2, -2),
    "b": (-1, -2),
    "n": (0, -2),
    "m": (1, -2),
    "@": (-4, 1),
    ".": (3, -2),
}


class FcOnScreenKeyboard:
    """FC 小键盘：DPAD 网格导航 + A 确认 + Menu 提交。"""

    def __init__(self, switcher: Any):
        self._sw = switcher
        self._cursor: Tuple[int, int] = (-5, 0)
        self.logger = get_logger("fc_on_screen_keyboard")

    async def type_text(self, text: str, *, interval: float = 0.35) -> None:
        normalized = (text or "").strip().lower()
        if not normalized:
            return
        self.logger.info("FC 小键盘输入开始，长度=%d", len(normalized))
        await self._press("L3", 0.08)
        await asyncio.sleep(0.25)
        for ch in normalized:
            if ch not in FC_KEYBOARD_LAYOUT:
                raise ValueError(f"FC 小键盘暂不支持字符: {ch!r}")
            if ch == "@":
                await self._press("LT", 0.12)
            await self._move_to(FC_KEYBOARD_LAYOUT[ch])
            await self._press("A", 0.1)
            await asyncio.sleep(interval)
            if ch == "@":
                await self._press("LT", 0.12)
        await self._press("MENU", 0.1)
        await asyncio.sleep(0.5)

    async def _press(self, button: str, duration: float) -> None:
        if button == "LT":
            await self._sw._send_raw_controller(0, 255, 0, 0, 0, 0, 0, duration)
            await self._sw._send_raw_controller(0, 0, 0, 0, 0, 0, 0, 0.05)
            return
        if button == "L3":
            await self._sw._send_raw_controller(
                int(XboxButtonFlag.L3.value), 0, 0, 0, 0, 0, 0, duration
            )
            await self._sw._send_raw_controller(0, 0, 0, 0, 0, 0, 0, 0.05)
            return
        await self._sw._press_button(button, duration)

    async def _move_to(self, target: Tuple[int, int]) -> None:
        while self._cursor != target:
            cx, cy = self._cursor
            tx, ty = target
            if cx > tx:
                await self._press("DPAD_LEFT", 0.08)
                self._cursor = (cx - 1, cy)
            elif cx < tx:
                await self._press("DPAD_RIGHT", 0.08)
                self._cursor = (cx + 1, cy)
            elif cy > ty:
                await self._press("DPAD_DOWN", 0.08)
                self._cursor = (cx, cy - 1)
            elif cy < ty:
                await self._press("DPAD_UP", 0.08)
                self._cursor = (cx, cy + 1)
            await asyncio.sleep(0.12)
