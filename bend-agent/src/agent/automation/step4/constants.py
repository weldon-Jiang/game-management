"""
Step4 常量定义
============
场景ID映射、游戏模式配置、难度/段位/拍卖行参数。
从原 step4_game_automation.py 提取，无行为变更。
"""
from typing import Dict

# 合法任务类型集合
VALID_TASK_TYPES = frozenset({
    'auction_transfer',
    'squad_battle',
    'transfer_sqb_combo',
    'divisions_rivals',
    'weekend_league',
})

# 比赛结束 / 回到 UT 菜单的场景（本地模板 + streaming 对齐）
MATCH_END_SCENE_IDS = [102, 193]
UT_MENU_SCENE_IDS = [127, 147, 149]
SETTLEMENT_SCENE_IDS = [184, 185, 186, 187, 188, 189, 193]

# expected_screen -> Streaming 场景 ID（Xbox 系统 UI 1-9，足球 UT 菜单 100+）
EXPECTED_SCREEN_SCENES: Dict[str, list] = {
    'MAIN_MENU': [127, 149, 147, 101],
    'MATCH_START': [168, 176],
    'XBOX_SCENE_3': [3],
    'XBOX_SCENE_5': [5],
    'XBOX_SCENE_6': [6],
}

# 游戏模式导航配置
NAVIGATION_CONFIG = {
    'ut_menu_timeout': 30,       # UT菜单检测超时(秒)
    'matchmaking_timeout': 60,   # 匹配超时(秒)
    'button_press_delay': 0.3,   # 按钮按下后等待时间(秒)
}

# SQB 难度配置
SQB_DIFFICULTY_MAP = {
    'easy': 'World Class',
    'normal': 'Professional',
    'hard': 'Harder',
    'ultimate': 'Ultimate',
}

# 拍卖行配置
AUCTION_CONFIG = {
    'buy': {
        'min_price': 1000,
        'max_price': 50000,
        'max_bid_increase': 1000,
        'retry_count': 3,
    },
    'sell': {
        'starting_price_ratio': 0.8,
        'buy_now_price_ratio': 1.0,
        'duration_minutes': 60,
    }
}

# DR 段位配置
DR_DIVISION_MAP = {
    'champion': {'min_points': 2000, 'max_points': 9999, 'display': 'Champion'},
    'elite': {'min_points': 1500, 'max_points': 1999, 'display': 'Elite'},
    'gold': {'min_points': 1000, 'max_points': 1499, 'display': 'Gold'},
    'silver': {'min_points': 500, 'max_points': 999, 'display': 'Silver'},
    'bronze': {'min_points': 0, 'max_points': 499, 'display': 'Bronze'},
}

# 周赛资格配置
WEEKEND_LEAGUE_REQUIREMENTS = {
    'min_division': 'elite',
    'min_dr_points': 1500,
    'max_matches_per_day': 5,
    'total_matches': 10,
}
