#!/usr/bin/env python3
"""
Sync scene_transitions.py from streaming/xsrpst.py get_scenes_diagram().

Usage:
    python tools/sync_scene_transitions.py
    python tools/sync_scene_transitions.py --dry-run

Merges bend-agent-only transitions (account switch) and fixes streaming
duplicate transition_id issues for scenes 1 and 177.
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
STREAMING_ROOT = ROOT.parent.parent / "streaming"
if not STREAMING_ROOT.exists():
    STREAMING_ROOT = Path(r"D:\auto-xbox\streaming")

XSRPST = STREAMING_ROOT / "xsrpst.py"
TRANSITION_OUT = ROOT / "configs" / "scene_transitions.py"

# 修正 streaming 重复 transition_id 后的描述
DESCRIPTION_OVERRIDES: Dict[Tuple[int, int], str] = {
    (1, 2): "西瓜主页界面 - 关机",
}

# bend-agent 独有转移（streaming get_scenes_diagram 中不存在）
AGENT_TRANSITION_EXTENSIONS: List[dict] = [
    {
        "scene_id": 2,
        "transition_id": 2,
        "description": "西瓜引导页进入档案和系统",
        "controller_options": [
            [50, 5, 512, 0, 0, 0, 0, 0, 0],
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        "target_scenes": [3],
    },
    {
        "scene_id": 3,
        "transition_id": 1,
        "description": "档案和系统选中添加和切换",
        "controller_options": [[50, 1, 16, 0, 0, 0, 0, 0, 0]],
        "target_scenes": [5],
    },
    {
        "scene_id": 5,
        "transition_id": 1,
        "description": "添加和切换进入账号选择",
        "controller_options": [[50, 1, 16, 0, 0, 0, 0, 0, 0]],
        "target_scenes": [6],
    },
    {
        "scene_id": 147,
        "transition_id": 2,
        "description": "UT主菜单 -> 转会Tab（152）",
        "controller_options": [
            [50, 1, 4096, 0, 255, 0, 0, 0, 0],
            [50, 2, 4096, 0, 255, 0, 0, 0, 0],
            [50, 3, 4096, 0, 255, 0, 0, 0, 0],
        ],
        "target_scenes": [152],
    },
    {
        "scene_id": 149,
        "transition_id": 2,
        "description": "UT开始游戏Tab -> 转会Tab（152）",
        "controller_options": [
            [50, 1, 4096, 0, 255, 0, 0, 0, 0],
            [50, 2, 4096, 0, 255, 0, 0, 0, 0],
            [50, 3, 4096, 0, 255, 0, 0, 0, 0],
        ],
        "target_scenes": [152],
    },
]


def _strip_comments(text: str) -> str:
    lines = []
    for line in text.splitlines():
        lines.append(line.split("#", 1)[0])
    return "\n".join(lines)


def _extract_diagrams_from_xsrpst() -> List[list]:
    content = XSRPST.read_text(encoding="utf-8")
    start = content.find("def get_scenes_diagram")
    end = content.find("def get_template_token", start)
    if start < 0 or end < 0:
        raise RuntimeError("get_scenes_diagram() block not found in xsrpst.py")

    block = content[start:end]
    diagrams: List[list] = []
    marker = "diagram = ["
    pos = 0
    # Skip the illustrative diagram inside the opening docstring
    first_doc = block.find("'''")
    if first_doc >= 0:
        second_doc = block.find("'''", first_doc + 3)
        if second_doc >= 0:
            pos = second_doc + 3

    while True:
        idx = block.find(marker, pos)
        if idx < 0:
            break
        arr_start = idx + len("diagram = ")
        depth = 0
        i = arr_start
        while i < len(block):
            ch = block[i]
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    raw = _strip_comments(block[arr_start : i + 1])
                    try:
                        diagram = ast.literal_eval(raw)
                    except (SyntaxError, ValueError) as exc:
                        raise RuntimeError(f"Failed to parse diagram at {idx}: {exc}") from exc
                    if not isinstance(diagram, list) or len(diagram) != 4:
                        raise RuntimeError(f"Unexpected diagram shape: {diagram!r}")
                    diagrams.append(diagram)
                    pos = i + 1
                    break
            i += 1
        else:
            break

    if not diagrams:
        raise RuntimeError("No diagrams extracted from get_scenes_diagram()")
    return diagrams


def _diagram_to_dict(diagram: list, description: str = "") -> dict:
    scene_id, transition_id, controller_options, target_scenes = diagram
    return {
        "scene_id": int(scene_id),
        "transition_id": int(transition_id),
        "description": description,
        "controller_options": [list(map(int, opt)) for opt in controller_options],
        "target_scenes": [int(x) for x in target_scenes],
    }


def _extract_descriptions(existing_text: str) -> Dict[Tuple[int, int], str]:
    """Preserve human descriptions keyed by (scene_id, transition_id)."""
    descriptions: Dict[Tuple[int, int], str] = {}
    for match in re.finditer(
        r"\{\s*'scene_id':\s*(\d+),\s*'transition_id':\s*(\d+),\s*"
        r"'description':\s*\"((?:\\.|[^\"])*)\"",
        existing_text,
    ):
        key = (int(match.group(1)), int(match.group(2)))
        descriptions[key] = match.group(3)
    return descriptions


def _apply_transition_id_fixes(transitions: List[dict]) -> List[dict]:
    """Fix streaming duplicate transition_id for scenes 1 and 177."""
    fixed: List[dict] = []

    for item in transitions:
        scene_id = item["scene_id"]
        transition_id = item["transition_id"]
        opts = item["controller_options"]
        targets = item["target_scenes"]

        if scene_id == 1 and transition_id == 1:
            duration = opts[0][0] if opts else 0
            if duration >= 1000 and 7 in targets:
                item = {**item, "transition_id": 2}

        if scene_id == 177 and transition_id == 1 and 183 in targets:
            item = {**item, "transition_id": 2}

        fixed.append(item)

    return fixed


def _merge_agent_extensions(transitions: List[dict]) -> List[dict]:
    keys = {(t["scene_id"], t["transition_id"]) for t in transitions}
    merged = list(transitions)
    for ext in AGENT_TRANSITION_EXTENSIONS:
        key = (ext["scene_id"], ext["transition_id"])
        if key not in keys:
            merged.append(ext)
            keys.add(key)
    return merged


def _comment_from_diagram(diagram: list) -> str:
    """Best-effort description from xsrpst inline comments (not available after ast)."""
    scene_id, _, _, targets = diagram
    target = targets[0] if targets else "?"
    return f"场景{scene_id} -> 场景{target}"


def build_transitions(existing_path: Optional[Path] = None) -> List[dict]:
    diagrams = _extract_diagrams_from_xsrpst()
    descriptions: Dict[Tuple[int, int], str] = {}
    if existing_path and existing_path.exists():
        descriptions = _extract_descriptions(existing_path.read_text(encoding="utf-8"))

    transitions = []
    for diagram in diagrams:
        item = _diagram_to_dict(diagram)
        key = (item["scene_id"], item["transition_id"])
        item["description"] = descriptions.get(key) or _comment_from_diagram(diagram)
        transitions.append(item)

    transitions = _apply_transition_id_fixes(transitions)
    for item in transitions:
        key = (item["scene_id"], item["transition_id"])
        if key in DESCRIPTION_OVERRIDES:
            item["description"] = DESCRIPTION_OVERRIDES[key]
    transitions = _merge_agent_extensions(transitions)
    transitions.sort(key=lambda t: (t["scene_id"], t["transition_id"]))
    return transitions


def _format_transition(item: dict) -> str:
    lines = [
        "    {",
        f"        'scene_id': {item['scene_id']},",
        f"        'transition_id': {item['transition_id']},",
        f"        'description': {_repr_str(item['description'])},",
        "        'controller_options': [",
    ]
    for opt in item["controller_options"]:
        lines.append(f"            {opt},")
    lines.append("        ],")
    targets = ", ".join(str(x) for x in item["target_scenes"])
    lines.append(f"        'target_scenes': [{targets}]")
    lines.append("    },")
    return "\n".join(lines)


def _repr_str(value: str) -> str:
    return repr(value)


def _write_scene_transitions(transitions: List[dict]) -> str:
    header = '''"""
