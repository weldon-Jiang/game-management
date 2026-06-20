"""
F8 人工接管 — 输入整形。

- 键盘 WASD/方向键：非比赛场景 → DPad 短按/长按连滚；比赛中场景 → 左摇杆持续。
- 物理手柄 DPad：短按一格 + 长按连滚（菜单）。
- 面键 A/B/X/Y：仅比赛中场景可长按；菜单短按（由 KeyboardMapper 控制）。
"""

from __future__ import annotations

import time
from typing import Any, Dict, FrozenSet, Optional, Set

from ..core.config import config as app_config
from .controller_protocol import ControllerSignal, XboxButtonFlag

_STICK_AXIS_THRESHOLD = 0.45
_STICK_VALUE_THRESHOLD = int(_STICK_AXIS_THRESHOLD * 32767)

# 人工输入视为「比赛中」的场景（左摇杆 + 面键长按）；随实机补录可扩展
MANUAL_IN_MATCH_SCENE_IDS: FrozenSet[int] = frozenset({102, 190})

# 明确 UT/菜单场景：即使 auto_play 仍为 True 也不启用比赛输入模式
UT_MENU_SCENE_IDS_FOR_INPUT: FrozenSet[int] = frozenset({101, 126, 127, 147, 149})

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

# 场中须剥离的系统键（NEXUS 已绑 Ctrl，用户 intentional 触发）
_IN_MATCH_STRIP_BUTTONS = int(
    XboxButtonFlag.MENU
    | XboxButtonFlag.VIEW
)

_IN_MATCH_ALLOWED_BUTTONS = int(
    XboxButtonFlag.NEXUS
    | XboxButtonFlag.A
    | XboxButtonFlag.B
    | XboxButtonFlag.X
    | XboxButtonFlag.Y
    | XboxButtonFlag.L1
    | XboxButtonFlag.R1
    | XboxButtonFlag.L3
    | XboxButtonFlag.R3
    | _NAV_MASK
)


def update_last_streaming_scene_id(context: Any, scene_id: Optional[int]) -> None:
    """写入最近一次 Streaming 场景 ID，供 KeyboardMapper 判定比赛内输入。"""
    if context is None or scene_id is None:
        return
    try:
        sid = int(scene_id)
    except (TypeError, ValueError):
        return
    if sid <= 0:
        return
    context._last_streaming_scene_id = sid


def get_last_streaming_scene_id(context: Any) -> Optional[int]:
    sid = getattr(context, "_last_streaming_scene_id", None)
    if sid is None:
        return None
    try:
        parsed = int(sid)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def is_manual_in_match(context: Any = None) -> bool:
    """
    是否处于「比赛中」人工输入模式（左摇杆 + 面键长按）。

    判定（任一满足）：
    1. StreamRuntime.auto_play（场中 play 20Hz）
    2. context._step4_in_match_active（比赛 loop 进行中，含平台暂停释键后）
    3. 最近识别 scene ∈ MANUAL_IN_MATCH_SCENE_IDS（如 102 开场、190 继续）

    不再用「缓存 UT 菜单 scene」否定 auto_play：场中 HUD 常无法匹配模板，
    _last_streaming_scene_id 会长期停留在 127 等菜单 ID，导致 WASD 误走 DPad。
    """
    if context is None:
        return False

    runtime = getattr(context, "_stream_runtime", None)
    if runtime is not None and getattr(runtime, "auto_play", False):
        return True

    if getattr(context, "_step4_in_match_active", False):
        return True

    last = get_last_streaming_scene_id(context)
    if last is not None and last in MANUAL_IN_MATCH_SCENE_IDS:
        return True

    return False


def is_manual_face_a_hold_allowed(context: Any = None) -> bool:
    """
    F8 下 K（TAP_A）是否允许 sustained 长按。

    - 比赛中（is_manual_in_match）始终允许
    - Step4 自动化进行中且非 UT 菜单：允许（覆盖赛前过场「按住 A 跳过」）
    """
    if is_manual_in_match(context):
        return True
    if context is None:
        return False
    last = get_last_streaming_scene_id(context)
    if last is not None and last in UT_MENU_SCENE_IDS_FOR_INPUT:
        return False
    runtime = getattr(context, "_stream_runtime", None)
    if runtime is None:
        return False
    if getattr(runtime, "auto_graph", False) or getattr(runtime, "auto_play", False):
        return True
    return False


def wire_manual_in_match_checker(context: Any, keyboard_mapper: Any) -> None:
    """KeyboardMapper 初始化 / F8 开启时注册比赛场景判定。"""
    if keyboard_mapper is None or not hasattr(
        keyboard_mapper, "set_manual_in_match_checker"
    ):
        return
    keyboard_mapper.set_manual_in_match_checker(lambda: is_manual_in_match(context))
    if hasattr(keyboard_mapper, "set_task_context"):
        keyboard_mapper.set_task_context(context)
    if hasattr(keyboard_mapper, "set_manual_face_a_hold_checker"):
        keyboard_mapper.set_manual_face_a_hold_checker(
            lambda: is_manual_face_a_hold_allowed(context)
        )


def resolve_manual_keyboard_stick(*, in_match: bool = False) -> bool:
    """
    仅 manual_keyboard_movement=auto/stick/dpad 时使用（split 由 KeyboardMapper 硬编码）。

    - auto：比赛内 stick，非比赛 dpad
    - stick / dpad：强制固定模式（调试用）
    """
    mode = str(app_config.get("debug.manual_keyboard_movement", "split")).lower().strip()
    if mode == "stick":
        return True
    if mode == "dpad":
        return False
    return in_match


def manual_keyboard_uses_stick(*, in_match: bool = False) -> bool:
    """兼容旧调用；等价于 resolve_manual_keyboard_stick。"""
    return resolve_manual_keyboard_stick(in_match=in_match)


def sanitize_manual_match_signal(signal: ControllerSignal) -> ControllerSignal:
    """
    比赛中 F8 人工输入：仅保留左摇杆 + 面键/LB/RB，去掉系统键与十字键。

    避免 idle Nexus 脉冲、Win32 误触 Enter/Esc、菜单 DPad 脉冲导致暂停/切屏。
    """
    out = ControllerSignal(
        buttons=int(signal.buttons) & _IN_MATCH_ALLOWED_BUTTONS,
        left_trigger=signal.left_trigger,
        right_trigger=signal.right_trigger,
        left_thumb_x=signal.left_thumb_x,
        left_thumb_y=signal.left_thumb_y,
        right_thumb_x=signal.right_thumb_x,
        right_thumb_y=signal.right_thumb_y,
    )
    out.buttons = int(out.buttons) & ~_IN_MATCH_STRIP_BUTTONS
    return out


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

    def apply(
        self,
        raw: ControllerSignal,
        *,
        now: Optional[float] = None,
        in_match: bool = False,
    ) -> ControllerSignal:
        if now is None:
            now = time.monotonic()

        # 场中：摇杆 + 面键/LB/RB 直传，不做 DPad 菜单脉冲
        if in_match:
            out = ControllerSignal()
            out.left_trigger = raw.left_trigger
            out.right_trigger = raw.right_trigger
            out.left_thumb_x = raw.left_thumb_x
            out.left_thumb_y = raw.left_thumb_y
            out.right_thumb_x = raw.right_thumb_x
            out.right_thumb_y = raw.right_thumb_y
            out.buttons = int(raw.buttons) & _IN_MATCH_ALLOWED_BUTTONS
            return out

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
