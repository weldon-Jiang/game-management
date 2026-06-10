"""xHome login 响应中的 GSSV 区域 baseUri 解析与探测。"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from ..core.config import config
from ..core.logger import get_logger

logger = get_logger("gssv_region")

# XStreaming / 官方客户端常见 xHome 区域（baseUri 缺失时按序探测）
KNOWN_XHOME_REGION_URIS: Tuple[str, ...] = (
    "https://uks.core.gssv-play-prodxhome.xboxlive.com",
    "https://eus.core.gssv-play-prodxhome.xboxlive.com",
    "https://wus2.core.gssv-play-prodxhome.xboxlive.com",
    "https://japaneast.core.gssv-play-prodxhome.xboxlive.com",
    "https://koreacentral.core.gssv-play-prodxhome.xboxlive.com",
)


def extract_xhome_regions(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    从 xHome /v2/login/user 响应提取 regions 列表。

    官方结构：offeringSettings.regions（XStreaming 文档）。
    兼容旧字段：serverDetails.regions、顶层 regions。
    """
    if not isinstance(data, dict):
        return []

    offering = data.get("offeringSettings") or {}
    if isinstance(offering, dict):
        regions = offering.get("regions")
        if isinstance(regions, list) and regions:
            return [r for r in regions if isinstance(r, dict)]

    server_details = data.get("serverDetails") or {}
    if isinstance(server_details, dict):
        regions = server_details.get("regions")
        if isinstance(regions, list) and regions:
            return [r for r in regions if isinstance(r, dict)]

    regions = data.get("regions")
    if isinstance(regions, list):
        return [r for r in regions if isinstance(r, dict)]
    return []


def _region_sort_key(region: Dict[str, Any]) -> Tuple[int, int, str]:
    """优先 isDefault，其次 fallbackPriority 越大越优先。"""
    is_default = 1 if region.get("isDefault") else 0
    try:
        priority = int(region.get("fallbackPriority") or 0)
    except (TypeError, ValueError):
        priority = 0
    name = str(region.get("name") or "")
    return (is_default, priority, name)


def select_xhome_base_uri(
    data: Dict[str, Any],
    *,
    configured_uri: Optional[str] = None,
) -> Optional[str]:
    """
    从 xHome 响应选择 GSSV baseUri。

    1. 配置项 gssv.base_uri / lan_stream.gssv_base_uri 强制覆盖
    2. offeringSettings.regions 中 isDefault + baseUri
    3. 任意带 baseUri 的 region（按 fallbackPriority 排序）
    """
    forced = (
        configured_uri
        or config.get("gssv.base_uri")
        or config.get("lan_stream.gssv_base_uri")
    )
    if forced:
        return str(forced).strip().rstrip("/")

    regions = extract_xhome_regions(data)
    if not regions:
        return None

    for region in sorted(regions, key=_region_sort_key, reverse=True):
        uri = region.get("baseUri")
        if uri:
            return str(uri).rstrip("/")
    return None


async def probe_gssv_base_uri(gs_token: str, candidate_uris: List[str]) -> Optional[str]:
    """
    用 gsToken 对候选 baseUri 发 GET /v6/servers/home，返回首个 HTTP 200 的地址。
    """
    import aiohttp

    from .device_info import build_x_ms_device_info

    if not gs_token or not candidate_uris:
        return None

    headers = {
        "Authorization": f"Bearer {gs_token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-xbl-contract-version": "1",
        "X-MS-Device-Info": build_x_ms_device_info(),
    }

    seen = set()
    async with aiohttp.ClientSession() as session:
        for raw in candidate_uris:
            uri = str(raw or "").strip().rstrip("/")
            if not uri or uri in seen:
                continue
            seen.add(uri)
            url = f"{uri}/v6/servers/home"
            try:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=8),
                ) as resp:
                    if resp.status == 200:
                        logger.info("GSSV 区域探测成功: %s", uri)
                        return uri
                    logger.debug("GSSV 区域探测 %s -> HTTP %s", uri, resp.status)
            except Exception as exc:
                logger.debug("GSSV 区域探测 %s 失败: %s", uri, exc)
    return None


async def resolve_xhome_base_uri(
    data: Dict[str, Any],
    gs_token: str,
) -> Optional[str]:
    """解析 + 必要时探测，得到可用 GSSV baseUri。"""
    uri = select_xhome_base_uri(data)
    if uri:
        return uri

    regions = extract_xhome_regions(data)
    candidates = [str(r.get("baseUri", "")).rstrip("/") for r in regions if r.get("baseUri")]
    for known in KNOWN_XHOME_REGION_URIS:
        if known not in candidates:
            candidates.append(known)

    probed = await probe_gssv_base_uri(gs_token, candidates)
    if probed:
        logger.info("xHome 响应无 baseUri，已通过区域探测选定: %s", probed)
    return probed
