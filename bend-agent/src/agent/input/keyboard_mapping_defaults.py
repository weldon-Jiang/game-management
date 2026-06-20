"""
平台默认键盘→手柄映射（与 bend-platform AgentKeyboardMappingDefaults 一致）。
"""

from typing import Dict

# WASD → 左摇杆；方向键 → 十字键（菜单/战术），与平台 12 项映射并存
DEFAULT_KEYBOARD_BINDINGS: Dict[str, str] = {
    "w": "MOVE_UP",
    "s": "MOVE_DOWN",
    "a": "MOVE_LEFT",
    "d": "MOVE_RIGHT",
    "up": "MOVE_UP",
    "down": "MOVE_DOWN",
    "left": "MOVE_LEFT",
    "right": "MOVE_RIGHT",
    "j": "TAP_X",
    "k": "TAP_A",
    "l": "TAP_B",
    "i": "TAP_Y",
    "return": "TAP_START",
    "escape": "TAP_SELECT",
    "q": "TAP_L1",
    "e": "TAP_R1",
    "left ctrl": "TAP_NEXUS",
    "left shift": "HOLD_L2",
    "space": "HOLD_R2",
    "c": "TAP_L3",
    "v": "TAP_R3",
    "t": "LOOK_UP",
    "g": "LOOK_DOWN",
    "f": "LOOK_LEFT",
    "h": "LOOK_RIGHT",
}
