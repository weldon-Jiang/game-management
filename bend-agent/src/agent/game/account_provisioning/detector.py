"""ProfileDetector — 检查主机上是否存在游戏账号档案。"""

from typing import Any

from ...task.task_context import GameAccountInfo


class ProfileDetector:
    def __init__(self, scene_detector: Any):
        self._scene = scene_detector

    async def profile_exists(self, game_account: GameAccountInfo) -> bool:
        if game_account.profile_bound and not game_account.is_new_user:
            return True
        if game_account.position_index >= 0 and not game_account.is_new_user:
            return True
        return False
