"""
游戏账号切换器
==============

功能说明：
- 管理多个游戏账号
- 自动化账号切换流程（位置索引 + Streaming 场景卡点）
- 验证账号登录状态

技术实现说明：
- gamertag 因人而异，列表内用 position_index + 方向键定位
- 场景 3/5/6 用 StreamingSceneDetector 校验 Xbox 系统 UI
"""

import asyncio
from typing import Optional, Dict, List, Any, Callable, Awaitable
from dataclasses import dataclass
from enum import Enum
import time

from ..core.logger import get_logger


class AccountStatus(Enum):
    """账号状态枚举"""
    UNKNOWN = "unknown"
    AVAILABLE = "available"
    LOGGING_IN = "logging_in"
    LOGGED_IN = "logged_in"
    LOGGING_OUT = "logging_out"
    LOGGED_OUT = "logged_out"
    ERROR = "error"


@dataclass
class GameAccount:
    """游戏账号数据"""
    account_id: str
    gamertag: str
    email: Optional[str] = None
    password: Optional[str] = None
    xuid: Optional[str] = None
    position_index: int = 0
    status: AccountStatus = AccountStatus.UNKNOWN
    last_login: Optional[float] = None
    matches_today: int = 0
    max_matches_per_day: int = 3

    def is_available(self) -> bool:
        return self.matches_today < self.max_matches_per_day

    def mark_login(self):
        self.status = AccountStatus.LOGGED_IN
        self.last_login = time.time()

    def increment_matches(self):
        self.matches_today += 1

    def reset_daily_count(self):
        self.matches_today = 0


@dataclass
class AccountSwitchResult:
    """账号切换结果"""
    success: bool
    from_account: Optional[str] = None
    to_account: Optional[str] = None
    error_message: Optional[str] = None
    time_taken: float = 0.0


