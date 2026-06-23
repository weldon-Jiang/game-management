"""添加新用户场景：scene5/6 → 添加新用户 → scene10 凭据登录。"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..account_switcher import AccountSwitcher, GameAccount


class AddAccountScene:
    """可复用的添加账号场景；各分支统一调用。"""

    def __init__(self, switcher: "AccountSwitcher"):
        self._switcher = switcher

    async def run(self, target_account: "GameAccount") -> None:
        await self._switcher.run_add_account_flow(target_account)
