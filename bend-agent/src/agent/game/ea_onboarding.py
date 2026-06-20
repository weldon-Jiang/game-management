"""
EA / FC 首登引导
================

对齐 ttt/test_xsrp.py 的 enter_the_game()：EA 绑定、国家/联赛/俱乐部选择、
新手引导直至 UT 主菜单（127/147/149 等）。

在 launch_fc_to_ut_menu 未能直接进入 UT 时由 AccountSwitcher 调用。
"""

from __future__ import annotations

import asyncio
import random
import time
from typing import Callable, List, Optional, Set, TYPE_CHECKING

from ..core.logger import get_logger
from .fc_on_screen_keyboard import FcOnScreenKeyboard

if TYPE_CHECKING:
    from .account_switcher import AccountSwitcher

# 引导完成：进入 UT 或 ttt 退出点
EA_UT_COMPLETE_SCENES: Set[int] = {101, 126, 127, 147, 149, 251, 252}

# ttt enter_the_game 批识别候选（需 templates 同步后命中率更高）
EA_ONBOARDING_CANDIDATES: List[int] = sorted(
    {
        1,
        99,
        101,
        103,
        104,
        105,
        106,
        107,
        108,
        109,
        110,
        111,
        112,
        113,
        114,
        115,
        116,
        124,
        127,
        129,
        131,
        136,
        141,
        142,
        143,
        144,
        145,
        146,
        147,
        149,
        217,
        219,
        220,
        221,
        222,
        223,
        225,
        226,
        227,
        228,
        229,
        230,
        231,
        232,
        234,
        241,
        242,
        243,
        244,
        245,
        246,
        247,
        248,
        249,
        250,
        251,
        252,
        254,
    }
)

# 仅按 A 继续的场景集合（ttt 中大量分支）
EA_PRESS_A_SCENES: Set[int] = {
    103,
    104,
    105,
    106,
    107,
    108,
    109,
    110,
    111,
    112,
    113,
    114,
    115,
    116,
    129,
    219,
    220,
    221,
    222,
    223,
    228,
    231,
    234,
    243,
    244,
    245,
    246,
    249,
    144,
    145,
    250,
    124,
    254,
}


async def _fc_stay_in_touch(switcher: "AccountSwitcher", logger) -> None:
    """scene 242 fc保持联系：ttt 连按两次 A（241 后常见，不依赖 242.1 模板）。"""
    await switcher._press_button("A", duration=0.1)
    await asyncio.sleep(1.0)
    await switcher._press_button("A", duration=0.1)
    logger.info("fc保持联系：已执行双 A（scene 242 动作）")


