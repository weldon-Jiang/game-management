"""本地网络辅助 — 避免扫描代理/TUN 假 IP 段。"""

import ipaddress
import socket
from typing import List, Optional, Tuple

# Clash/sing-box 等代理常用 198.18.0.0/15 作为 fake-ip。
BLOCKED_SCAN_NETWORKS = (
    ipaddress.ip_network("198.18.0.0/15"),
    ipaddress.ip_network("0.0.0.0/8"),
)


def is_blocked_scan_ip(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
        return any(addr in net for net in BLOCKED_SCAN_NETWORKS)
    except ValueError:
        return True


def is_private_lan_ip(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_private
    except ValueError:
        return False


def pick_local_lan_ip() -> Optional[str]:
    """
    优先 RFC1918 网卡地址；仅当为私网时才回退到路由探测。
    """
    candidates: List[str] = []

    try:
        import netifaces  # type: ignore

        for iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface).get(netifaces.AF_INET, [])
            for entry in addrs:
                ip = entry.get("addr")
                if ip and is_private_lan_ip(ip) and not is_blocked_scan_ip(ip):
                    candidates.append(ip)
    except Exception:
        pass

    if candidates:
        for preferred in ("192.168.", "10.", "172."):
            for ip in candidates:
                if ip.startswith(preferred):
                    return ip
        return candidates[0]

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
        if ip and not is_blocked_scan_ip(ip):
            return ip
    except Exception:
        pass
    return None


def fit_display_size(
    screen_w: int,
    screen_h: int,
    video_w: int,
    video_h: int,
    *,
    max_w: int,
    max_h: int,
    margin: int = 48,
) -> Tuple[int, int]:
    """计算适配屏幕的窗口客户区尺寸，并保持宽高比。"""
    if video_w <= 0 or video_h <= 0:
        return max_w, max_h

    avail_w = max(320, min(max_w, screen_w - margin))
    avail_h = max(240, min(max_h, screen_h - margin))
    scale = min(avail_w / video_w, avail_h / video_h, 1.0)
    return max(320, int(video_w * scale)), max(240, int(video_h * scale))


def lan_segment_from_ip(ip: str) -> Optional[str]:
    """从 IPv4 提取 /24 网段键，如 192.168.1.10 → 192.168.1。"""
    if not ip:
        return None
    trimmed = ip.strip()
    if "/" in trimmed:
        trimmed = trimmed.split("/", 1)[0]
    parts = trimmed.split(".")
    if len(parts) != 4:
        return None
    try:
        for part in parts:
            octet = int(part)
            if octet < 0 or octet > 255:
                return None
    except ValueError:
        return None
    return f"{parts[0]}.{parts[1]}.{parts[2]}"


def is_same_lan_segment(ip_a: str, ip_b: str) -> bool:
    """判断两个 IPv4 是否处于同一 /24 网段。"""
    seg_a = lan_segment_from_ip(ip_a)
    seg_b = lan_segment_from_ip(ip_b)
    return seg_a is not None and seg_a == seg_b