场景转移配置
============

本配置文件由 tools/sync_scene_transitions.py 从 streaming/xsrpst.py 同步生成，
并合并 bend-agent 账号切换扩展转移。

配置结构：
[
    {
        'scene_id': 场景ID,
        'transition_id': 转移ID,
        'description': 描述,
        'controller_options': [
            [duration_ms, count, buttons, left_trigger, right_trigger, left_thumb_x, left_thumb_y, right_thumb_x, right_thumb_y],
            ...
        ],
        'target_scenes': [目标场景ID列表]
    },
    ...
]

作者：技术团队
版本：1.1（sync 生成）
"""

from typing import Dict, List, Optional, Tuple

SCENE_TRANSITIONS = [
'''
    body_parts = []
    current_scene = None
    for item in transitions:
        if item["scene_id"] != current_scene:
            if current_scene is not None:
                body_parts.append("")
            body_parts.append(f"    # 场景{item['scene_id']}")
            current_scene = item["scene_id"]
        body_parts.append(_format_transition(item))

    footer = '''
]

# SQB 导航链（UT 主菜单 → Squad Battles → 对手 → 难度 → 开赛）
SQB_UT_MENU_CHAIN: List[Tuple[int, int]] = [
    (147, 1),
    (149, 1),
    (155, 1),
    (156, 1),
    (168, 1),
    (177, 2),
    (183, 1),
]

SQB_OPPONENT_TRANSITIONS: Dict[int, Tuple[int, int]] = {
    168: (168, 1),
    169: (169, 1),
    170: (170, 1),
    171: (171, 1),
    172: (172, 1),
    173: (173, 1),
    174: (174, 1),
}

SQB_NAVIGATION_SCENES = [
    127, 147, 149, 155, 156,
    *range(168, 176),
    177, 183, 189,
]

SQB_COMPLETE_SCENES = {189}

# SQB 189 开赛后 → 进入场中
SQB_PREMATCH_TARGETS = [102, 190]
SQB_PREMATCH_PROBE_SCENES = [
    189, 190, 102,
    127, 147, 149, 155, 156,
    *range(168, 176),
    177, 183,
    184, 185, 186, 187, 188, 193, 194,
]
SQB_PREMATCH_DISMISS_TIMEOUT = 90.0

# 「按住 A 跳过」类过场/庆祝
HOLD_A_SKIP_SCENE_IDS = frozenset({101, 102, 189, 190})
DISMISS_A_TAP_SEC = 0.12
HOLD_A_SKIP_PRESS_SEC = 2.0
DISMISS_HOLD_A_UNMATCHED_LABELS = frozenset({"SQB-PREMATCH"})


def resolve_automation_a_press_sec(
    scene_id: Optional[int],
    *,
    force_hold: bool = False,
) -> float:
    """自动化按 A 时长：过场/庆祝 scene 用长按，普通弹窗用短按。"""
    hold = HOLD_A_SKIP_PRESS_SEC
    tap = DISMISS_A_TAP_SEC
    try:
        from agent.core.config import config as app_config

        hold = float(app_config.get("step4.hold_a_skip_sec", hold))
        tap = float(app_config.get("step4.dismiss_a_tap_sec", tap))
    except Exception:
        pass
    if force_hold:
        return hold
    if scene_id is not None and int(scene_id) in HOLD_A_SKIP_SCENE_IDS:
        return hold
    return tap


# 转会导航链
AUCTION_UT_CHAIN: List[Tuple[int, int]] = [
    (147, 2),
]

AUCTION_NAVIGATION_SCENES = [
    127, 147, 149, 150, 151, 152, 153, 154,
]

AUCTION_COMPLETE_SCENES = {152}

AUCTION_ENTRY_DWELL_SEC = 3.0
AUCTION_EXIT_DISMISS_TIMEOUT = 45.0


def trim_auction_navigation_chain(
    current_scene: Optional[int],
) -> List[Tuple[int, int]]:
    """根据当前 scene 裁剪转会导航链。"""
    if current_scene in AUCTION_COMPLETE_SCENES:
        return []

    if current_scene == 149:
        return [(149, 2)]
    if current_scene == 147:
        return list(AUCTION_UT_CHAIN)
    if current_scene == 127:
        return [(127, 1), (147, 2)]

    return [(127, 1), (147, 2)]


def get_transition(scene_id: int, transition_id: int) -> Optional[dict]:
    """按 scene_id + transition_id 查找单条转移配置。"""
    for item in SCENE_TRANSITIONS:
        if item['scene_id'] == scene_id and item['transition_id'] == transition_id:
            return item
    return None


def trim_sqb_navigation_chain(current_scene: Optional[int]) -> List[Tuple[int, int]]:
    """根据当前 scene 裁剪 SQB 链。"""
    if current_scene in SQB_COMPLETE_SCENES:
        return []

    suffix: List[Tuple[int, int]] = [(177, 2), (183, 1)]

    if current_scene == 183:
        return [(183, 1)]
    if current_scene == 177:
        return list(suffix)
    if current_scene in SQB_OPPONENT_TRANSITIONS:
        return [SQB_OPPONENT_TRANSITIONS[current_scene], *suffix]
    if current_scene == 156:
        return [(156, 1), (168, 1), *suffix]
    if current_scene == 155:
        return [(155, 1), (156, 1), (168, 1), *suffix]
    if current_scene == 149:
        return [(149, 1), (155, 1), (156, 1), (168, 1), *suffix]
    if current_scene == 147:
        return list(SQB_UT_MENU_CHAIN)

    return list(SQB_UT_MENU_CHAIN)


def get_transitions_by_scene(scene_id: int):
    """获取指定场景的所有转移配置"""
    return [t for t in SCENE_TRANSITIONS if t['scene_id'] == scene_id]


def get_all_scene_ids():
    """获取所有场景ID"""
    return list({t['scene_id'] for t in SCENE_TRANSITIONS})
'''
    return header + "\n".join(body_parts) + footer


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync scene_transitions from xsrpst.py")
    parser.add_argument("--dry-run", action="store_true", help="Print summary only")
    args = parser.parse_args()

    if not XSRPST.exists():
        print(f"xsrpst.py not found: {XSRPST}", file=sys.stderr)
        return 1

    transitions = build_transitions(TRANSITION_OUT if TRANSITION_OUT.exists() else None)
    text = _write_scene_transitions(transitions)

    if args.dry_run:
        print(f"Would write {len(transitions)} transitions to {TRANSITION_OUT}")
        for item in transitions:
            print(
                f"  {item['scene_id']}/{item['transition_id']} -> {item['target_scenes']} "
                f"({item['description'][:40]})"
            )
        return 0

    TRANSITION_OUT.write_text(text, encoding="utf-8")
    print(f"Wrote {len(transitions)} transitions to {TRANSITION_OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
