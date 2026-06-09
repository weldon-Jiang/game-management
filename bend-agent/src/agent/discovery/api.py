"""
DiscoveryService — 云端主机列表 + SSDP 增强 + 电源路由。

重逻辑委托 step2；列表/解析使用 GSSV + power_manager。
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..auth.api import StreamingCredentials
from ..core.logger import get_logger
from ..task.task_context import AgentTaskContext, XboxInfo
from .models import ConsoleTarget


@dataclass
class ResolveResult:
    """主机目标及 step2 上下文（SmartGlass 会话须流入 step3）。"""

    console: ConsoleTarget
    context: AgentTaskContext


class DiscoveryService:
    def __init__(self):
        from .gssv_discovery import GssvDiscovery
        from .lan_enricher import LanEnricher
        from .power_manager import PowerManager

        self.logger = get_logger("discovery_service")
        self._gssv = GssvDiscovery()
        self._lan = LanEnricher()
        self._power = PowerManager()

    async def list_consoles(
        self,
        credentials: StreamingCredentials,
        *,
        use_cache: bool = True,
        ssdp_enrich: bool = True,
    ) -> List[ConsoleTarget]:
        consoles = await self._gssv.list_consoles(credentials)
        if ssdp_enrich and consoles:
            consoles = await self._lan.enrich(consoles)
        return consoles

    async def resolve_console(
        self,
        credentials: StreamingCredentials,
        task_id: str,
        assigned_xbox: Optional[Dict[str, Any]] = None,
        platform_xbox_hosts: Optional[List[Dict[str, Any]]] = None,
        auto_match_host: bool = True,
        check_cancel: Optional[Callable[[], bool]] = None,
        report_progress: Optional[Callable] = None,
    ) -> ResolveResult:
        from .console_resolver import resolve_console_target

        context = AgentTaskContext(
            task_id=task_id,
            streaming_account_id=credentials.streaming_account_id,
            streaming_account_email=credentials.email,
            streaming_account_password=credentials.password,
            streaming_account_auto_code=credentials.auto_code,
            auto_match_host=auto_match_host,
        )
        context.microsoft_tokens = credentials.microsoft_tokens
        context.xbox_tokens = credentials.xbox_tokens
        context.platform_xbox_hosts = list(platform_xbox_hosts or [])

        if assigned_xbox:
            platform_id = assigned_xbox.get("id", "")
            xbox_id = assigned_xbox.get("xboxId") or assigned_xbox.get("xbox_id") or ""
            context.assigned_xbox = XboxInfo(
                id=xbox_id or platform_id,
                platform_host_id=platform_id,
                name=assigned_xbox.get("name", "Xbox"),
                ip_address=assigned_xbox.get("ipAddress", "") or assigned_xbox.get("ip_address", ""),
                live_id=assigned_xbox.get("liveId", "") or assigned_xbox.get("live_id", ""),
                mac_address=assigned_xbox.get("macAddress", "") or assigned_xbox.get("mac_address", ""),
            )
            if not context.platform_xbox_hosts:
                context.platform_xbox_hosts = [assigned_xbox]

        async def _report(*args, **kwargs):
            if report_progress:
                await report_progress(*args, **kwargs)

        cancel = check_cancel or (lambda: False)
        resolved = await resolve_console_target(context, cancel, _report)
        if not resolved.success or not resolved.xbox_info:
            raise RuntimeError(resolved.message or "Console discovery failed")

        xb = resolved.xbox_info
        target = ConsoleTarget(
            id=xb.id,
            name=xb.name,
            server_id=xb.id,
            live_id=xb.live_id,
            ip_address=xb.ip_address,
            mac_address=xb.mac_address,
            power_state=xb.power_state,
            console_type=xb.console_type,
            play_path=xb.play_path,
        )

        return ResolveResult(console=target, context=context)

    async def list_bound_consoles(
        self,
        credentials: StreamingCredentials,
    ) -> List[ConsoleTarget]:
        return await self.list_consoles(credentials)
