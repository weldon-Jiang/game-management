"""
游戏账号管理器 — 管理 Xbox 游戏账号。
"""
import asyncio
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..core.logger import get_logger


@dataclass
class GameAccount:
    """游戏账号信息"""
    id: str
    name: str
    email: str
    gamertag: str
    password: Optional[str] = None
    is_active: bool = False
    last_used: Optional[datetime] = None
    max_play_time: int = 360  # 每日最大游玩分钟数
    used_today: int = 0
    reset_time: str = "00:00"  # 每日重置时间


class GameAccountManager:
    """
    管理 Xbox 游戏账号。
    处理账号切换与游玩时长跟踪。
    """

    def __init__(self, input_controller, scene_detector, template_matcher):
        self.input = input_controller
        self.scene = scene_detector
        self.matcher = template_matcher
        self._accounts: Dict[str, GameAccount] = {}
        self._active_account: Optional[GameAccount] = None
        self.logger = get_logger('game_account')

    def add_account(self, account: GameAccount):
        """向管理器添加游戏账号。"""
        self._accounts[account.id] = account
        self.logger.info(f"Added account: {account.gamertag}")

    def remove_account(self, account_id: str):
        """从管理器移除账号。"""
        if account_id in self._accounts:
            del self._accounts[account_id]
            self.logger.info(f"Removed account: {account_id}")

    def get_account(self, account_id: str) -> Optional[GameAccount]:
        """按 ID 获取账号"""
        return self._accounts.get(account_id)

    def get_all_accounts(self) -> List[GameAccount]:
        """获取全部账号"""
        return list(self._accounts.values())

    def get_active_account(self) -> Optional[GameAccount]:
        """获取当前活动账号"""
        return self._active_account

    def get_available_accounts(self) -> List[GameAccount]:
        """获取今日未超游玩时长的账号"""
        now = datetime.now()
        accounts = []

        for account in self._accounts.values():
            if self._should_reset(account, now):
                account.used_today = 0

            if account.used_today < account.max_play_time:
                accounts.append(account)

        return accounts

    def _should_reset(self, account: GameAccount, now: datetime) -> bool:
        """检查账号每日计时是否应重置。"""
        try:
            reset_hour, reset_min = map(int, account.reset_time.split(':'))
            reset_today = now.replace(hour=reset_hour, minute=reset_min, second=0)
            return now >= reset_today and account.last_used and account.last_used < reset_today
        except:
            return False

    async def switch_to_account(self, account: GameAccount, frame_getter) -> bool:
        """
        切换到指定游戏账号。

        参数:
            account: 要切换到的账号
            frame_getter: 获取当前帧的异步函数

        返回:
            切换成功为 True
        """
        if self._active_account and self._active_account.id == account.id:
            self.logger.info(f"Account already active: {account.gamertag}")
            return True

        self.logger.info(f"Switching to account: {account.gamertag}")

        try:
            await self._open_guide()
            await asyncio.sleep(0.5)

            await self._navigate_to_accounts()
            await asyncio.sleep(0.5)

            await self._select_account(account, frame_getter)
            await asyncio.sleep(1)

            await self._confirm_switch()
            await asyncio.sleep(2)

            self._active_account = account
            account.is_active = True
            account.last_used = datetime.now()

            self.logger.info(f"Switched to account: {account.gamertag}")
            return True

        except Exception as e:
            self.logger.error(f"Account switch failed: {e}")
            return False

    async def _open_guide(self):
        """打开 Xbox 引导页。"""
        await self.input.press_key('xbox')  # 手柄 Xbox 键
        await asyncio.sleep(1)

    async def _navigate_to_accounts(self):
        """在引导页导航到账号管理。"""
        for _ in range(3):
            await self.input.press_key('down')
            await asyncio.sleep(0.2)

        await self.input.press_key('a')
        await asyncio.sleep(0.5)

    async def _select_account(self, account: GameAccount, frame_getter):
        """从列表选择账号（遗留；step4 优先用 AccountSwitcher）。"""
        for _ in range(5):
            await self.input.press_key('up')
            await asyncio.sleep(0.2)

        for _ in range(len(self._accounts)):
            await self.input.press_key('down')
            await asyncio.sleep(0.2)

            frame_data = await self._resolve_frame_data(frame_getter)
            if frame_data is None:
                continue

            result = await self.matcher.find_template(
                frame_data,
                f"account_{account.gamertag}.png"
            )
            if result.found:
                await self.input.press_key('a')
                break

    @staticmethod
    async def _resolve_frame_data(frame_getter):
        frame = frame_getter()
        if asyncio.iscoroutine(frame):
            frame = await frame
        if frame is None:
            return None
        if hasattr(frame, 'data'):
            return frame.data
        return frame

    async def _confirm_switch(self):
        """确认账号切换。"""
        await self.input.press_key('a')
        await asyncio.sleep(1)

        result = await self.matcher.find_template(
            await self._get_current_frame(),
            'confirm_switch.png'
        )
        if result.found:
            await self.input.press_key('a')

    async def _get_current_frame(self, frame_getter=None):
        """可用时通过注入的 getter 获取当前帧。"""
        if frame_getter is None:
            return None
        return await self._resolve_frame_data(frame_getter)

    def update_play_time(self, minutes: int):
        """更新活动账号游玩时长。"""
        if self._active_account:
            self._active_account.used_today += minutes
            self.logger.debug(f"Play time updated: {minutes}min, total today: {self._active_account.used_today}min")

    def is_play_time_available(self, account: Optional[GameAccount] = None) -> bool:
        """检查账号今日是否还有剩余游玩时长。"""
        acc = account or self._active_account
        if not acc:
            return False
        return acc.used_today < acc.max_play_time

    def get_remaining_time(self, account: Optional[GameAccount] = None) -> int:
        """获取剩余游玩时长（分钟）。"""
        acc = account or self._active_account
        if not acc:
            return 0
        return max(0, acc.max_play_time - acc.used_today)