class EaOnboardingRunner:
    """EA/FC 首登场景循环（ttt enter_the_game 移植）。"""

    def __init__(self, switcher: "AccountSwitcher"):
        self._sw = switcher
        self.logger = get_logger("ea_onboarding")
        self._ea_account_typed = False
        self._scene1_nav_done = False

    async def run(
        self,
        ea_email: str,
        *,
        timeout: float = 900.0,
        check_cancel: Optional[Callable[[], bool]] = None,
    ) -> bool:
        if not self._sw._scene_detector or not self._sw._frame_getter:
            self.logger.warning("EA 引导跳过：未绑定场景检测器或截帧")
            return False

        from ..xbox.stream_keepalive import StreamKeepaliveLoop

        deadline = time.monotonic() + timeout
        self.logger.info("开始 EA/FC 首登引导 (timeout=%ss)", int(timeout))

        async with StreamKeepaliveLoop(lambda: self._sw._stream_session):
            while time.monotonic() < deadline:
                if check_cancel and check_cancel():
                    self.logger.info("EA 引导被取消")
                    return False

                scene_id = await self._sw._detect_any_scene(
                    EA_ONBOARDING_CANDIDATES,
                    strict=False,
                )
                if scene_id is None:
                    await asyncio.sleep(0.5)
                    continue

                if scene_id in EA_UT_COMPLETE_SCENES:
                    self.logger.info("EA 引导完成，当前场景 %s", scene_id)
                    return True

                handled = await self._handle_scene(scene_id, ea_email)
                if not handled:
                    self.logger.debug("场景 %s 暂无专用处理，尝试 A", scene_id)
                    await self._sw._press_button("A", duration=0.1)
                await asyncio.sleep(0.45)

        self.logger.warning("EA 引导超时 (%ss)", int(timeout))
        hit = await self._sw._detect_any_scene(
            list(EA_UT_COMPLETE_SCENES),
            strict=False,
        )
        return hit in EA_UT_COMPLETE_SCENES

    async def _handle_scene(self, scene_id: int, ea_email: str) -> bool:
        sw = self._sw

        if scene_id == 1 and not self._scene1_nav_done:
            await sw._press_button("DPAD_RIGHT", duration=0.1)
            await asyncio.sleep(0.3)
            await sw._press_button("A", duration=0.1)
            for _ in range(20):
                sub = await sw._detect_any_scene([217, 99], strict=False)
                if sub in (217, 99):
                    await sw._press_button("A", duration=0.1)
                    self._scene1_nav_done = True
                    return True
                await sw._press_button("DPAD_RIGHT", duration=0.1)
                await asyncio.sleep(0.4)
            return True

        if scene_id == 230 and ea_email and not self._ea_account_typed:
            await asyncio.sleep(0.3)
            await sw._press_button("A", duration=0.1)
            await asyncio.sleep(0.3)
            for _ in range(30):
                await sw._press_button("X", duration=0.1)
                await asyncio.sleep(0.25)
            keyboard = FcOnScreenKeyboard(sw)
            await keyboard.type_text(ea_email)
            await asyncio.sleep(0.5)
            await sw._press_button("DPAD_DOWN", duration=0.1)
            await asyncio.sleep(0.4)
            await sw._press_button("A", duration=0.1)
            self._ea_account_typed = True
            return True

        if scene_id == 232:
            await sw._press_button("B", duration=0.1)
            return True

        if scene_id == 229:
            return True

        if scene_id in (225, 226, 227):
            await self._random_grid_select(max_x=29 if scene_id == 225 else (2 if scene_id == 226 else 20))
            return True

        if scene_id == 131 or scene_id in (141, 142, 143):
            await self._random_grid_select(max_x=3, max_y=3)
            return True

        if scene_id == 248:
            await self._random_grid_select(max_x=5, max_y=1)
            return True

        if scene_id in (247, 136):
            await sw._press_button("DPAD_UP", duration=0.1)
            await asyncio.sleep(0.4)
            await sw._press_button("A", duration=0.1)
            return True

        if scene_id == 241:
            await sw._press_button("DPAD_DOWN", duration=0.1)
            await asyncio.sleep(0.8)
            await sw._press_button("DPAD_DOWN", duration=0.1)
            await asyncio.sleep(0.8)
            await sw._press_button("A", duration=0.1)
            # 242.1 模板上游缺失：241(fc新闻) 后通常紧跟 242，主动双 A 兜底
            await asyncio.sleep(0.6)
            await _fc_stay_in_touch(sw, self.logger)
            return True

        if scene_id == 242:
            await _fc_stay_in_touch(sw, self.logger)
            return True

        if scene_id == 146:
            await sw._press_button("DPAD_RIGHT", duration=0.1)
            await asyncio.sleep(0.8)
            await sw._press_button("A", duration=0.1)
            return True

        if scene_id == 250:
            for _ in range(4):
                await sw._press_button("A", duration=0.1)
                await asyncio.sleep(0.45)
            return True

        if scene_id == 244:
            await sw._press_button("MENU", duration=0.1)
            return True

        if scene_id in EA_PRESS_A_SCENES:
            await sw._press_button("A", duration=0.1)
            return True

        return False

    async def _random_grid_select(
        self,
        *,
        max_x: int,
        max_y: int = 1,
    ) -> None:
        sw = self._sw
        x = random.randrange(0, max_x + 1)
        y = random.randrange(0, max_y + 1) if max_y > 0 else 0
        for _ in range(x):
            await sw._press_button("DPAD_RIGHT", duration=0.1)
            await asyncio.sleep(0.25)
        for _ in range(y):
            await sw._press_button("DPAD_DOWN", duration=0.1)
            await asyncio.sleep(0.25)
        await sw._press_button("A", duration=0.1)
        await asyncio.sleep(0.8)


async def run_ea_onboarding(
    switcher: "AccountSwitcher",
    *,
    ea_email: str = "",
    timeout: float = 900.0,
    check_cancel: Optional[Callable[[], bool]] = None,
) -> bool:
    """对外入口：运行 EA/FC 首登直至 UT 场景或超时。"""
    runner = EaOnboardingRunner(switcher)
    return await runner.run(ea_email, timeout=timeout, check_cancel=check_cancel)
