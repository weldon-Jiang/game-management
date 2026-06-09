"""PlayStation Agent 模块（Chiaki 发现 / 串流，与 xbox/ 物理隔离）。"""

from .chiaki_connect import ChiakiConnectResult, connect_playstation_lan, disconnect_playstation_session
from .chiaki_discovery import discover_chiaki_consoles
from .context_mapper import ps_console_to_task_context
from .models import ChiakiDiscoveryHost, PlayStationConsole
from .pipeline_diagnostic import pipeline_diagnostic_from_context
from .ps_console_lease import (
    is_host_occupied_by_device_id,
    release_device_id,
    try_acquire_device_id,
)
from .ps_host_matcher import PsHostMatcher, PsMatchResult
from .ps_lan_discovery import discover_playstation_lan, report_playstation_lan_to_platform
from .ps_stream_controller import PsStreamController
from .step2_flow import discover_and_match_playstation_hosts

__all__ = [
    "ChiakiConnectResult",
    "ChiakiDiscoveryHost",
    "PlayStationConsole",
    "PsHostMatcher",
    "PsMatchResult",
    "PsStreamController",
    "connect_playstation_lan",
    "disconnect_playstation_session",
    "discover_and_match_playstation_hosts",
    "discover_chiaki_consoles",
    "discover_playstation_lan",
    "is_host_occupied_by_device_id",
    "pipeline_diagnostic_from_context",
    "ps_console_to_task_context",
    "release_device_id",
    "report_playstation_lan_to_platform",
    "try_acquire_device_id",
]
