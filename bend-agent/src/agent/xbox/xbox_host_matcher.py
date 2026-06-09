"""
Xbox 主机智能匹配器
==================

云端 GSSV GET /v6/servers/home + SmartGlass UDP LAN 发现（0xDD01），
按 serverId/hardware_uuid 求交集；顺序与云端列表一致。
"""

import asyncio
import base64
from typing import Awaitable, Callable, List, Optional, Dict, Any, Set, TYPE_CHECKING
from dataclasses import dataclass, field
from enum import Enum

import aiohttp

from ..core.config import config
from ..core.logger import get_logger
from ..gssv.base_uri import normalize_gssv_base_uri
from ..task.task_context import AgentTaskContext
from ..gssv.device_info import build_x_ms_device_info
from ..lan.network_util import (
    is_blocked_scan_ip,
    is_private_lan_ip,
    pick_local_lan_ip,
    is_same_lan_segment,
)
from .smartglass_discovery import SmartGlassConsole, discover_smartglass_consoles, discover_smartglass_at

if TYPE_CHECKING:
    from ..api.platform_api_client import PlatformApiClient


class XboxMatchPriority(Enum):
    """Xbox 匹配优先级"""
    AUTHORIZED_ONLINE_POWERED = 1
    AUTHORIZED_ONLINE_STANDBY = 2
    AUTHORIZED_OFFLINE = 3
    UNAUTHORIZED = 99


@dataclass
class XboxInfo:
    """Xbox 主机信息（兼容 task_context.XboxInfo 扩展字段）"""
    id: str = ""
    name: str = ""
    ip_address: str = ""
    live_id: str = ""
    mac_address: str = ""
    device_id: str = ""
    port: int = 5050
    power_state: str = "Unknown"
    console_type: str = "Unknown"
    play_path: str = ""
    platform_host_id: str = ""


@dataclass
class XboxMatchResult:
    """Xbox 主机匹配结果"""
    xbox_info: Optional[XboxInfo] = None
    priority: XboxMatchPriority = XboxMatchPriority.UNAUTHORIZED
    is_authorized: bool = False
    is_local_online: bool = False
    is_powered_on: bool = False
    match_reason: str = ""
    success: bool = False
    error_code: str = ""
    error_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class XboxWakeupResult:
    """Xbox 唤醒结果"""
    success: bool
    xbox_info: XboxInfo
    wakeup_method: str
    attempts: int
    wait_time_seconds: float
    error_message: Optional[str] = None


