"""跨平台 LAN 工具（与 Xbox GSSV / PlayStation Chiaki 无关）。"""

from .network_util import (
    BLOCKED_SCAN_NETWORKS,
    fit_display_size,
    is_blocked_scan_ip,
    is_private_lan_ip,
    is_same_lan_segment,
    lan_segment_from_ip,
    pick_local_lan_ip,
    subnet_broadcast_from_ip,
)

__all__ = [
    "BLOCKED_SCAN_NETWORKS",
    "fit_display_size",
    "is_blocked_scan_ip",
    "is_private_lan_ip",
    "is_same_lan_segment",
    "lan_segment_from_ip",
    "pick_local_lan_ip",
    "subnet_broadcast_from_ip",
]
