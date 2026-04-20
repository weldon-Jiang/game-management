"""
Game Account Manager - Manages Xbox game accounts
"""
import asyncio
from typing import List, Optional, Dict
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..core.logger import get_logger


@dataclass
class GameAccount:
    """Game account information"""
    id: str
    name: str
    email: str
    gamertag: str
    password: Optional[str] = None
    is_active: bool = False
    last_used: Optional[datetime] = None
    max_play_time: int = 360  # minutes per day
    used_today: int = 0
    reset_time: str = "00:00"  # daily reset time


class GameAccountManager:
    """
    Manages Xbox game accounts
    Handles account switching and play time tracking
    """

    def __init__(self, input_controller, scene_detector, template_matcher):
        self.input = input_controller
        self.scene = scene_detector
        self.matcher = template_matcher
        self._accounts: Dict[str, GameAccount] = {}
        self._active_account: Optional[GameAccount] = None
        self.logger = get_logger('game_account')

    def add_account(self, account: GameAccount):
        """Add game account to manager"""
        self._accounts[account.id] = account
        self.logger.info(f"Added account: {account.gamertag}")

    def remove_account(self, account_id: str):
        """Remove account from manager"""
        if account_id in self._accounts:
            del self._accounts[account_id]
            self.logger.info(f"Removed account: {account_id}")

    def get_account(self, account_id: str) -> Optional[GameAccount]:
        """Get account by ID"""
        return self._accounts.get(account_id)

    def get_all_accounts(self) -> List[GameAccount]:
        """Get all accounts"""
        return list(self._accounts.values())

    def get_active_account(self) -> Optional[GameAccount]:
        """Get currently active account"""
        return self._active_account

    def get_available_accounts(self) -> List[GameAccount]:
        """Get accounts that haven't exceeded play time today"""
        now = datetime.now()
        accounts = []

        for account in self._accounts.values():
            if self._should_reset(account, now):
                account.used_today = 0

            if account.used_today < account.max_play_time:
                accounts.append(account)

        return accounts

    def _should_reset(self, account: GameAccount, now: datetime) -> bool:
        """Check if account's daily timer should reset"""
        try:
            reset_hour, reset_min = map(int, account.reset_time.split(':'))
            reset_today = now.replace(hour=reset_hour, minute=reset_min, second=0)
            return now >= reset_today and account.last_used and account.last_used < reset_today
        except:
            return False

    async def switch_to_account(self, account: GameAccount, frame_getter) -> bool:
        """
        Switch to specified game account

        Args:
            account: Account to switch to
            frame_getter: Async function to get current frame

        Returns:
            True if switch successful
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

            await self._select_account(account)
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
        """Open Xbox guide"""
        await self.input.press_key('xbox')  # Xbox button on gamepad
        await asyncio.sleep(1)

    async def _navigate_to_accounts(self):
        """Navigate to account management in guide"""
        for _ in range(3):
            await self.input.press_key('down')
            await asyncio.sleep(0.2)

        await self.input.press_key('a')
        await asyncio.sleep(0.5)

    async def _select_account(self, account: GameAccount):
        """Select account from list"""
        for _ in range(5):
            await self.input.press_key('up')
            await asyncio.sleep(0.2)

        for _ in range(len(self._accounts)):
            await self.input.press_key('down')
            await asyncio.sleep(0.2)

            result = await self.matcher.find_template(
                await frame_getter(),
                f"account_{account.gamertag}.png"
            )
            if result.found:
                await self.input.press_key('a')
                break

    async def _confirm_switch(self):
        """Confirm account switch"""
        await self.input.press_key('a')
        await asyncio.sleep(1)

        result = await self.matcher.find_template(
            await self._get_current_frame(),
            'confirm_switch.png'
        )
        if result.found:
            await self.input.press_key('a')

    async def _get_current_frame(self):
        """Get current frame (placeholder - should be injected)"""
        return None

    def update_play_time(self, minutes: int):
        """Update play time for active account"""
        if self._active_account:
            self._active_account.used_today += minutes
            self.logger.debug(f"Play time updated: {minutes}min, total today: {self._active_account.used_today}min")

    def is_play_time_available(self, account: Optional[GameAccount] = None) -> bool:
        """Check if account has remaining play time today"""
        acc = account or self._active_account
        if not acc:
            return False
        return acc.used_today < acc.max_play_time

    def get_remaining_time(self, account: Optional[GameAccount] = None) -> int:
        """Get remaining play time in minutes"""
        acc = account or self._active_account
        if not acc:
            return 0
        return max(0, acc.max_play_time - acc.used_today)
