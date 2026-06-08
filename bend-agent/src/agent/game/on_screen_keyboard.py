"""
Xbox 登录页 On-Screen 小键盘输入
================================

QWERTY 网格相对导航 + 单场景校验（对齐 streaming 场景 11-64）。
"""

import asyncio
import time
from typing import Optional, Dict, Tuple, Callable, Awaitable, Any

from ..core.logger import get_logger
from ..scene.game_automation_engine import Action, ActionType


# 字符 -> 焦点场景编号（键位被选中时的场景 ID）
CHAR_TO_SCENE: Dict[str, int] = {
    '1': 20, '2': 21, '3': 22, '4': 23, '5': 24,
    '6': 25, '7': 26, '8': 27, '9': 28, '0': 29,
    'q': 30, 'w': 31, 'e': 32, 'r': 33, 't': 34,
    'y': 35, 'u': 36, 'i': 37, 'o': 38, 'p': 39,
    'a': 40, 's': 41, 'd': 42, 'f': 43, 'g': 44,
    'h': 45, 'j': 46, 'k': 47, 'l': 48, 'z': 50,
    'x': 51, 'c': 52, 'v': 53, 'b': 54, 'n': 55,
    'm': 56, ',': 57, '.': 58, '?': 59,
    '@': 14, ' ': 15,
}

KEY_ROWS = (
    "1234567890",
    "qwertyuiop",
    "asdfghjkl",
    "zxcvbnm,.?",
)


def _grid_pos(ch: str) -> Tuple[int, int]:
    for row_idx, row in enumerate(KEY_ROWS):
        col_idx = row.find(ch)
        if col_idx >= 0:
            return row_idx, col_idx
    raise KeyError(ch)


class OnScreenKeyboard:
    """屏幕小键盘输入器（网格导航）。"""

    def __init__(
        self,
        action_executor,
        scene_detector,
        frame_getter: Callable[[], Awaitable[Any]],
        threshold: float = 0.55,
        stream_session=None,
    ):
        self._executor = action_executor
        self._scene_detector = scene_detector
        self._frame_getter = frame_getter
        self._threshold = threshold
        self._stream_session = stream_session
        self._cursor: Tuple[int, int] = (1, 0)  # 默认在 'a'
        self.logger = get_logger('on_screen_keyboard')

    async def ensure_open(self) -> None:
        """确保电子邮件输入框已聚焦且小键盘可见。"""
        if await self._scene_matches(40) or await self._scene_matches(30) or await self._scene_matches(20):
            return
        await self._press_button('A', duration=0.1)
        await asyncio.sleep(0.6)
        if await self._scene_matches(40) or await self._scene_matches(30):
            return
        await self._press_button('X', duration=0.1)
        await asyncio.sleep(0.5)
        await self._reset_cursor()

    async def type_text(self, text: str, timeout_per_char: float = 3.0) -> None:
        normalized = text.strip().lower()
        if not normalized:
            return

        from ..xbox.stream_keepalive import StreamKeepaliveLoop

        await self.ensure_open()
        self.logger.info("小键盘输入开始，长度=%d", len(normalized))

        async with StreamKeepaliveLoop(self._stream_session):
            await self._type_text_inner(normalized, timeout_per_char)

    async def _type_text_inner(self, normalized: str, timeout_per_char: float) -> None:
        from ..xbox.stream_keepalive import send_keepalive

        for idx, ch in enumerate(normalized):
            if idx > 0 and idx % 5 == 0 and self._stream_session is not None:
                await send_keepalive(self._stream_session)
            if ch not in CHAR_TO_SCENE:
                raise ValueError(f"小键盘暂不支持字符: {ch!r}")

            deadline = time.time() + timeout_per_char
            target_scene = CHAR_TO_SCENE[ch]

            if ch == '@':
                await self._switch_symbols_page()
                if not await self._nudge_until(target_scene, deadline):
                    raise RuntimeError("小键盘无法定位字符 '@'")
            else:
                await self._move_to_char(ch)
                if not await self._scene_matches(target_scene):
                    await self._nudge_until(target_scene, deadline)

            await self._press_button('A', duration=0.08)
            await asyncio.sleep(0.22)
            try:
                self._cursor = _grid_pos(ch)
            except KeyError:
                pass

            from ..xbox.stream_keepalive import send_keepalive
            if self._stream_session is not None:
                await send_keepalive(self._stream_session)

        self.logger.info("小键盘输入完成")

    async def press_dot_com(self) -> None:
        await self._move_to_char('m')
        for _ in range(3):
            await self._press_button('DPAD_RIGHT', duration=0.06)
        await asyncio.sleep(0.15)
        if await self._scene_matches(16):
            await self._press_button('A', duration=0.08)

    async def _switch_symbols_page(self) -> None:
        """按 LT（#+=）切换到符号页。"""
        await self._reset_cursor()
        for _ in range(2):
            await self._press_button('DPAD_UP', duration=0.07)
            await asyncio.sleep(0.1)
        for _ in range(2):
            await self._press_button('DPAD_LEFT', duration=0.07)
            await asyncio.sleep(0.1)
        if await self._scene_matches(11):
            await self._press_button('A', duration=0.08)
        else:
            await self._nudge_until(11, time.time() + 4.0)
            await self._press_button('A', duration=0.08)
        await asyncio.sleep(0.35)
        self._cursor = (0, 0)

    async def _reset_cursor(self) -> None:
        for _ in range(5):
            await self._press_button('DPAD_UP', duration=0.06)
            await asyncio.sleep(0.08)
        for _ in range(12):
            await self._press_button('DPAD_LEFT', duration=0.06)
            await asyncio.sleep(0.06)
        self._cursor = (0, 0)
        await asyncio.sleep(0.15)

    async def _move_to_char(self, ch: str) -> None:
        target = _grid_pos(ch)
        current = self._cursor
        row_delta = target[0] - current[0]
        col_delta = target[1] - current[1]

        vertical = 'DPAD_DOWN' if row_delta > 0 else 'DPAD_UP'
        horizontal = 'DPAD_RIGHT' if col_delta > 0 else 'DPAD_LEFT'

        for _ in range(abs(row_delta)):
            await self._press_button(vertical, duration=0.07)
            await asyncio.sleep(0.12)
        for _ in range(abs(col_delta)):
            await self._press_button(horizontal, duration=0.07)
            await asyncio.sleep(0.12)

        self._cursor = target

    async def _nudge_until(self, target_scene: int, deadline: float) -> bool:
        directions = ('DPAD_RIGHT', 'DPAD_DOWN', 'DPAD_LEFT', 'DPAD_UP')
        step = 0
        while time.time() < deadline:
            if await self._scene_matches(target_scene):
                return True
            await self._press_button(directions[step % len(directions)], duration=0.06)
            await asyncio.sleep(0.12)
            step += 1
        return await self._scene_matches(target_scene)

    async def _scene_matches(self, scene_id: int) -> bool:
        if not self._scene_detector or not self._frame_getter:
            return True
        frame = await self._frame_getter()
        if frame is None:
            return False
        image = frame.data if hasattr(frame, 'data') else frame
        result = self._scene_detector.recognize_scene(
            image, scene_id=scene_id, threshold=self._threshold
        )
        return result.matched

    async def _press_button(self, button: str, duration: float = 0.08) -> None:
        if not self._executor:
            return
        await self._executor.execute(
            Action(
                type=ActionType.PRESS_BUTTON,
                params={'button': button, 'duration': duration},
                description=f"Keyboard {button}",
                timeout=2.0,
            )
        )
