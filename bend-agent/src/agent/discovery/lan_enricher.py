"""Parallel SSDP enrich for LAN IP (optional, non-blocking)."""

import asyncio
from typing import Dict, List

from ..core.config import config
from ..core.logger import get_logger
from .models import ConsoleTarget


class LanEnricher:
    def __init__(self):
        self.logger = get_logger("lan_enricher")
        self._enabled = bool(config.get("discovery.ssdp_enrich_enabled", True))

    async def enrich(self, consoles: List[ConsoleTarget]) -> List[ConsoleTarget]:
        if not self._enabled or not consoles:
            return consoles
        # xCloud 已匹配 serverId 且已开机时无需全网段端口扫描（会阻塞数分钟）
        if all(
            (c.server_id or c.id)
            and (c.power_state or "").strip().lower() == "on"
            and c.ip_address
            for c in consoles
        ):
            return consoles
        if all((c.server_id or c.id) for c in consoles):
            self.logger.info(
                "Skip LAN enrich: cloud serverId resolved (serverId=%s)",
                consoles[0].server_id or consoles[0].id,
            )
            return consoles
        try:
            from ..xbox.xbox_discovery import XboxDiscovery

            discovery = XboxDiscovery()
            local = await discovery.discover(use_cloud_first=False)
            if not local:
                return consoles
            by_live: Dict[str, str] = {}
            for x in local:
                lid = getattr(x, "live_id", "") or ""
                ip = getattr(x, "ip_address", "") or ""
                if lid and ip:
                    by_live[lid] = ip
            for c in consoles:
                if not c.ip_address and c.live_id in by_live:
                    c.ip_address = by_live[c.live_id]
                    self.logger.info("SSDP enrich %s -> %s", c.name, c.ip_address)
        except Exception as exc:
            self.logger.warning("SSDP enrich skipped: %s", exc)
        return consoles
