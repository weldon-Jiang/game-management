"""AddAccountFlow — 在 Xbox 主机添加微软账号并同步 Gamertag 到平台。"""

from typing import Any, Awaitable, Callable, Optional

from ...core.logger import get_logger
from ...task.task_context import GameAccountInfo


class AddAccountFlow:
    def __init__(
        self,
        scene_detector: Any,
        input_sender: Any,
        platform_client: Any = None,
        frame_getter: Any = None,
        stream_session: Any = None,
        reconnect_callback: Optional[Callable[[], Awaitable[bool]]] = None,
        task_context: Any = None,
    ):
        self.logger = get_logger("add_account_flow")
        self._scene = scene_detector
        self._input = input_sender
        self._platform_client = platform_client
        self._frame_getter = frame_getter
        self._stream_session = stream_session
        self._reconnect_callback = reconnect_callback
        self._task_context = task_context

    def _build_switcher(self):
        from ..account_switcher import AccountSwitcher
        from ...scene.game_automation_engine import ActionExecutor

        switcher = AccountSwitcher()
        switcher.set_scene_detector(self._scene)

        executor = ActionExecutor()
        if self._input is not None:
            if isinstance(self._input, ActionExecutor):
                executor = self._input
            else:
                executor.set_controller_protocol(self._input)
        if self._stream_session is not None:
            executor.set_xbox_session(self._stream_session)
        switcher.set_action_executor(executor)
        if self._frame_getter is not None:
            switcher.set_frame_getter(self._frame_getter)
        if self._stream_session is not None:
            switcher.set_stream_session(self._stream_session)
        if self._reconnect_callback is not None:
            switcher.set_reconnect_callback(self._reconnect_callback)
        if self._task_context is not None:
            switcher.set_task_context(self._task_context)
        if self._platform_client and hasattr(self._platform_client, "update_profile_binding"):

            async def _sync_binding(
                ga_id: str,
                game_name: Optional[str] = None,
            ) -> None:
                await self._platform_client.update_profile_binding(
                    ga_id,
                    game_name=game_name,
                )

            switcher.set_gamertag_sync_callback(_sync_binding)
        return switcher

    async def run(
        self,
        game_account: GameAccountInfo,
        check_cancel: Callable[[], bool],
        on_step: Optional[Callable[[int, str], Any]] = None,
    ) -> bool:
        if not game_account.email or not game_account.password:
            self.logger.warning(
                "Missing credentials for game account %s",
                game_account.id or game_account.email,
            )
            return False

        steps = [
            (2, "打开添加用户"),
            (3, "选择使用现有 Microsoft 账号"),
            (4, "输入邮箱"),
            (5, "输入密码"),
            (6, "确认登录"),
            (7, "读取主机昵称"),
        ]
        try:
            switcher = self._build_switcher()
            from ..account_switcher import GameAccount
            from ..scenes.add_account import AddAccountScene

            for idx, msg in steps:
                if check_cancel():
                    return False
                if on_step:
                    on_step(idx, msg)
            target = GameAccount(
                account_id=game_account.id or "",
                gamertag=game_account.gamertag or "",
                email=game_account.email,
                password=game_account.password,
            )
            if check_cancel():
                return False
            async with switcher._stream_keepalive_loop():
                await switcher._ensure_input_ready()
                if not await switcher._open_guide_menu():
                    await switcher._navigate_to_accounts_system()
                elif not await switcher._run_scene_transition(2, 2):
                    await switcher._navigate_to_accounts_system()
                if not await switcher._wait_for_scene(3):
                    raise RuntimeError("未进入档案和系统页面（场景3）")
                await AddAccountScene(switcher).run(target)
            if target.gamertag:
                game_account.gamertag = target.gamertag
            return True
        except Exception as exc:
            self.logger.error("Add account flow failed: %s", exc)
            return False
