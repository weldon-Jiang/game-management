"""
SmartGlass UDP Connect（0xCC00 / 0xCC01）+ XSTS 认证。

成功表示主机已接受 Xbox Live 令牌；后续 LAN 媒体仍可走 stream_controller TCP 通道。
"""

from __future__ import annotations

import asyncio
import socket
import struct
import uuid
from dataclasses import dataclass
from typing import Optional, Tuple

from ..core.config import config
from ..core.logger import get_logger
from .smartglass_crypto import (
    CONNECT_RESULT_SUCCESS,
    SmartGlassCrypto,
    SmartGlassCryptoError,
    pkcs7_pad,
    pkcs7_unpad,
    write_sg_string,
)
from .smartglass_discovery import _sync_discover_at

logger = get_logger("smartglass_connect")

PACKET_CONNECT_REQUEST = 0xCC00
PACKET_CONNECT_RESPONSE = 0xCC01


@dataclass
class SmartGlassConnectResult:
    success: bool
    participant_id: int = 0
    message: str = ""


def _pack_connect_request(
    crypto: SmartGlassCrypto,
    client_uuid: bytes,
    userhash: str,
    xsts_token: str,
) -> bytes:
    iv = crypto.generate_iv()
    protected_plain = (
        write_sg_string(userhash or "")
        + write_sg_string(xsts_token or "")
        + struct.pack(">III", 0, 0, 1)
    )
    protected_padded = pkcs7_pad(protected_plain, 16)
    protected_enc = crypto.encrypt(iv, protected_padded)

    unprotected = (
        client_uuid
        + struct.pack(">H", crypto.pubkey_type)
        + crypto._pubkey_bytes
        + iv
    )

    header = struct.pack(
        ">HHHH",
        PACKET_CONNECT_REQUEST,
        len(unprotected),
        len(protected_plain),
        2,
    )
    packet = header + unprotected + protected_enc
    return packet + crypto.hash(packet)


def _parse_connect_response(data: bytes, crypto: SmartGlassCrypto) -> Tuple[int, int]:
    if len(data) < 8:
        raise SmartGlassCryptoError("ConnectResponse 过短")
    pkt_type, unprot_len, prot_len, _version = struct.unpack_from(">HHHH", data, 0)
    if pkt_type != PACKET_CONNECT_RESPONSE:
        raise SmartGlassCryptoError(f"非 ConnectResponse: 0x{pkt_type:04x}")

    offset = 8
    unprotected = data[offset : offset + unprot_len]
    offset += unprot_len
    if len(data) < offset + 32:
        raise SmartGlassCryptoError("ConnectResponse 缺少 HMAC")
    signature = data[-32:]
    protected_enc = data[offset:-32]
    signed = data[:-32]

    if not hmac_compare(crypto.hash(signed), signature):
        raise SmartGlassCryptoError("ConnectResponse HMAC 校验失败")

    if len(unprotected) < 16:
        raise SmartGlassCryptoError("ConnectResponse IV 缺失")
    iv = unprotected[:16]
    plain = pkcs7_unpad(crypto.decrypt(iv, protected_enc))
    if len(plain) < 8:
        raise SmartGlassCryptoError("ConnectResponse 明文过短")

    connect_result, pairing_state = struct.unpack_from(">HH", plain, 0)
    participant_id = struct.unpack_from(">I", plain, 4)[0]
    if connect_result != CONNECT_RESULT_SUCCESS:
        raise SmartGlassCryptoError(f"Connect 失败 result=0x{connect_result:04x}")
    return pairing_state, participant_id


def hmac_compare(a: bytes, b: bytes) -> bool:
    import hmac

    return hmac.compare_digest(a, b)


def _sync_udp_connect(
    xbox_ip: str,
    userhash: str,
    xsts_token: str,
    certificate: Optional[bytes],
    timeout: float,
) -> SmartGlassConnectResult:
    if not certificate:
        discovered = _sync_discover_at(xbox_ip, timeout)
        certificate = discovered.certificate if discovered else None
    if not certificate:
        return SmartGlassConnectResult(False, message="缺少 Discovery 证书，无法 ECDH")

    try:
        crypto = SmartGlassCrypto.from_certificate(certificate)
    except SmartGlassCryptoError as exc:
        return SmartGlassConnectResult(False, message=str(exc))

    client_uuid = uuid.uuid4().bytes
    request = _pack_connect_request(crypto, client_uuid, userhash, xsts_token)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    try:
        sock.settimeout(timeout)
        sock.bind(("", 0))
        sock.sendto(request, (xbox_ip, 5050))

        import time

        end = time.monotonic() + timeout
        while time.monotonic() < end:
            remaining = end - time.monotonic()
            sock.settimeout(max(0.1, remaining))
            try:
                data, addr = sock.recvfrom(65535)
            except socket.timeout:
                continue
            if addr[0] != xbox_ip:
                continue
            if len(data) >= 2 and struct.unpack_from(">H", data, 0)[0] != PACKET_CONNECT_RESPONSE:
                continue
            pairing_state, participant_id = _parse_connect_response(data, crypto)
            logger.info(
                "SmartGlass UDP Connect 成功 %s participant=%s pairing=0x%04x",
                xbox_ip,
                participant_id,
                pairing_state,
            )
            return SmartGlassConnectResult(
                True,
                participant_id=participant_id,
                message="SmartGlass UDP Connect 成功",
            )
        return SmartGlassConnectResult(False, message="ConnectResponse 超时")
    except SmartGlassCryptoError as exc:
        return SmartGlassConnectResult(False, message=str(exc))
    except OSError as exc:
        return SmartGlassConnectResult(False, message=f"UDP 错误: {exc}")
    finally:
        sock.close()


async def connect_smartglass_udp(
    xbox_ip: str,
    userhash: str,
    xsts_token: str,
    certificate: Optional[bytes] = None,
    timeout: Optional[float] = None,
) -> SmartGlassConnectResult:
    """
    经 UDP 5050 发送加密 ConnectRequest（XSTS + uhs）。

    参数:
        certificate: Discovery 阶段获得的 DER 证书；为空则对目标 IP 再 Discovery 一次
    """
    timeout = timeout or float(config.get("lan_stream.smartglass_connect_timeout_sec", 8))
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _sync_udp_connect(xbox_ip, userhash, xsts_token, certificate, timeout),
    )
