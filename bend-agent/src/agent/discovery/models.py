"""发现层 DTO（独立文件以避免循环导入）。"""

from dataclasses import dataclass


@dataclass
class ConsoleTarget:
    id: str
    name: str
    server_id: str
    live_id: str = ""
    ip_address: str = ""
    mac_address: str = ""
    power_state: str = ""
    console_type: str = ""
    play_path: str = ""
