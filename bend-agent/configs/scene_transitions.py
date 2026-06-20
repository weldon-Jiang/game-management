"""
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
    # 场景1
    {
        'scene_id': 1,
        'transition_id': 1,
        'description': '场景1 -> 场景2',
        'controller_options': [
            [50, 1, 2, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [2]
    },
    {
        'scene_id': 1,
        'transition_id': 2,
        'description': '西瓜主页界面 - 关机',
        'controller_options': [
            [1000, 1, 2, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [7]
    },

    # 场景2
    {
        'scene_id': 2,
        'transition_id': 1,
        'description': '场景2 -> 场景203',
        'controller_options': [
            [50, 0, 512, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [203]
    },
    {
        'scene_id': 2,
        'transition_id': 2,
        'description': '西瓜引导页进入档案和系统',
        'controller_options': [
            [50, 5, 512, 0, 0, 0, 0, 0, 0],
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [3]
    },

    # 场景3
    {
        'scene_id': 3,
        'transition_id': 1,
        'description': '档案和系统选中添加和切换',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [5]
    },

    # 场景5
    {
        'scene_id': 5,
        'transition_id': 1,
        'description': '添加和切换进入账号选择',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [6]
    },

    # 场景7
    {
        'scene_id': 7,
        'transition_id': 1,
        'description': '场景7 -> 场景8',
        'controller_options': [
            [50, 1, 256, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [8]
    },

    # 场景8
    {
        'scene_id': 8,
        'transition_id': 1,
        'description': '场景8 -> 场景8',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [8]
    },

    # 场景101
    {
        'scene_id': 101,
        'transition_id': 1,
        'description': '场景101 -> 场景126',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [126]
    },

    # 场景126
    {
        'scene_id': 126,
        'transition_id': 1,
        'description': '场景126 -> 场景127',
        'controller_options': [
            [50, 0, 512, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [127]
    },

    # 场景127
    {
        'scene_id': 127,
        'transition_id': 1,
        'description': '场景127 -> 场景147',
        'controller_options': [
            [50, 0, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [147]
    },

    # 场景147
    {
        'scene_id': 147,
        'transition_id': 1,
        'description': '场景147 -> 场景149',
        'controller_options': [
            [50, 2, 4, 0, 255, 0, 0, 0, 0],
        ],
        'target_scenes': [149]
    },
    {
        'scene_id': 147,
        'transition_id': 2,
        'description': 'UT主菜单 -> 转会Tab（152）',
        'controller_options': [
            [50, 1, 4096, 0, 255, 0, 0, 0, 0],
            [50, 2, 4096, 0, 255, 0, 0, 0, 0],
            [50, 3, 4096, 0, 255, 0, 0, 0, 0],
        ],
        'target_scenes': [152]
    },

    # 场景149
    {
        'scene_id': 149,
        'transition_id': 1,
        'description': '场景149 -> 场景155',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [155]
    },
    {
        'scene_id': 149,
        'transition_id': 2,
        'description': 'UT开始游戏Tab -> 转会Tab（152）',
        'controller_options': [
            [50, 1, 4096, 0, 255, 0, 0, 0, 0],
            [50, 2, 4096, 0, 255, 0, 0, 0, 0],
            [50, 3, 4096, 0, 255, 0, 0, 0, 0],
        ],
        'target_scenes': [152]
    },

    # 场景155
    {
        'scene_id': 155,
        'transition_id': 1,
        'description': '场景155 -> 场景156',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [156]
    },

    # 场景156
    {
        'scene_id': 156,
        'transition_id': 1,
        'description': '场景156 -> 场景168',
        'controller_options': [
            [50, 0, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [168]
    },

    # 场景168
    {
        'scene_id': 168,
        'transition_id': 1,
        'description': '场景168 -> 场景177',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [177]
    },

    # 场景169
    {
        'scene_id': 169,
        'transition_id': 1,
        'description': '场景169 -> 场景177',
        'controller_options': [
            [50, 1, 2048, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [177]
    },

    # 场景170
    {
        'scene_id': 170,
        'transition_id': 1,
        'description': '场景170 -> 场景177',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [177]
    },

    # 场景171
    {
        'scene_id': 171,
        'transition_id': 1,
        'description': '场景171 -> 场景177',
        'controller_options': [
            [50, 1, 512, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [177]
    },

    # 场景172
    {
        'scene_id': 172,
        'transition_id': 1,
        'description': '场景172 -> 场景177',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [177]
    },

    # 场景173
    {
        'scene_id': 173,
        'transition_id': 1,
        'description': '场景173 -> 场景177',
        'controller_options': [
            [50, 1, 1024, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [177]
    },

    # 场景174
    {
        'scene_id': 174,
        'transition_id': 1,
        'description': '场景174 -> 场景177',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [177]
    },

    # 场景175
    {
        'scene_id': 175,
        'transition_id': 1,
        'description': '场景175 -> 场景168',
        'controller_options': [
            [50, 1, 64, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [168]
    },

    # 场景177
    {
        'scene_id': 177,
        'transition_id': 1,
        'description': '场景177 -> 场景176',
        'controller_options': [
            [50, 1, 256, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [176]
    },
    {
        'scene_id': 177,
        'transition_id': 2,
        'description': '场景177 -> 场景183',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [183]
    },

    # 场景183
    {
        'scene_id': 183,
        'transition_id': 1,
        'description': '场景183 -> 场景189',
        'controller_options': [
            [50, 10, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [189]
    },

    # 场景203
    {
        'scene_id': 203,
        'transition_id': 1,
        'description': '场景203 -> 场景101',
        'controller_options': [
            [50, 1, 16, 0, 0, 0, 0, 0, 0],
        ],
        'target_scenes': [101]
    },
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

# SQB 189 开赛后 → 进入场中：轮询识别 + A/场景转移
SQB_PREMATCH_TARGETS = [102, 190]
SQB_PREMATCH_PROBE_SCENES = [
    189, 190, 102,
    127, 147, 149, 155, 156,
    *range(168, 176),
    177, 183,
    184, 185, 186, 187, 188, 193, 194,
]
SQB_PREMATCH_DISMISS_TIMEOUT = 90.0

# 「按住 A 跳过」类过场/庆祝：自动化须 sustained A（短按无效）
HOLD_A_SKIP_SCENE_IDS = frozenset({101, 102, 189, 190})
DISMISS_A_TAP_SEC = 0.12
HOLD_A_SKIP_PRESS_SEC = 2.0
# dismiss_until_scenes 模板未匹配时仍尝试长按 A 的 label（如 SQB 开球前过场）
DISMISS_HOLD_A_UNMATCHED_LABELS = frozenset({"SQB-PREMATCH"})


def resolve_automation_a_press_sec(
    scene_id: Optional[int],
    *,
    force_hold: bool = False,
) -> float:
    """
    自动化按 A 时长：过场/庆祝 scene 用长按，普通弹窗用短按。

    可通过 agent.yaml step4.hold_a_skip_sec / dismiss_a_tap_sec 覆盖。
    """
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


# 转会导航链（UT 主菜单 → 转会 Tab 152）
AUCTION_UT_CHAIN: List[Tuple[int, int]] = [
    (147, 2),
]

AUCTION_NAVIGATION_SCENES = [
    127, 147, 149, 150, 151, 152, 153, 154,
]

AUCTION_COMPLETE_SCENES = {152}

# 152 按 A 进入转会中心后占位等待（子界面 scene 实机补录前用 sleep）
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
