"""
电源路由：开机放行 / 待机唤醒 / 关机报错。

以 GSSV 云端电源 API 唤醒待机主机。
"""

from dataclasses import dataclass
from typing import Any, Optional

from ..core.config import config
from ..core.logger import get_logger


@dataclass
class PowerResult:
    ok: bool
    power_state: str = ""
    error_code: Optional[str] = None
    message: str = ""


class PowerManager:
    STANDBY_STATES = frozenset({"standby", "connectedstandby"})
    OFF_STATES = frozenset({"off"})

    def __init__(self):
        self.logger = get_logger("power_manager")
        self._wakeup_timeout = int(config.get("discovery.wakeup_timeout_sec", 30))

    def classify(self, power_state: str) -> str:
        ps = (power_state or "").strip().lower()
        if ps == "on":
            return "on"
        if ps in self.OFF_STATES:
            return "off"
        if ps in self.STANDBY_STATES:
            return "standby"
        return "unknown"

    async def ensure_power_on(
        self,
        credentials: Any,
        console: Any,
        *,
        gssv_client: Any = None,
        timeout: Optional[int] = None,
    ) -> PowerResult:
        ps = getattr(console, "power_state", "") or ""
        kind = self.classify(ps)
        if kind == "on":
            return PowerResult(ok=True, power_state="On")

        if kind == "off":
            return PowerResult(
                ok=False,
                power_state=ps,
                error_code="HOST_POWERED_OFF",
                message="主机已关机，请手动开机",
            )

        if kind == "unknown":
            return PowerResult(
                ok=False,
                power_state=ps,
                error_code="HOST_OFFLINE",
                message="主机不可达",
            )

        timeout = timeout or self._wakeup_timeout
        server_id = getattr(console, "server_id", "") or getattr(console, "id", "")
        if gssv_client and server_id:
            ok = await gssv_client.power_on(server_id)
            if ok:
                final = await self._poll_power(gssv_client, server_id, timeout)
                if final:
                    console.power_state = "On"
                    return PowerResult(ok=True, power_state="On")
                return PowerResult(
                    ok=False,
                    error_code="WAKEUP_FAILED",
                    message="唤醒超时",
                )

        return PowerResult(
            ok=False,
            error_code="WAKEUP_FAILED",
            message="云端唤醒失败",
        )

    async def _poll_power(self, gssv_client: Any, server_id: str, timeout: int) -> bool:
        import asyncio

        for _ in range(timeout):
            await asyncio.sleep(1)
            try:
                servers = await gssv_client.list_home_servers()
                for s in servers:
                    sid = s.get("serverId") or s.get("id", "")
                    if sid == server_id:
                        ps = (s.get("powerState") or "").strip()
                        if ps == "On":
                            return True
            except Exception as exc:
                self.logger.warning("Power poll error: %s", exc)
        return False
