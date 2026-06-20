"""ProfileDetector — 检查主机上是否存在游戏账号档案。"""

from typing import Any

from ...task.task_context import GameAccountInfo


class ProfileDetector:
    def __init__(self, scene_detector: Any):
        self._scene = scene_detector

    async def profile_exists(self, game_account: GameAccountInfo) -> bool:
        """是否跳过「添加账号」：仅依据 is_new_user，不读平台 profile_bound / position_index。"""
        return not game_account.is_new_user
