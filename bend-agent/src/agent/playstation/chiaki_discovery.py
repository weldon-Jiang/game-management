"""
Chiaki PlayStation LAN UDP 发现（SRCH / HTTP-style 响应）。

参考 chiaki-ng lib/src/discovery.c：
- PS4: UDP 987, protocol 00020020
- PS5: UDP 9302, protocol 00030010
- 请求: SRCH * HTTP/1.1\\ndevice-discovery-protocol-version:{version}\\n
- 响应: HTTP/1.1 200 (ready) / 620 (standby) + 头字段
"""

from __future__ import annotations

import asyncio
import socket
import time
from typing import Dict, List, Optional, Tuple

from ..core.logger import get_logger
from ..lan.network_util import subnet_broadcast_from_ip
from .models import ChiakiDiscoveryHost

logger = get_logger("chiaki_discovery")

DISCOVERY_PORT_PS4 = 987
DISCOVERY_PORT_PS5 = 9302
PROTOCOL_VERSION_PS4 = "00020020"
PROTOCOL_VERSION_PS5 = "00030010"
BROADCAST_ADDR = "255.255.255.255"
DEFAULT_REGISTRATION_PORT = 9295

# Chiaki 本地 bind 端口范围（9303–9319）
LOCAL_BIND_PORT_MIN = 9303
LOCAL_BIND_PORT_MAX = 9319


def build_srch_packet(protocol_version: str) -> bytes:
    """构建 SRCH 广播包（含 Chiaki 约定的 null 终止符）。"""
    text = f"SRCH * HTTP/1.1\ndevice-discovery-protocol-version:{protocol_version}\n"
    return text.encode("utf-8") + b"\x00"


def parse_srch_response(data: bytes, source_ip: str) -> Optional[ChiakiDiscoveryHost]:
    """
    解析 SRCH 响应为 ChiakiDiscoveryHost。

    返回 None 表示非合法发现响应。
    """
    if not data:
        return None

    text = data.split(b"\x00", 1)[0].decode("utf-8", errors="replace")
    lines = text.split("\n")
    if not lines:
        return None

    status_line = lines[0].strip("\r")
    parts = status_line.split()
    if len(parts) < 2:
        return None

    try:
        status_code = int(parts[1])
    except ValueError:
        return None

    if status_code == 200:
        state = "ready"
    elif status_code == 620:
        state = "standby"
    else:
        state = "unknown"

    headers: Dict[str, str] = {}
    for line in lines[1:]:
        line = line.strip("\r")
        if not line or ":" not in line:
            continue
        key, value = line.split(":", 1)
        headers[key.strip().lower()] = value.strip()

    host_id = headers.get("host-id", "")
    if not host_id:
        return None

    request_port_raw = headers.get("host-request-port", "")
    try:
        host_request_port = int(request_port_raw) if request_port_raw else DEFAULT_REGISTRATION_PORT
    except ValueError:
        host_request_port = DEFAULT_REGISTRATION_PORT

    return ChiakiDiscoveryHost(
        ip_address=source_ip,
        host_id=host_id,
        host_name=headers.get("host-name", ""),
        host_type=headers.get("host-type", ""),
        system_version=headers.get("system-version", ""),
        device_discovery_protocol_version=headers.get(
            "device-discovery-protocol-version", ""
        ),
        host_request_port=host_request_port,
        state=state,
        running_app_titleid=headers.get("running-app-titleid", ""),
        running_app_name=headers.get("running-app-name", ""),
    )


def _discovery_targets(subnet_broadcast: Optional[str]) -> List[Tuple[str, int, str]]:
    """(addr, port, label) 列表：PS4 + PS5 双协议广播。"""
    targets: List[Tuple[str, int, str]] = [
        (BROADCAST_ADDR, DISCOVERY_PORT_PS4, "PS4-global"),
        (BROADCAST_ADDR, DISCOVERY_PORT_PS5, "PS5-global"),
    ]
    if subnet_broadcast:
        targets.append((subnet_broadcast, DISCOVERY_PORT_PS4, "PS4-subnet"))
        targets.append((subnet_broadcast, DISCOVERY_PORT_PS5, "PS5-subnet"))
    return targets


def _bind_discovery_socket() -> socket.socket:
    """绑定 Chiaki 本地端口范围；失败则回退系统分配。"""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if hasattr(socket, "SO_REUSEPORT"):
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)

    bound = False
    for port in range(LOCAL_BIND_PORT_MIN, LOCAL_BIND_PORT_MAX + 1):
        try:
            sock.bind(("", port))
            bound = True
            break
        except OSError:
            continue
    if not bound:
        sock.bind(("", 0))
    return sock


def _sync_discover(
    timeout_sec: float,
    subnet_broadcast: Optional[str],
) -> List[ChiakiDiscoveryHost]:
    """同步 UDP 发现（在线程池中调用）。"""
    hosts: Dict[str, ChiakiDiscoveryHost] = {}
    sock = _bind_discovery_socket()
    try:
        sock.settimeout(0.5)

        for addr, port, label in _discovery_targets(subnet_broadcast):
            if port == DISCOVERY_PORT_PS4:
                packet = build_srch_packet(PROTOCOL_VERSION_PS4)
            else:
                packet = build_srch_packet(PROTOCOL_VERSION_PS5)
            try:
                sock.sendto(packet, (addr, port))
                logger.debug("Chiaki SRCH sent to %s:%s (%s)", addr, port, label)
            except OSError as exc:
                logger.debug("Chiaki SRCH send failed %s:%s: %s", addr, port, exc)

        end_time = time.monotonic() + timeout_sec
        while time.monotonic() < end_time:
            remaining = end_time - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(min(0.5, remaining))
            try:
                data, addr = sock.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError as exc:
                logger.debug("Chiaki recv error: %s", exc)
                break

            ip = addr[0]
            parsed = parse_srch_response(data, ip)
            if not parsed:
                continue
            if ip in hosts:
                continue

            hosts[ip] = parsed
            logger.info(
                "Chiaki UDP 发现: %s @ %s (id=%s, %s, state=%s)",
                parsed.host_name or parsed.console_type,
                ip,
                parsed.host_id,
                parsed.console_type,
                parsed.state,
            )

    finally:
        sock.close()

    return list(hosts.values())


async def discover_chiaki_consoles(
    timeout_sec: float = 5.0,
    local_ip: Optional[str] = None,
    subnet_broadcast: Optional[str] = None,
) -> List[ChiakiDiscoveryHost]:
    """
    异步 Chiaki LAN UDP 发现。

    参数:
        timeout_sec: 收包总超时
        local_ip: 本机 LAN IP，用于推导子网广播
        subnet_broadcast: 显式子网广播，如 192.168.1.255
    """
    broadcast = subnet_broadcast or subnet_broadcast_from_ip(local_ip)
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _sync_discover(timeout_sec, broadcast),
    )
