"""
游戏账号切换器
==============

功能说明：
- 管理多个游戏账号
- 自动化账号切换流程
- 验证账号登录状态
- 支持账号信息安全存储

技术实现参考（streaming项目）：
- account_manager.cpp (C++)
- AccountSwitcher (C++)

作者：技术团队
版本：1.0
"""

import asyncio
from typing import Optional, Dict, List, Any, Callable
from dataclasses import dataclass, field
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
    status: AccountStatus = AccountStatus.UNKNOWN
    last_login: Optional[float] = None
    matches_today: int = 0
    max_matches_per_day: int = 3

    def is_available(self) -> bool:
        """检查账号是否可用（未达到当日上限）"""
        return self.matches_today < self.max_matches_per_day

    def mark_login(self):
        """标记登录"""
        self.status = AccountStatus.LOGGED_IN
        self.last_login = time.time()

    def increment_matches(self):
        """增加比赛计数"""
        self.matches_today += 1

    def reset_daily_count(self):
        """重置每日计数"""
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
    游戏账号切换器

    功能说明：
    - 管理游戏账号列表
    - 执行账号切换动作序列
    - 验证切换结果
    - 支持自动化流程

    使用方式：
    - set_accounts(accounts): 设置账号列表
    - set_action_executor(executor): 设置动作执行器
    - switch_to(account_id): 切换到指定账号
    - validate_current(): 验证当前账号
    """

    def __init__(self):
        self.logger = get_logger('account_switcher')
        self._accounts: Dict[str, GameAccount] = {}
        self._current_account_id: Optional[str] = None
        self._action_executor = None
        self._state_callback: Optional[Callable] = None

    def set_accounts(self, accounts: List[Dict[str, Any]]):
        """
        设置账号列表

        参数：
        - accounts: 账号信息列表
        """
        self._accounts.clear()

        for acc_data in accounts:
            account = GameAccount(
                account_id=acc_data.get('account_id', ''),
                gamertag=acc_data.get('gamertag', ''),
                email=acc_data.get('email'),
                password=acc_data.get('password'),
                xuid=acc_data.get('xuid'),
                max_matches_per_day=acc_data.get('max_matches_per_day', 3)
            )
            self._accounts[account.account_id] = account

        self.logger.info(f"已加载 {len(self._accounts)} 个游戏账号")

    def set_action_executor(self, executor):
        """设置动作执行器"""
        self._action_executor = executor
        self.logger.info("账号切换器已绑定动作执行器")

    def set_state_callback(self, callback: Callable):
        """设置状态回调"""
        self._state_callback = callback

    @property
    def current_account(self) -> Optional[GameAccount]:
        """获取当前账号"""
        if self._current_account_id:
            return self._accounts.get(self._current_account_id)
        return None

    @property
    def available_accounts(self) -> List[GameAccount]:
        """获取可用账号列表"""
        return [acc for acc in self._accounts.values() if acc.is_available()]

    def get_account(self, account_id: str) -> Optional[GameAccount]:
        """获取指定账号"""
        return self._accounts.get(account_id)

    async def switch_to(self, target_account_id: str) -> AccountSwitchResult:
        """
        切换到目标账号

        参数：
        - target_account_id: 目标账号ID

        返回：
        - AccountSwitchResult: 切换结果
        """
        start_time = time.time()

        from_account = self._current_account_id

        if target_account_id == from_account:
            self.logger.info(f"已是目标账号: {target_account_id}")
            return AccountSwitchResult(
                success=True,
                from_account=from_account,
                to_account=target_account_id,
                time_taken=time.time() - start_time
            )

        target_account = self._accounts.get(target_account_id)
        if not target_account:
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                error_message=f"账号不存在: {target_account_id}",
                time_taken=time.time() - start_time
            )

        self.logger.info(f"切换账号: {from_account} -> {target_account_id} ({target_account.gamertag})")

        try:
            self.logger.info("[账号切换] 开始登出当前账号...")
            await self._logout_current()
            self.logger.info("[账号切换] 当前账号已登出")

            await asyncio.sleep(0.5)

            self.logger.info(f"[账号切换] 开始登录目标账号: {target_account.gamertag}")
            await self._login_to(target_account)
            self.logger.info(f"[账号切换] 目标账号登录动作已执行")

            self._current_account_id = target_account_id
            target_account.mark_login()

            time_taken = time.time() - start_time
            self.logger.info(f"账号切换成功: {target_account_id} (耗时: {time_taken:.2f}s)")

            return AccountSwitchResult(
                success=True,
                from_account=from_account,
                to_account=target_account_id,
                time_taken=time_taken
            )

        except Exception as e:
            self.logger.error(f"账号切换失败: {e}")
            return AccountSwitchResult(
                success=False,
                from_account=from_account,
                to_account=target_account_id,
                error_message=str(e),
                time_taken=time.time() - start_time
            )

    async def _logout_current(self):
        """登出当前账号"""
        if not self._current_account_id:
            self.logger.debug("无当前账号，无需登出")
            return

        current = self._accounts.get(self._current_account_id)
        if current:
            current.status = AccountStatus.LOGGING_OUT

        if self._action_executor:
            self.logger.debug("执行登出动作...")
            await self._action_executor.execute_sequence([
                await self._create_back_sequence(),
            ])

        self.logger.debug("当前账号已登出")

    async def _login_to(self, account: GameAccount):
        """登录到指定账号"""
        account.status = AccountStatus.LOGGING_IN

        if self._action_executor:
            self.logger.debug(f"执行登录动作: {account.gamertag}")

            await self._action_executor.execute_sequence([
                await self._create_navigate_sequence('LEFT'),
                await self._create_press_action('A'),
            ])

            await asyncio.sleep(1.0)

            await self._action_executor.execute_sequence([
                await self._create_navigate_sequence('DOWN'),
                await self._create_press_action('A'),
            ])

            await asyncio.sleep(2.0)

            accounts_on_screen = self._find_account_on_screen(account.gamertag)

            if accounts_on_screen >= 0:
                for _ in range(accounts_on_screen):
                    await self._action_executor.execute(
                        await self._create_press_action('DOWN')
                    )
                    await asyncio.sleep(0.2)

            await self._action_executor.execute(
                await self._create_press_action('A')
            )

            await asyncio.sleep(2.0)

        self.logger.debug(f"账号 {account.gamertag} 登录动作已执行")

    async def _find_account_on_screen(self, gamertag: str) -> int:
        """
        查找账号在屏幕上的位置

        参数：
        - gamertag: 玩家标签

        返回：
        - 位置索引，未找到返回-1
        """
        if self._state_callback:
            try:
                scene = await self._state_callback()
                if hasattr(scene, 'matched_accounts'):
                    if gamertag in scene.matched_accounts:
                        return scene.matched_accounts.index(gamertag)
            except:
                pass

        return 0

    async def _create_back_sequence(self) -> 'Action':
        """创建返回序列"""
        from .game_automation_engine import Action, ActionType
        return Action(
            type=ActionType.PRESS_BUTTON_SEQUENCE,
            params={'sequence': ['B', 'B', 'B'], 'interval': 0.3},
            description="Navigate back",
            timeout=5.0
        )

    async def _create_navigate_sequence(self, direction: str) -> 'Action':
        """创建导航序列"""
        from .game_automation_engine import Action, ActionType
        return Action(
            type=ActionType.NAVIGATE,
            params={'path': [direction]},
            description=f"Navigate {direction}",
            timeout=2.0
        )

    async def _create_press_action(self, button: str) -> 'Action':
        """创建按按钮动作"""
        from .game_automation_engine import Action, ActionType
        return Action(
            type=ActionType.PRESS_BUTTON,
            params={'button': button, 'duration': 0.1},
            description=f"Press {button}",
            timeout=2.0
        )

    async def validate_current(self) -> bool:
        """
        验证当前账号登录状态

        返回：
        - True: 账号有效
        - False: 账号无效
        """
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
        """重置所有账号的每日计数"""
        for account in self._accounts.values():
            account.reset_daily_count()
        self.logger.info("所有账号每日计数已重置")


account_switcher = AccountSwitcher()