class XboxHostMatcher:
    """
    Xbox 主机匹配器：GSSV 云端列表 + SmartGlass UDP LAN 发现，按 serverId 求交集。

    使用方式：
    matcher = XboxHostMatcher(gs_token)
    err = await matcher.discover_cloud_and_lan()
    intersections = matcher.build_intersection()
    """

    WAKUP_MAX_RETRIES = 2
    WAKUP_WAIT_SECONDS = 30
    WAKUP_CHECK_INTERVAL = 3
    DEFAULT_PLAY_PATH = "v5/sessions/home/play"
    STANDBY_POWER_STATES = frozenset({"Standby", "ConnectedStandby", "Off"})
    LAN_PLATFORM = "xbox"

    def __init__(
        self,
        gs_token: str,
        gssv_base_uri: Optional[str] = None,
        platform_client: Optional["PlatformApiClient"] = None,
    ):
        self.logger = get_logger('xbox_matcher')
        self._gs_token = gs_token
        self._gssv_base_uri = normalize_gssv_base_uri(gssv_base_uri)
        self._platform_client = platform_client
        self._authorized_xboxes: List[XboxInfo] = []
        self._local_xboxes: Dict[str, XboxInfo] = {}
        self._lan_certificates: Dict[str, bytes] = {}

    @staticmethod
    def _is_powered_on(power_state: str) -> bool:
        return (power_state or "").strip() == "On"

    @classmethod
    def _can_wakeup(cls, power_state: str) -> bool:
        return (power_state or "").strip() in cls.STANDBY_POWER_STATES

    async def discover_authorized_xboxes(self) -> List[XboxInfo]:
        """通过云端 API 获取账号授权的 Xbox 主机列表"""
        self.logger.info("正在获取云端授权的 Xbox 主机列表...")

        try:
            headers = {
                'Authorization': f'Bearer {self._gs_token}',
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'x-xbl-contract-version': '1',
                'X-MS-Device-Info': build_x_ms_device_info(),
            }

            url = f"{self._gssv_base_uri}/v6/servers/home"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get('results', [])

                        self._authorized_xboxes = []
                        for server in results:
                            server_id = server.get('serverId', '')
                            play_path = server.get('playPath', '') or self.DEFAULT_PLAY_PATH
                            xbox_info = XboxInfo(
                                id=server_id,
                                device_id=server_id,
                                name=server.get('deviceName', 'Xbox'),
                                ip_address="",
                                port=5050,
                                live_id=server.get('liveId', '') or server_id,
                                power_state=server.get('powerState', 'Unknown'),
                                console_type=server.get('consoleType', 'Unknown'),
                                play_path=play_path,
                            )
                            self._authorized_xboxes.append(xbox_info)

                        self.logger.info(f"✓ 获取到 {len(self._authorized_xboxes)} 台授权 Xbox 主机")

                        for xbox in self._authorized_xboxes:
                            self.logger.info(
                                f"  - {xbox.name} ({xbox.device_id[:16]}...): "
                                f"Power={xbox.power_state}, Type={xbox.console_type}, "
                                f"PlayPath={xbox.play_path}"
                            )

                        return self._authorized_xboxes

                    text = await resp.text()
                    self.logger.error(f"获取授权 Xbox 列表失败: {resp.status} - {text}")
                    return []

        except Exception as e:
            self.logger.error(f"获取授权 Xbox 列表异常: {e}", exc_info=True)
            return []

    async def discover_local_xboxes(self) -> Dict[str, XboxInfo]:
        """
        SmartGlass UDP 发现局域网 Xbox；优先读平台 Redis 缓存（同商户同 /24）。

        缓存未命中时再发 UDP 广播，成功后回写平台供同 LAN 其他 Agent/账号复用。
        """
        self.logger.info("SmartGlass UDP 发现局域网 Xbox...")
        self._local_xboxes = {}
        self._lan_certificates = {}

        local_ip = pick_local_lan_ip()
        if is_blocked_scan_ip(local_ip or ""):
            self.logger.warning("SmartGlass UDP 跳过：本机不在真实 LAN 网段")
            return {}

        if local_ip and await self._load_from_platform_lan_cache(local_ip):
            return self._local_xboxes

        timeout = float(config.get("discovery.smartglass_udp_timeout_sec", 5))
        subnet_broadcast: Optional[str] = None
        if local_ip:
            parts = local_ip.split(".")
            if len(parts) == 4:
                subnet_broadcast = f"{parts[0]}.{parts[1]}.{parts[2]}.255"

        consoles: List[SmartGlassConsole] = []
        try:
            consoles = await discover_smartglass_consoles(
                timeout_sec=timeout,
                subnet_broadcast=subnet_broadcast,
            )
        except Exception as exc:
            self.logger.error("SmartGlass UDP 发现异常: %s", exc, exc_info=True)
            return {}

        self._ingest_smartglass_consoles(consoles)

        if local_ip and consoles:
            await self._report_lan_to_platform(local_ip, consoles)

        self.logger.info("✓ SmartGlass UDP 发现 %s 台", len(self._local_xboxes))
        return self._local_xboxes

    def _ingest_smartglass_consoles(self, consoles: List[SmartGlassConsole]) -> None:
        for console in consoles:
            xbox = self._from_smartglass_console(console)
            if xbox is None:
                continue
            self._local_xboxes[xbox.device_id] = xbox
            if console.certificate:
                self._lan_certificates[xbox.device_id] = console.certificate
            self.logger.info(
                "  - %s @ %s (uuid=%s)",
                xbox.name,
                xbox.ip_address,
                console.hardware_uuid,
            )

    async def _load_from_platform_lan_cache(self, local_ip: str) -> bool:
        """读取平台 LAN 缓存；命中且同网段则填充 _local_xboxes。"""
        if not config.get("discovery.platform_lan_cache_enabled", True):
            return False
        if self._platform_client is None:
            return False
        if not is_private_lan_ip(local_ip):
            return False

        cache = await self._platform_client.get_lan_discovery_cache(local_ip, self.LAN_PLATFORM)
        if not cache or not cache.get("hit"):
            reason = (cache or {}).get("reason", "MISS")
            self.logger.info("平台 LAN 缓存未命中 (%s)，将执行 UDP 发现", reason)
            return False

        consoles = cache.get("consoles") or []
        if not consoles:
            return False

        reporter_ip = cache.get("reporterLocalIp") or ""
        age_sec = cache.get("ageSec")
        self.logger.info(
            "平台 LAN 缓存命中 segment=%s consoles=%s ageSec=%s reporter=%s",
            cache.get("lanSegment"),
            len(consoles),
            age_sec,
            reporter_ip,
        )

        cert_timeout = float(config.get("discovery.smartglass_udp_timeout_sec", 5))
        for entry in consoles:
            ip = entry.get("ipAddress") or entry.get("ip")
            if not ip or not is_same_lan_segment(local_ip, ip):
                self.logger.warning("忽略缓存中非本网段主机 ip=%s local=%s", ip, local_ip)
                continue

            xbox = self._from_cache_entry(entry)
            if xbox is None:
                continue
            self._local_xboxes[xbox.device_id] = xbox

            cert_b64 = entry.get("certificateB64") or entry.get("certificate_b64")
            if cert_b64:
                try:
                    self._lan_certificates[xbox.device_id] = base64.b64decode(cert_b64)
                except Exception as exc:
                    self.logger.warning("缓存证书解码失败 %s: %s", xbox.device_id, exc)
            elif ip:
                directed = await discover_smartglass_at(ip, timeout_sec=min(3.0, cert_timeout))
                if directed and directed.certificate:
                    self._lan_certificates[xbox.device_id] = directed.certificate

            self.logger.info("  [cache] %s @ %s", xbox.name, xbox.ip_address)

        if self._local_xboxes:
            self.logger.info("✓ 平台 LAN 缓存加载 %s 台（同 /24 网段）", len(self._local_xboxes))
            return True
        return False

    @staticmethod
    def _from_cache_entry(entry: Dict[str, Any]) -> Optional[XboxInfo]:
        server_id = (
            entry.get("serverId")
            or entry.get("deviceId")
            or entry.get("device_id")
        )
        ip = entry.get("ipAddress") or entry.get("ip")
        if not server_id or not ip:
            return None
        device_id = str(server_id).strip().upper()
        if not device_id.startswith("XBOX-"):
            device_id = f"XBOX-{device_id}"
        console_type = entry.get("consoleType") or "Xbox Unknown"
        return XboxInfo(
            id=device_id,
            device_id=device_id,
            name=entry.get("name") or f"Xbox ({ip})",
            ip_address=ip,
            port=int(entry.get("port") or 5050),
            live_id=device_id,
            power_state="On",
            console_type=console_type,
        )

    async def _report_lan_to_platform(
        self,
        local_ip: str,
        consoles: List[SmartGlassConsole],
    ) -> None:
        if self._platform_client is None:
            return
        if not config.get("discovery.platform_lan_cache_enabled", True):
            return

        payload: List[Dict[str, Any]] = []
        for console in consoles:
            xbox = self._from_smartglass_console(console)
            if xbox is None:
                continue
            item: Dict[str, Any] = {
                "serverId": xbox.device_id,
                "name": xbox.name,
                "ipAddress": xbox.ip_address,
                "port": xbox.port,
                "liveId": xbox.live_id,
                "consoleType": xbox.console_type,
            }
            if console.certificate:
                item["certificateB64"] = base64.b64encode(console.certificate).decode("ascii")
            payload.append(item)

        if not payload:
            return

        ttl = int(config.get("discovery.cache_ttl_sec", 90))
        result = await self._platform_client.report_lan_discovery(
            local_ip,
            payload,
            ttl_sec=ttl,
            platform=self.LAN_PLATFORM,
        )
        if result and result.get("accepted"):
            self.logger.info(
                "LAN 发现已上报平台 segment=%s consoles=%s cached=%s ttl=%s",
                result.get("lanSegment"),
                result.get("consoleCount"),
                result.get("cached"),
                result.get("ttlSec"),
            )

    @staticmethod
    def _from_smartglass_console(console: SmartGlassConsole) -> Optional[XboxInfo]:
        """将 Discovery Response 转为 XboxInfo；无 hardware_uuid 则丢弃。"""
        hardware_id = (console.hardware_uuid or "").strip()
        if not hardware_id or not console.ip_address:
            return None
        device_id = hardware_id.upper()
        if not device_id.startswith("XBOX-"):
            device_id = f"XBOX-{device_id}"
        console_type = "Xbox One" if console.console_type == 0x01 else "Xbox Unknown"
        return XboxInfo(
            id=device_id,
            device_id=device_id,
            name=console.console_name or f"Xbox ({console.ip_address})",
            ip_address=console.ip_address,
            port=5050,
            live_id=device_id,
            power_state="On",
            console_type=console_type,
        )

    def get_smartglass_certificate(self, device_id: str) -> Optional[bytes]:
        return self._lan_certificates.get(device_id)

    async def discover_cloud_and_lan(self) -> Optional[XboxMatchResult]:
        """
        并行云端 + LAN 发现；失败返回 XboxMatchResult，成功返回 None。
        """
        self.logger.info("=" * 60)
        self.logger.info("Xbox 发现：GSSV 云端 + SmartGlass UDP")
        self.logger.info("=" * 60)

        await asyncio.gather(
            self.discover_authorized_xboxes(),
            self.discover_local_xboxes(),
        )

        if not self._authorized_xboxes:
            return XboxMatchResult(
                success=False,
                match_reason="云端未发现已授权的 Xbox 主机",
                error_code="CLOUD_NO_HOST",
                error_details={
                    "cloud_authorized_count": 0,
                    "suggestion": "请在 Xbox 应用中添加并授权此流媒体账号",
                },
            )

        if not self._local_xboxes:
            return XboxMatchResult(
                success=False,
                is_authorized=True,
                match_reason="局域网 SmartGlass UDP 未发现任何 Xbox 主机",
                error_code="LAN_NO_CONSOLE",
                error_details={
                    "cloud_authorized_count": len(self._authorized_xboxes),
                    "suggestion": "确认 Agent 与 Xbox 同网段、主机已开机且 UDP 5050 可达",
                },
            )

        intersections = self.build_intersection()
        if not intersections:
            return XboxMatchResult(
                success=False,
                is_authorized=True,
                is_local_online=True,
                match_reason="云端授权与局域网发现无交集",
                error_code="NO_INTERSECTION",
                error_details={
                    "cloud_authorized_count": len(self._authorized_xboxes),
                    "lan_discovered_count": len(self._local_xboxes),
                    "cloud_hosts": [
                        {"id": x.device_id, "name": x.name} for x in self._authorized_xboxes
                    ],
                    "lan_hosts": [
                        {"id": x.device_id, "name": x.name, "ip": x.ip_address}
                        for x in self._local_xboxes.values()
                    ],
                    "suggestion": "确认授权主机与 Agent 在同一局域网",
                },
            )

        self.logger.info("✓ 交集 %s 台（按云端顺序）", len(intersections))
        return None

    def build_intersection(self) -> List[XboxInfo]:
        """GSSV 授权 ∩ SmartGlass LAN，顺序与云端列表一致。"""
        intersections: List[XboxInfo] = []
        for cloud in self._authorized_xboxes:
            local = self._find_local_for_cloud(cloud)
            if local is None:
                continue
            merged = self._merge_cloud_local(cloud, local)
            if merged.ip_address:
                intersections.append(merged)
        return intersections

    @staticmethod
    def normalize_server_id(server_id: str) -> str:
        """统一 GSSV serverId 格式（XBOX- 前缀 + 大写）。"""
        normalized = (server_id or "").strip().upper()
        if not normalized:
            return ""
        if not normalized.startswith("XBOX-"):
            normalized = f"XBOX-{normalized}"
        return normalized

    def build_candidates(self, context: AgentTaskContext) -> List[XboxInfo]:
        """
        在交集基础上按平台下发的主机约束过滤候选。

        - assigned_xbox：按 serverId / IP 精确匹配
        - platform_xbox_hosts：自动匹配时限定商户绑定列表
        - auto_match_host=False 且无指定：返回空
        """
        intersections = self.build_intersection()
        if not intersections:
            return []

        assigned = context.assigned_xbox
        if assigned and (assigned.id or assigned.ip_address):
            matched = self._filter_assigned(intersections, assigned)
            if matched:
                return self._attach_platform_host_ids(matched, context.platform_xbox_hosts)
            self.logger.warning(
                "指定 Xbox 主机未在 GSSV∩LAN 交集: id=%s ip=%s",
                assigned.id,
                assigned.ip_address,
            )
            return []

        bound_hosts = context.platform_xbox_hosts or []
        if bound_hosts:
            filtered = self._filter_bound_hosts(intersections, bound_hosts)
            if filtered:
                return self._attach_platform_host_ids(filtered, bound_hosts)
            self.logger.warning("绑定主机列表与 GSSV∩LAN 交集无匹配")
            return []

        if not context.auto_match_host:
            return []

        return intersections

    def _filter_assigned(
        self,
        consoles: List[XboxInfo],
        assigned,
    ) -> List[XboxInfo]:
        target_id = self.normalize_server_id(assigned.id or "")
        target_ip = (assigned.ip_address or "").strip()
        result: List[XboxInfo] = []
        for console in consoles:
            console_id = self.normalize_server_id(console.device_id or console.id or "")
            if target_id and console_id == target_id:
                result.append(console)
            elif target_ip and console.ip_address == target_ip:
                result.append(console)
        return result

    def _filter_bound_hosts(
        self,
        consoles: List[XboxInfo],
        bound_hosts: List[Dict[str, Any]],
    ) -> List[XboxInfo]:
        allowed_ids: set = set()
        allowed_ips: set = set()
        for entry in bound_hosts:
            xbox_id = entry.get("xboxId") or entry.get("xbox_id") or entry.get("id") or ""
            normalized = self.normalize_server_id(str(xbox_id))
            if normalized:
                allowed_ids.add(normalized)
            ip = (entry.get("ipAddress") or entry.get("ip_address") or "").strip()
            if ip:
                allowed_ips.add(ip)

        result: List[XboxInfo] = []
        for console in consoles:
            console_id = self.normalize_server_id(console.device_id or console.id or "")
            if console_id in allowed_ids:
                result.append(console)
            elif console.ip_address in allowed_ips:
                result.append(console)
        return result

    @staticmethod
    def _attach_platform_host_ids(
        consoles: List[XboxInfo],
        bound_hosts: List[Dict[str, Any]],
    ) -> List[XboxInfo]:
        """将平台 xbox_host 表主键写入 platform_host_id，供租约/锁定使用。"""
        if not bound_hosts:
            return consoles

        id_by_server: Dict[str, str] = {}
        for entry in bound_hosts:
            platform_id = str(entry.get("id") or "").strip()
            server_key = XboxHostMatcher.normalize_server_id(
                str(entry.get("xboxId") or entry.get("xbox_id") or entry.get("id") or "")
            )
            if platform_id and server_key:
                id_by_server[server_key] = platform_id

        for console in consoles:
            server_key = XboxHostMatcher.normalize_server_id(console.device_id or console.id or "")
            if server_key in id_by_server:
                console.platform_host_id = id_by_server[server_key]
        return consoles

    async def _ensure_powered_on(
        self,
        xbox: XboxInfo,
        wakeup: bool,
        wakeup_timeout: int,
    ) -> Dict[str, Any]:
        """确保 Xbox 处于开机状态。"""
        if self._is_powered_on(xbox.power_state):
            return {"ok": True}

        if not self._can_wakeup(xbox.power_state):
            return {"ok": True}

        if not wakeup:
            self.logger.warning(f"Xbox {xbox.name} 处于 {xbox.power_state}，但唤醒功能已禁用")
            return {
                "ok": False,
                "result": XboxMatchResult(
                    xbox_info=None,
                    priority=XboxMatchPriority.UNAUTHORIZED,
                    is_authorized=True,
                    is_local_online=False,
                    is_powered_on=False,
                    success=False,
                    match_reason="Xbox 处于待机/关机状态，但唤醒功能已禁用",
                    error_code="WAKEUP_DISABLED",
                    error_details={"xbox_name": xbox.name, "power_state": xbox.power_state}
                )
            }

        self.logger.info(f"Xbox {xbox.name} 处于 {xbox.power_state}，尝试云端唤醒...")
        wakeup_result = await self._wakeup_xbox(xbox, timeout=wakeup_timeout)
        if wakeup_result.success:
            xbox.power_state = "On"
            self.logger.info(f"✓ Xbox 唤醒成功: {xbox.name}")
            return {"ok": True}

        self.logger.error(f"✗ 唤醒失败: {wakeup_result.error_message}")
        return {
            "ok": False,
            "result": XboxMatchResult(
                xbox_info=None,
                priority=XboxMatchPriority.UNAUTHORIZED,
                is_authorized=True,
                is_local_online=False,
                is_powered_on=False,
                success=False,
                match_reason=f"唤醒 Xbox 失败: {wakeup_result.error_message}",
                error_code="WAKEUP_FAILED",
                error_details={
                    "xbox_name": xbox.name,
                    "error_message": wakeup_result.error_message,
                }
            )
        }

    def _build_success_result(
        self,
        xbox: XboxInfo,
        priority: XboxMatchPriority,
        reason: str,
        is_powered_on: bool,
        is_local_online: bool = False,
    ) -> XboxMatchResult:
        """构建成功的匹配结果并打印日志。"""
        self.logger.info("")
        self.logger.info("=" * 60)
        self.logger.info("Xbox 主机匹配结果")
        self.logger.info("=" * 60)
        self.logger.info(f"✓ 选择: {xbox.name}")
        self.logger.info(f"  设备 ID: {(xbox.device_id or xbox.id or '')[:16]}...")
        self.logger.info(f"  LAN IP: {xbox.ip_address or 'N/A'}")
        self.logger.info(f"  主机类型: {xbox.console_type}")
        self.logger.info(f"  电源状态: {xbox.power_state}")
        self.logger.info(f"  PlayPath: {xbox.play_path}")
        self.logger.info(f"  匹配原因: {reason}")
        self.logger.info("=" * 60)
        return XboxMatchResult(
            xbox_info=xbox,
            priority=priority,
            is_authorized=True,
            is_local_online=is_local_online,
            is_powered_on=is_powered_on,
            success=True,
            match_reason=reason,
        )

    @staticmethod
    def _normalize_id(value: str) -> str:
        return (value or "").strip().lower()

    def _id_keys(self, xbox: XboxInfo) -> Set[str]:
        """收集可用于 GSSV/LAN/平台对齐的 ID 键（不含平台 UUID）。"""
        keys: Set[str] = set()
        for raw in (xbox.device_id, xbox.live_id, xbox.mac_address):
            normalized = self._normalize_id(raw)
            if not normalized:
                continue
            keys.add(normalized)
            # SmartGlass Hardware UUID 与 GSSV serverId / XBOX- 前缀形式互通
            if normalized.startswith("xbox-"):
                keys.add(normalized[5:])
            elif len(normalized.replace("-", "")) >= 32:
                keys.add(f"xbox-{normalized}")
        return keys

    def _cloud_matches_local(self, cloud: XboxInfo, local: XboxInfo) -> bool:
        cloud_keys = self._id_keys(cloud)
        local_keys = self._id_keys(local)
        if cloud_keys & local_keys:
            return True
        cloud_name = self._normalize_id(cloud.name)
        local_name = self._normalize_id(local.name)
        if cloud_name and cloud_name == local_name:
            return True
        return False

    def _find_local_for_cloud(self, cloud: XboxInfo) -> Optional[XboxInfo]:
        for local in self._local_xboxes.values():
            if self._cloud_matches_local(cloud, local):
                return local
        return None

    def _merge_cloud_local(self, cloud: XboxInfo, local: XboxInfo) -> XboxInfo:
        return XboxInfo(
            id=cloud.id or cloud.device_id,
            device_id=cloud.device_id or cloud.id,
            name=cloud.name or local.name,
            ip_address=local.ip_address,
            live_id=cloud.live_id or local.live_id,
            mac_address=local.mac_address,
            port=local.port or cloud.port or 5050,
            power_state=cloud.power_state,
            console_type=cloud.console_type or local.console_type,
            play_path=cloud.play_path or self.DEFAULT_PLAY_PATH,
        )

    def _find_authorized_match(self, xbox: XboxInfo) -> Optional[XboxInfo]:
        """在云端授权列表中查找与给定 Xbox 匹配的条目（按 xboxId/liveId，不用平台 UUID）。"""
        candidates_id_keys = list(self._id_keys(xbox))
        assigned_name = self._normalize_id(xbox.name)

        for authorized in self._authorized_xboxes:
            authorized_keys = list(self._id_keys(authorized))
            if any(k in authorized_keys for k in candidates_id_keys):
                return authorized
            if assigned_name and assigned_name == self._normalize_id(authorized.name):
                return authorized

        return None

    async def _wakeup_xbox(self, xbox: XboxInfo, timeout: int = 30) -> XboxWakeupResult:
        """通过云端 API 唤醒 Xbox 主机"""
        self.logger.info(f"开始唤醒 Xbox: {xbox.name} ({xbox.device_id})")

        start_time = asyncio.get_event_loop().time()
        attempts = 0
        last_error = None

        for attempt in range(self.WAKUP_MAX_RETRIES):
            attempts += 1
            self.logger.info(f"唤醒尝试 {attempt + 1}/{self.WAKUP_MAX_RETRIES}")

            success = await self._wakeup_via_api(xbox.device_id)
            if success:
                self.logger.info("✓ 云端 API 唤醒命令发送成功")
                self.logger.info(f"等待 Xbox 开机（最多 {timeout} 秒）...")

                if await self._wait_for_power_on(xbox.device_id, timeout):
                    elapsed = asyncio.get_event_loop().time() - start_time
                    return XboxWakeupResult(
                        success=True,
                        xbox_info=xbox,
                        wakeup_method="api",
                        attempts=attempts,
                        wait_time_seconds=elapsed,
                    )
                last_error = "等待开机超时"
            else:
                last_error = "唤醒命令发送失败"

        elapsed = asyncio.get_event_loop().time() - start_time
        return XboxWakeupResult(
            success=False,
            xbox_info=xbox,
            wakeup_method="none",
            attempts=attempts,
            wait_time_seconds=elapsed,
            error_message=last_error,
        )

    async def _wakeup_via_api(self, device_id: str) -> bool:
        """通过 Xbox Live API 唤醒"""
        try:
            headers = {
                'Authorization': f'Bearer {self._gs_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self._gssv_base_uri}/v6/servers/{device_id}/power"

            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    headers=headers,
                    json={"action": "on"},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        self.logger.debug(f"API 唤醒成功: {device_id}")
                        return True
                    text = await resp.text()
                    self.logger.warning(f"API 唤醒失败: {resp.status} - {text}")
                    return False

        except Exception as e:
            self.logger.warning(f"API 唤醒异常: {e}")
            return False

    async def _wait_for_power_on(self, device_id: str, timeout: int) -> bool:
        """等待 Xbox 开机"""
        self.logger.info(f"开始轮询检查电源状态（超时: {timeout}s）...")

        elapsed = 0
        while elapsed < timeout:
            power_state = await self._check_power_state(device_id)

            if power_state == 'On':
                self.logger.info(f"✓ Xbox 已开机！（耗时: {elapsed}s）")
                return True

            self.logger.debug(f"当前电源状态: {power_state}，等待中... ({elapsed}s/{timeout}s)")

            await asyncio.sleep(self.WAKUP_CHECK_INTERVAL)
            elapsed += self.WAKUP_CHECK_INTERVAL

        self.logger.warning(f"等待开机超时（{timeout}s）")
        return False

    async def _check_power_state(self, device_id: str) -> str:
        """检查 Xbox 电源状态"""
        try:
            headers = {
                'Authorization': f'Bearer {self._gs_token}',
                'Content-Type': 'application/json',
                'x-xbl-contract-version': '1'
            }

            url = f"{self._gssv_base_uri}/v6/servers/{device_id}"

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('powerState', 'Unknown')
                    return 'Unknown'

        except Exception as e:
            self.logger.debug(f"检查电源状态失败: {e}")
            return 'Unknown'

    def get_authorized_xboxes_summary(self) -> List[Dict[str, Any]]:
        """获取授权 Xbox 主机摘要"""
        return [
            {
                'device_id': xbox.device_id,
                'name': xbox.name,
                'power_state': xbox.power_state,
                'console_type': xbox.console_type,
                'play_path': xbox.play_path,
            }
            for xbox in self._authorized_xboxes
        ]
