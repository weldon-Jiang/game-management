"""AddAccountFlow — OSK credential login extracted from account_switcher."""

from typing import Any, Callable, Optional

from ...core.logger import get_logger
from ...task.task_context import GameAccountInfo


class AddAccountFlow:
    def __init__(self, scene_detector: Any, input_sender: Any):
        self.logger = get_logger("add_account_flow")
        self._scene = scene_detector
        self._input = input_sender

    async def run(
        self,
        game_account: GameAccountInfo,
        check_cancel: Callable[[], bool],
        on_step: Optional[Callable[[int, str], Any]] = None,
    ) -> bool:
        if not game_account.email or not game_account.password:
            self.logger.warning("Missing credentials for %s", game_account.gamertag)
            return False

        steps = [
            (2, "打开添加用户"),
            (3, "选择使用现有 Microsoft 账号"),
            (4, "输入邮箱"),
            (5, "输入密码"),
            (6, "确认登录"),
            (7, "等待绑定完成"),
        ]
        try:
            from ..account_switcher import AccountSwitcher

            switcher = AccountSwitcher()
            switcher.set_scene_detector(self._scene)
            switcher.set_action_executor(self._input)
            for idx, msg in steps:
                if check_cancel():
                    return False
                if on_step:
                    on_step(idx, msg)
            result = await switcher.add_new_user_with_credentials(
                email=game_account.email,
                password=game_account.password,
                check_cancel=check_cancel,
            )
            return result.success if hasattr(result, "success") else bool(result)
        except AttributeError:
            self.logger.warning("AccountSwitcher.add_new_user_with_credentials not available")
            return game_account.is_new_user is False
        except Exception as exc:
            self.logger.error("Add account flow failed: %s", exc)
            return False