class AccountSwitcher:
    """
    游戏账号切换器（位置索引 + 场景校验）

    步骤：引导菜单 → 场景3 → 场景5 → 场景6 → 按索引选账号 → 确认
    """

    def __init__(self):
        self.logger = get_logger('account_switcher')
        self._accounts: Dict[str, GameAccount] = {}
        self._current_account_id: Optional[str] = None
        self._action_executor = None
        self._scene_detector = None
        self._frame_getter: Optional[Callable[[], Awaitable[Any]]] = None

    def set_accounts(self, accounts: List[Dict[str, Any]]):
        self._accounts.clear()
        for idx, acc_data in enumerate(accounts):
            position_index = acc_data.get('position_index', idx)
            account = GameAccount(
                account_id=acc_data.get('account_id', ''),
                gamertag=acc_data.get('gamertag', ''),
                email=acc_data.get('email'),
                password=acc_data.get('password'),
                xuid=acc_data.get('xuid'),
                position_index=position_index,
                max_matches_per_day=acc_data.get('max_matches_per_day', 3),
            )
            self._accounts[account.account_id] = account

        self.logger.info(f"已加载 {len(self._accounts)} 个游戏账号")
        for acc in self._accounts.values():
            self.logger.info(f"  - {acc.gamertag} (位置: {acc.position_index})")

    def set_action_executor(self, executor):
        self._action_executor = executor
        self.logger.info("账号切换器已绑定动作执行器")

    def set_scene_detector(self, detector):
        self._scene_detector = detector
        self.logger.info("账号切换器已绑定场景检测器")

    def set_frame_getter(self, getter: Callable[[], Awaitable[Any]]):
        """设置异步截帧函数，用于场景校验"""
        self._frame_getter = getter

    @property
    def current_account(self) -> Optional[GameAccount]:
        if self._current_account_id:
            return self._accounts.get(self._current_account_id)
        return None

    @property
    def available_accounts(self) -> List[GameAccount]:
        return [acc for acc in self._accounts.values() if acc.is_available()]

    def get_account(self, account_id: str) -> Optional[GameAccount]:
        return self._accounts.get(account_id)

    async def switch_to(self, target_account_id: str) -> AccountSwitchResult:
        start_time = time.time()
        from_account = self._current_account_id

        if target_account_id == from_account:
            return AccountSwitchResult(
                success=True,
                from_account=from_account,
                to_account=target_account_id,
                time_taken=time.time() - start_time,
            )

        target_account = self._accounts.get(target_account_id)
        if not target_account:
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                error_message=f"账号不存在: {target_account_id}",
                time_taken=time.time() - start_time,
            )

        self.logger.info(
            f"切换账号: {from_account} -> {target_account_id} "
            f"({target_account.gamertag}, 位置: {target_account.position_index})"
        )

        try:
            await self._press_guide_button()

            await self._navigate_to_accounts_system()
            if not await self._wait_for_scene(3):
                raise RuntimeError("未进入档案和系统页面（场景3）")

            await self._select_add_switch()
            if not await self._wait_for_scene(5):
                raise RuntimeError("未进入添加和切换页面（场景5）")

            await self._enter_account_selection()
            if not await self._wait_for_scene(6):
                raise RuntimeError("未进入账号选择页面（场景6）")

            await self._navigate_to_account_position(target_account.position_index)
            await self._confirm_account_selection()

            if target_account.email and target_account.password:
                await self._login_with_credentials(target_account.email, target_account.password)

            self._current_account_id = target_account_id
            target_account.mark_login()

            time_taken = time.time() - start_time
            self.logger.info(f"账号切换成功: {target_account_id} (耗时: {time_taken:.2f}s)")
            return AccountSwitchResult(
                success=True,
                from_account=from_account,
                to_account=target_account_id,
                time_taken=time_taken,
            )

        except NotImplementedError as e:
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                to_account=target_account_id,
                error_message=str(e),
                time_taken=time.time() - start_time,
            )
        except Exception as e:
            self.logger.error(f"账号切换失败: {e}")
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                to_account=target_account_id,
                error_message=str(e),
                time_taken=time.time() - start_time,
            )

    async def _wait_for_scene(self, scene_id: int, timeout: float = 20.0) -> bool:
        if not self._scene_detector or not self._frame_getter:
            self.logger.warning(f"跳过场景{scene_id}校验（未绑定检测器或截帧）")
            return True

        deadline = time.time() + timeout
        while time.time() < deadline:
            frame = await self._frame_getter()
            if frame is None:
                await asyncio.sleep(0.4)
                continue
            image = frame.data if hasattr(frame, 'data') else frame
            result = self._scene_detector.recognize_scene(image, scene_id=scene_id)
            if result.matched:
                self.logger.info(f"场景{scene_id}校验通过 (置信度 {result.confidence:.2f})")
                return True
            await asyncio.sleep(0.5)

        self.logger.warning(f"场景{scene_id}校验超时 ({timeout}s)")
        return False

    async def _press_guide_button(self):
        if not self._action_executor:
            return
        from ..scene.game_automation_engine import Action, ActionType
        await self._action_executor.execute(
            Action(
                type=ActionType.PRESS_BUTTON,
                params={'button': 'XBOX', 'duration': 0.2},
                description="Press Xbox guide button",
                timeout=3.0,
            )
        )
        await asyncio.sleep(1.0)

    async def _navigate_to_accounts_system(self):
        if not self._action_executor:
            return
        from ..scene.game_automation_engine import Action, ActionType
        for _ in range(3):
            await self._action_executor.execute(
                Action(
                    type=ActionType.PRESS_BUTTON,
                    params={'button': 'DPAD_DOWN', 'duration': 0.1},
                    description="Press DOWN",
                    timeout=1.0,
                )
            )
            await asyncio.sleep(0.2)
        await self._action_executor.execute(
            Action(
                type=ActionType.PRESS_BUTTON,
                params={'button': 'A', 'duration': 0.1},
                description="Press A",
                timeout=1.0,
            )
        )
        await asyncio.sleep(1.0)

    async def _select_add_switch(self):
        if not self._action_executor:
            return
        from ..scene.game_automation_engine import Action, ActionType
        for _ in range(2):
            await self._action_executor.execute(
                Action(
                    type=ActionType.PRESS_BUTTON,
                    params={'button': 'DPAD_DOWN', 'duration': 0.1},
                    description="Press DOWN",
                    timeout=1.0,
                )
            )
            await asyncio.sleep(0.2)
        await self._action_executor.execute(
            Action(
                type=ActionType.PRESS_BUTTON,
                params={'button': 'A', 'duration': 0.1},
                description="Press A",
                timeout=1.0,
            )
        )
        await asyncio.sleep(1.5)

    async def _enter_account_selection(self):
        if not self._action_executor:
            return
        from ..scene.game_automation_engine import Action, ActionType
        await self._action_executor.execute(
            Action(
                type=ActionType.PRESS_BUTTON,
                params={'button': 'A', 'duration': 0.1},
                description="Press A to enter account selection",
                timeout=1.0,
            )
        )
        await asyncio.sleep(1.5)

    async def _navigate_to_account_position(self, position_index: int):
        if not self._action_executor:
            return
        from ..scene.game_automation_engine import Action, ActionType

        for _ in range(10):
            await self._action_executor.execute(
                Action(
                    type=ActionType.PRESS_BUTTON,
                    params={'button': 'DPAD_UP', 'duration': 0.1},
                    description="Press UP",
                    timeout=0.5,
                )
            )
            await asyncio.sleep(0.15)

        for i in range(position_index):
            await self._action_executor.execute(
                Action(
                    type=ActionType.PRESS_BUTTON,
                    params={'button': 'DPAD_DOWN', 'duration': 0.1},
                    description=f"Press DOWN ({i + 1}/{position_index})",
                    timeout=0.5,
                )
            )
            await asyncio.sleep(0.2)

    async def _confirm_account_selection(self):
        if not self._action_executor:
            return
        from ..scene.game_automation_engine import Action, ActionType
        await self._action_executor.execute(
            Action(
                type=ActionType.PRESS_BUTTON,
                params={'button': 'A', 'duration': 0.1},
                description="Press A to confirm selection",
                timeout=1.0,
            )
        )
        await asyncio.sleep(2.0)

    async def _login_with_credentials(self, email: str, password: str):
        """小键盘场景 10-33 尚未实现，需要时由平台预登录或后续补齐。"""
        self.logger.error(
            "账号需要邮箱密码登录，但 on-screen 小键盘流程未实现 (email=%s)",
            email,
        )
        raise NotImplementedError("邮箱密码登录（场景10-33）尚未实现，请确保账号已在主机上登录")

    async def validate_current(self) -> bool:
        if not self._current_account_id:
            return False
        current = self._accounts.get(self._current_account_id)
        if not current:
            return False
        if current.status == AccountStatus.LOGGED_IN:
            return True
        if current.last_login and (time.time() - current.last_login) > 3600:
            self.logger.warning("账号登录已超过1小时，可能需要重新验证")
            return False
        return True

    def reset_all_daily_counts(self):
        for account in self._accounts.values():
            account.reset_daily_count()
        self.logger.info("所有账号每日计数已重置")


account_switcher = AccountSwitcher()
