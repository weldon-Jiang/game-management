"""
平台默认键盘→手柄映射（与 bend-platform AgentKeyboardMappingDefaults 一致）。
"""

from typing import Dict

DEFAULT_KEYBOARD_BINDINGS: Dict[str, str] = {
    "w": "MOVE_UP",
    "s": "MOVE_DOWN",
    "a": "MOVE_LEFT",
    "d": "MOVE_RIGHT",
    "j": "TAP_A",
    "b": "TAP_B",
    "x": "TAP_X",
    "y": "TAP_Y",
    "return": "TAP_START",
    "escape": "TAP_SELECT",
    "q": "TAP_L1",
    "e": "TAP_R1",
}
