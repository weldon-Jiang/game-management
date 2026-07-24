"""
Step4 场中自动化 — 场景感知 + 左摇杆/面键占位，直到检测到比赛结束。

优先级：
1. 识别到庆祝等需长按 A 的 scene → sustained A
2. 否则周期性左摇杆方向 + A/Y/B（占位，待 FootballController 全量接入）

生产环境可改用 FC remote play（StreamRuntime play 20Hz）。
"""

from __future__ import annotations

import asyncio
import time
from typing import Awaitable, Callable, List, Optional, Tuple

from ...input.controller_protocol import ControllerProtocol, ControllerSignal, XboxButtonFlag

# 左摇杆四方向（int16 量级，对齐 xCloud）
_STICK_DIRS: List[Tuple[int, int]] = [
    (0, -22000),
    (22000, 0),
    (0, 22000),
    (-22000, 0),
]

_ACTION_BUTTONS = (
    XboxButtonFlag.A,
    XboxButtonFlag.Y,
    XboxButtonFlag.B,
)

# 场中轮询 scene（100 开球、101 庆祝、102 场中等）
_IN_MATCH_PROBE_SCENES = [100, 101, 102, 103, 104, 105, 108]

# 需优先长按 A 处理的 scene（与 scene_transitions.HOLD_A_SKIP_SCENE_IDS 对齐的子集）
_IN_MATCH_HOLD_A_SCENES = frozenset({101})

_DEFAULT_STICK_HOLD_SEC = 0.45
_DEFAULT_BUTTON_HOLD_SEC = 0.25
_DEFAULT_TICK_INTERVAL_SEC = 0.85
_PROGRESS_EVERY_TICKS = 35


def _in_match_timing() -> Tuple[float, float, float]:
    try:
        from ...core.config import config as app_config

        stick = float(
            app_config.get("step4.in_match_stick_hold_sec", _DEFAULT_STICK_HOLD_SEC)
        )
        btn = float(
            app_config.get("step4.in_match_button_hold_sec", _DEFAULT_BUTTON_HOLD_SEC)
        )
        interval = float(
            app_config.get("step4.in_match_tick_interval_sec", _DEFAULT_TICK_INTERVAL_SEC)
        )
        return stick, btn, interval
    except Exception:
        return _DEFAULT_STICK_HOLD_SEC, _DEFAULT_BUTTON_HOLD_SEC, _DEFAULT_TICK_INTERVAL_SEC


async def _try_scene_hold_a(
    context,
    protocol: ControllerProtocol,
    task_logger,
) -> bool:
    """
    场中 scene 101 等：发 sustained A 跳过庆祝/过场。

    返回 True 表示本 tick 已处理，跳过占位输入。
    """
    switcher = getattr(context, "_account_switcher", None)
    if switcher is None:
        return False

    try:
        scene_id = await switcher._detect_any_scene(
            list(_IN_MATCH_PROBE_SCENES),
            strict=False,
        )
    except Exception as exc:
        task_logger.debug("场中 scene 探针失败: %s", exc)
        return False

    if scene_id not in _IN_MATCH_HOLD_A_SCENES:
        return False

    from configs.scene_transitions import resolve_automation_a_press_sec

    duration = resolve_automation_a_press_sec(scene_id)
    task_logger.info("场中 scene=%s：长按 A %.1fs", scene_id, duration)
    try:
        await protocol.press_button(XboxButtonFlag.A, duration)
    except Exception as exc:
        task_logger.debug("场中长按 A 失败: %s", exc)
    return True


async def _send_placeholder_tick(
    protocol: ControllerProtocol,
    tick: int,
    *,
    stick_hold_sec: float,
    button_hold_sec: float,
) -> None:
    """占位：左摇杆一个方向 + 面键，各 hold 后 zero。"""
    lx, ly = _STICK_DIRS[tick % len(_STICK_DIRS)]
    btn = _ACTION_BUTTONS[(tick // len(_STICK_DIRS)) % len(_ACTION_BUTTONS)]
    active = ControllerSignal(left_thumb_x=lx, left_thumb_y=ly)
    active.set_button(btn, True)
    await protocol.send_signal(active)
    hold = max(stick_hold_sec, button_hold_sec)
    await asyncio.sleep(hold)
    await protocol.send_signal(ControllerSignal.zero())


async def run_local_in_match_loop(
    context,
    task_logger,
    check_cancel: Callable[[], bool],
    detect_match_ended: Callable[[], Awaitable[bool]],
    *,
    match_duration: float = 1200.0,
    on_progress: Optional[Callable[[int, int], Awaitable[None]]] = None,
) -> None:
    """
    场中自动化循环：scene 感知长按 A + 周期性摇杆/面键占位，检测到终场即退出。
    """
    protocol: Optional[ControllerProtocol] = getattr(context, "_controller_protocol", None)
    deadline = time.monotonic() + match_duration
    tick = 0
    start = time.monotonic()
    stick_hold, button_hold, tick_interval = _in_match_timing()

    if protocol is None:
        task_logger.warning("无 controller_protocol，比赛阶段仅等待结束检测")
        while time.monotonic() < deadline:
            if check_cancel():
                raise RuntimeError("比赛被取消")
            if getattr(context, "is_paused", lambda: False)():
                await context.wait_if_paused()
                from ...runtime.pause_input_control import raise_if_resume_reanchor

                raise_if_resume_reanchor(context)
            if await detect_match_ended():
                return
            await asyncio.sleep(5.0)
        return

    task_logger.info(
        "场中自动化已启动 (stick_hold=%.2fs, btn_hold=%.2fs, tick=%.2fs, max=%ds)",
        stick_hold,
        button_hold,
        tick_interval,
        int(match_duration),
    )

    while time.monotonic() < deadline:
        if check_cancel():
            raise RuntimeError("比赛被取消")
        if getattr(context, "_manual_takeover", False):
            await asyncio.sleep(tick_interval)
            tick += 1
            continue
        if getattr(context, "is_paused", lambda: False)():
            await context.wait_if_paused()
            from ...runtime.pause_input_control import raise_if_resume_reanchor

            raise_if_resume_reanchor(context)
        if await detect_match_ended():
            task_logger.info("场中自动化：检测到比赛结束，停止发键")
            return

        handled = False
        if tick % 2 == 0:
            try:
                handled = await _try_scene_hold_a(context, protocol, task_logger)
            except Exception as exc:
                task_logger.debug("场中 scene 动作异常: %s", exc)

        if not handled:
            try:
                await _send_placeholder_tick(
                    protocol,
                    tick,
                    stick_hold_sec=stick_hold,
                    button_hold_sec=button_hold,
                )
            except Exception as exc:
                task_logger.debug("场中占位输入异常: %s", exc)

        tick += 1
        if on_progress and tick % _PROGRESS_EVERY_TICKS == 0:
            elapsed = int(time.monotonic() - start)
            try:
                await on_progress(elapsed, int(match_duration))
            except Exception as exc:
                task_logger.debug("比赛进度回调异常: %s", exc)

        await asyncio.sleep(tick_interval)

    task_logger.info("场中自动化达到最长时长 %ds", int(match_duration))
