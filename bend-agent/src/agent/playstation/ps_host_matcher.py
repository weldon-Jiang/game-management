"""
PlayStation 主机匹配：Chiaki LAN 发现 + 指定主机 / 自动匹配排序。

无 GSSV 云端列表；候选集来自 LAN UDP（或平台 Redis 缓存）。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..core.logger import get_logger
from ..task.task_context import AgentTaskContext
from .models import PlayStationConsole
from .ps_lan_discovery import discover_playstation_lan

if TYPE_CHECKING:
    from ..api.platform_api_client import PlatformApiClient


@dataclass
class PsMatchResult:
    """PS 发现/匹配失败描述。"""

    success: bool = False
    error_code: str = ""
    message: str = ""
    error_details: Dict[str, Any] = field(default_factory=dict)


class PsHostMatcher:
    """PlayStation LAN 主机匹配（对标 xbox/XboxHostMatcher 的 LAN 段）。"""

    def __init__(self, platform_client: Optional["PlatformApiClient"] = None):
        self.logger = get_logger("ps_host_matcher")
        self._platform_client = platform_client
        self._local_consoles: Dict[str, PlayStationConsole] = {}

    async def discover_lan(self) -> Optional[PsMatchResult]:
        """Chiaki UDP + 平台缓存；失败返回 PsMatchResult。"""
        self.logger.info("PlayStation LAN 发现（Chiaki UDP）")
        self._local_consoles = await discover_playstation_lan(self._platform_client)
        if not self._local_consoles:
            return PsMatchResult(
                success=False,
                error_code="LAN_NO_HOST",
                message="局域网未发现 PlayStation 主机",
                error_details={
                    "suggestion": "确认账号平台类型为 PlayStation、主机同 LAN、Remote Play 已开启",
                },
            )
        self.logger.info("✓ PS LAN 发现 %s 台", len(self._local_consoles))
        return None

    def build_candidates(self, context: AgentTaskContext) -> List[PlayStationConsole]:
        """
        构建候选主机列表。

        - 指定主机：按 device_id / IP 过滤
        - auto_match_host=False 且无匹配：返回空
        - 否则：全部 LAN 主机，Ready 优先于 Standby
        """
        all_consoles = list(self._local_consoles.values())
        if not all_consoles:
            return []

        assigned = context.assigned_xbox
        if assigned and (assigned.id or assigned.ip_address):
            matched = self._filter_assigned(all_consoles, assigned)
            if matched:
                return self._sort_candidates(matched)
            self.logger.warning(
                "指定 PS 主机未在 LAN 发现: id=%s ip=%s",
                assigned.id,
                assigned.ip_address,
            )
            return []

        if not context.auto_match_host:
            return []

        return self._sort_candidates(all_consoles)

    @staticmethod
    def _filter_assigned(
        consoles: List[PlayStationConsole],
        assigned,
    ) -> List[PlayStationConsole]:
        target_id = (assigned.id or "").strip()
        target_ip = (assigned.ip_address or "").strip()
        result: List[PlayStationConsole] = []
        for console in consoles:
            if target_id and console.device_id == target_id:
                result.append(console)
            elif target_ip and console.ip_address == target_ip:
                result.append(console)
        return result

    @staticmethod
    def _sort_candidates(consoles: List[PlayStationConsole]) -> List[PlayStationConsole]:
        def _rank(c: PlayStationConsole) -> tuple:
            ps = c.power_state or ""
            if ps == "Ready":
                power_rank = 0
            elif ps == "Standby":
                power_rank = 1
            else:
                power_rank = 2
            return (power_rank, c.name.lower())

        return sorted(consoles, key=_rank)
