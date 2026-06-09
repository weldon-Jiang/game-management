"""
PlayStation LAN 发现（占位）。

按 platform=playstation 走平台 Redis 缓存；UDP 发现协议待 Chiaki 集成后实现。
选错账号类型时按正常流程在 Step2 报错（LAN 无主机 / 串流未开放）。
"""

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from ..core.config import config
from ..core.logger import get_logger
from ..gssv.network_util import (
    is_blocked_scan_ip,
    is_private_lan_ip,
    is_same_lan_segment,
    pick_local_lan_ip,
)

if TYPE_CHECKING:
    from ..api.platform_api_client import PlatformApiClient

logger = get_logger("ps_lan_discovery")

LAN_PLATFORM = "playstation"


@dataclass
class PlayStationConsole:
    """局域网 PlayStation 主机摘要。"""

    device_id: str
    name: str
    ip_address: str
    port: int = 9295
    console_type: str = "PS5"


async def discover_playstation_lan(
    platform_client: Optional["PlatformApiClient"] = None,
) -> Dict[str, PlayStationConsole]:
    """
    PS LAN 发现：优先平台缓存，未命中则 UDP（尚未实现）。

    返回 device_id → PlayStationConsole 映射。
    """
    local_ip = pick_local_lan_ip()
    result: Dict[str, PlayStationConsole] = {}

    if is_blocked_scan_ip(local_ip or ""):
        logger.warning("PS LAN 发现跳过：本机不在真实 LAN 网段")
        return result

    if (
        local_ip
        and platform_client
        and config.get("discovery.platform_lan_cache_enabled", True)
        and is_private_lan_ip(local_ip)
    ):
        cached = await _load_from_platform_cache(platform_client, local_ip)
        if cached:
            return cached

    # TODO: Chiaki / PS Remote Play UDP 注册发现
    logger.info("PlayStation UDP LAN 发现尚未实现，未发现主机")
    return result


async def report_playstation_lan_to_platform(
    platform_client: Optional["PlatformApiClient"],
    local_ip: str,
    consoles: Dict[str, PlayStationConsole],
) -> None:
    """将 PS LAN 发现结果上报平台（Redis + upsert xbox_host）。"""
    if not platform_client or not local_ip or not consoles:
        return
    if not config.get("discovery.platform_lan_cache_enabled", True):
        return

    payload: List[Dict[str, Any]] = []
    for console in consoles.values():
        payload.append({
            "serverId": console.device_id,
            "name": console.name,
            "ipAddress": console.ip_address,
            "port": console.port,
            "consoleType": console.console_type,
        })

    ttl = int(config.get("discovery.cache_ttl_sec", 90))
    result = await platform_client.report_lan_discovery(
        local_ip,
        payload,
        ttl_sec=ttl,
        platform=LAN_PLATFORM,
    )
    if result and result.get("accepted"):
        logger.info(
            "PS LAN 发现已上报平台 segment=%s consoles=%s cached=%s",
            result.get("lanSegment"),
            result.get("consoleCount"),
            result.get("cached"),
        )


async def _load_from_platform_cache(
    platform_client: "PlatformApiClient",
    local_ip: str,
) -> Dict[str, PlayStationConsole]:
    cache = await platform_client.get_lan_discovery_cache(local_ip, LAN_PLATFORM)
    if not cache or not cache.get("hit"):
        reason = (cache or {}).get("reason", "MISS")
        logger.info("平台 PS LAN 缓存未命中 (%s)，将尝试 UDP 发现", reason)
        return {}

    consoles = cache.get("consoles") or []
    result: Dict[str, PlayStationConsole] = {}
    for entry in consoles:
        ip = entry.get("ipAddress") or entry.get("ip")
        if not ip or not is_same_lan_segment(local_ip, ip):
            continue
        device_id = (
            entry.get("serverId")
            or entry.get("deviceId")
            or entry.get("device_id")
        )
        if not device_id:
            continue
        console = PlayStationConsole(
            device_id=str(device_id),
            name=entry.get("name") or f"PlayStation ({ip})",
            ip_address=ip,
            port=int(entry.get("port") or 9295),
            console_type=entry.get("consoleType") or "PS5",
        )
        result[console.device_id] = console
        logger.info("  [cache] %s @ %s", console.name, console.ip_address)

    if result:
        logger.info("✓ 平台 PS LAN 缓存加载 %s 台", len(result))
    return result
