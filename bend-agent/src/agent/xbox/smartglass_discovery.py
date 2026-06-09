"""
OpenXbox SmartGlass UDP 发现（Simple Message 0xDD00 / 0xDD01）。

参考：https://openxbox.org/smartglass-documentation/simple_message/
"""

from __future__ import annotations

import asyncio
import socket
import struct
from dataclasses import dataclass
from typing import List, Optional, Tuple

from ..core.logger import get_logger

logger = get_logger("smartglass_discovery")

# Simple Message packet types
PACKET_DISCOVERY_REQUEST = 0xDD00
PACKET_DISCOVERY_RESPONSE = 0xDD01
PACKET_POWER_ON_REQUEST = 0xDD02

# Client types (discovering client)
CLIENT_TYPE_XBOX_ONE = 0x01
CLIENT_TYPE_WINDOWS_DESKTOP = 0x03

SMARTGLASS_PORT = 5050
BROADCAST_ADDR = "255.255.255.255"
SSDP_MULTICAST_ADDR = "239.255.255.250"


@dataclass
class SmartGlassConsole:
    """SmartGlass Discovery Response 解析结果。"""

    ip_address: str
    console_name: str
    hardware_uuid: str
    console_type: int
    primary_device_flags: int
    certificate: bytes = b""


def _read_sg_string(data: bytes, offset: int) -> Tuple[str, int]:
    """读取 SGString：uint16 长度 + UTF-8 + null。"""
    if offset + 2 > len(data):
        return "", offset
    (length,) = struct.unpack_from(">H", data, offset)
    offset += 2
    end = offset + length
    if end > len(data):
        return "", offset
    text = data[offset:end].decode("utf-8", errors="replace")
    offset = end + 1  # null terminator
    return text, offset


def build_discovery_request(
    client_type: int = CLIENT_TYPE_WINDOWS_DESKTOP,
    min_version: int = 0,
    max_version: int = 2,
) -> bytes:
    """
    构建 Discovery Request（0xDD00）。

    Header（无 Protected Length）：Type + UnprotectedLen + Version(0)
    Payload：Flags(0) + ClientType + MinVer + MaxVer
    """
    payload = struct.pack(">IHHH", 0, client_type, min_version, max_version)
    header = struct.pack(">HHH", PACKET_DISCOVERY_REQUEST, len(payload), 0)
    return header + payload


def parse_discovery_response(data: bytes) -> Optional[SmartGlassConsole]:
    """
    解析 Discovery Response（0xDD01）。

    返回 None 表示非 Discovery Response 或数据不完整。
    """
    if len(data) < 6:
        return None

    packet_type, unprot_len, version = struct.unpack_from(">HHH", data, 0)
    if packet_type != PACKET_DISCOVERY_RESPONSE:
        return None

    payload_end = 6 + unprot_len
    if payload_end > len(data):
        return None

    payload = data[6:payload_end]
    if len(payload) < 6:
        return None

    primary_flags, console_type = struct.unpack_from(">IH", payload, 0)
    offset = 6
    console_name, offset = _read_sg_string(payload, offset)
    hardware_uuid, offset = _read_sg_string(payload, offset)

    certificate = b""
    if offset + 4 <= len(payload):
        (last_error,) = struct.unpack_from(">I", payload, offset)
        offset += 4
        if offset + 2 <= len(payload):
            (cert_len,) = struct.unpack_from(">H", payload, offset)
            offset += 2
            if cert_len > 0 and offset + cert_len <= len(payload):
                certificate = payload[offset : offset + cert_len]

    if not hardware_uuid and not console_name:
        return None

    return SmartGlassConsole(
        ip_address="",  # 由 recvfrom 填充
        console_name=console_name or "Xbox",
        hardware_uuid=hardware_uuid,
        console_type=console_type,
        primary_device_flags=primary_flags,
        certificate=certificate,
    )


def _discovery_targets(subnet_broadcast: Optional[str]) -> List[Tuple[str, int]]:
    """Discovery 发送目标：全局广播、SSDP 组播、子网广播。"""
    targets: List[Tuple[str, int]] = [
        (BROADCAST_ADDR, SMARTGLASS_PORT),
        (SSDP_MULTICAST_ADDR, SMARTGLASS_PORT),
    ]
    if subnet_broadcast:
        targets.append((subnet_broadcast, SMARTGLASS_PORT))
    return targets


def _sync_discover(
    timeout_sec: float,
    subnet_broadcast: Optional[str],
) -> List[SmartGlassConsole]:
    """同步 UDP 发现（在线程池中调用）。"""
    request = build_discovery_request()
    consoles: dict[str, SmartGlassConsole] = {}

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.bind(("", 0))
        sock.settimeout(0.5)

        for addr, port in _discovery_targets(subnet_broadcast):
            try:
                sock.sendto(request, (addr, port))
                logger.debug("SmartGlass Discovery sent to %s:%s", addr, port)
            except OSError as exc:
                logger.debug("SmartGlass Discovery send failed %s:%s: %s", addr, port, exc)

        import time

        end_time = time.monotonic() + timeout_sec
        while time.monotonic() < end_time:
            remaining = end_time - time.monotonic()
            if remaining <= 0:
                break
            sock.settimeout(min(0.5, remaining))
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError as exc:
                logger.debug("SmartGlass recv error: %s", exc)
                break

            parsed = parse_discovery_response(data)
            if not parsed:
                continue

            ip = addr[0]
            if ip in consoles:
                continue

            parsed.ip_address = ip
            consoles[ip] = parsed
            logger.info(
                "SmartGlass UDP 发现: %s @ %s (uuid=%s, type=0x%04x)",
                parsed.console_name,
                ip,
                parsed.hardware_uuid,
                parsed.console_type,
            )

    finally:
        sock.close()

    return list(consoles.values())


async def discover_smartglass_at(
    xbox_ip: str,
    timeout_sec: float = 3.0,
) -> Optional[SmartGlassConsole]:
    """向指定 IP 发送 Discovery Request 并等待 0xDD01。"""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _sync_discover_at(xbox_ip, timeout_sec),
    )


def _sync_discover_at(xbox_ip: str, timeout_sec: float) -> Optional[SmartGlassConsole]:
    request = build_discovery_request()
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.settimeout(timeout_sec)
        sock.bind(("", 0))
        sock.sendto(request, (xbox_ip, SMARTGLASS_PORT))
        import time

        end = time.monotonic() + timeout_sec
        while time.monotonic() < end:
            remaining = end - time.monotonic()
            sock.settimeout(max(0.1, remaining))
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            if addr[0] != xbox_ip:
                continue
            parsed = parse_discovery_response(data)
            if parsed:
                parsed.ip_address = xbox_ip
                return parsed
    except OSError as exc:
        logger.debug("定向 Discovery 失败 %s: %s", xbox_ip, exc)
    finally:
        sock.close()
    return None


async def discover_smartglass_consoles(
    timeout_sec: float = 5.0,
    subnet_broadcast: Optional[str] = None,
) -> List[SmartGlassConsole]:
    """
    异步 SmartGlass UDP 发现。

    参数:
        timeout_sec: 收包总超时
        subnet_broadcast: 如 192.168.1.255，可选
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _sync_discover(timeout_sec, subnet_broadcast),
    )
