"""PlayStation 发现/串流数据模型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class PlayStationConsole:
    """局域网 PlayStation 主机摘要（平台缓存与 Step2 共用）。"""

    device_id: str
    name: str
    ip_address: str
    port: int = 9295
    console_type: str = "PS5"
    power_state: str = "Unknown"
    system_version: str = ""


@dataclass
class ChiakiDiscoveryHost:
    """Chiaki SRCH 响应解析结果（对标 chiaki_discovery_srch_response_parse）。"""

    ip_address: str
    host_id: str
    host_name: str = ""
    host_type: str = ""
    system_version: str = ""
    device_discovery_protocol_version: str = ""
    host_request_port: int = 9295
    state: str = "unknown"  # ready / standby / unknown
    running_app_titleid: str = ""
    running_app_name: str = ""

    @property
    def is_ps5(self) -> bool:
        return self.device_discovery_protocol_version == "00030010"

    @property
    def console_type(self) -> str:
        return "PS5" if self.is_ps5 else "PS4"
