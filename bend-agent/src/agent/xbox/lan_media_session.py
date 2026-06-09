"""
LAN 媒体通道：SmartGlass 会话协商 → DTLS-SRTP 握手 → RTP 收流准备。

对照 streaming/xsrp（libxsrp 内部 WebRTC/DTLS-SRTP），bend-agent 在无法加载
xsrpwrapper 时走本模块：TCP SmartGlass 已连接后，在 UDP 上完成 DTLS-PSK 并导出 SRTP 密钥。
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, field
from typing import Any, Dict, Optional, TYPE_CHECKING

from ..core.config import config
from ..core.logger import get_logger
from .dtls_handler import DTLSPSKClient, SRTPKeyMaterial
from . import xsrp_bridge

if TYPE_CHECKING:
    from .stream_controller import StreamConfig, XboxStreamController

logger = get_logger("lan_media_session")


@dataclass
class LanMediaEndpoints:
    """LAN 媒体端点（来自 Xbox SmartGlass 响应或配置默认值）。"""
    xbox_ip: str
    dtls_port: int = 50500
    rtp_port: int = 50500
    psk_identity: str = "xbox"
    psk: bytes = b""
    raw_response: Dict[str, Any] = field(default_factory=dict)


def _lan_stream_config() -> Dict[str, Any]:
    return {
        "rtp_port": int(config.get("lan_stream.rtp_port", 50500)),
        "dtls_port": int(config.get("lan_stream.dtls_port", 50500)),
        "handshake_timeout_sec": float(config.get("lan_stream.handshake_timeout_sec", 15)),
        "first_frame_timeout_sec": float(config.get("lan_stream.first_frame_timeout_sec", 10)),
    }


def _extract_nested(data: Dict[str, Any], *keys: str) -> Any:
    cur: Any = data
    for key in keys:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def parse_stream_session_response(payload: Dict[str, Any], xbox_ip: str) -> LanMediaEndpoints:
    """
    从 SmartGlass 串流会话响应解析 DTLS/RTP 端口与 PSK。

    兼容多种字段命名（JSON 嵌套或扁平）。
    """
    cfg = _lan_stream_config()
    endpoints = LanMediaEndpoints(
        xbox_ip=xbox_ip,
        dtls_port=int(
            payload.get("dtlsPort")
            or payload.get("dtls_port")
            or _extract_nested(payload, "streaming", "dtlsPort")
            or cfg["dtls_port"]
        ),
        rtp_port=int(
            payload.get("rtpPort")
            or payload.get("rtp_port")
            or payload.get("videoPort")
            or _extract_nested(payload, "streaming", "rtpPort")
            or cfg["rtp_port"]
        ),
        raw_response=payload,
    )

    psk_b64 = (
        payload.get("psk")
        or payload.get("preSharedKey")
        or _extract_nested(payload, "security", "psk")
    )
    if isinstance(psk_b64, str) and psk_b64:
        import base64

        try:
            endpoints.psk = base64.b64decode(psk_b64)
        except Exception:
            endpoints.psk = psk_b64.encode("utf-8")
    elif isinstance(psk_b64, (bytes, bytearray)):
        endpoints.psk = bytes(psk_b64)

    endpoints.psk_identity = str(
        payload.get("pskIdentity")
        or payload.get("psk_identity")
        or endpoints.psk_identity
    )
    return endpoints


def derive_psk_from_tokens(auth_token: str, user_hash: str, xbox_ip: str) -> bytes:
    """
    当 SmartGlass 响应未携带 PSK 时的开发兜底（SHA256 截断 16 字节）。

    生产环境应优先使用会话响应中的 PSK；auth_token 应为 XSTS。
    """
    import hashlib

    seed = f"{user_hash}:{auth_token[:32]}:{xbox_ip}".encode("utf-8")
    return hashlib.sha256(seed).digest()[:16]


async def request_streaming_session(
    controller: "XboxStreamController",
    stream_config: "StreamConfig",
    timeout: float = 5.0,
) -> Optional[Dict[str, Any]]:
    """
    经 SmartGlass 通道请求串流会话，解析 JSON 响应中的媒体参数。
    """
    command = {
        "type": "Streaming",
        "RequestStream": {
            "version": 1,
            "settings": {
                "video": {
                    "width": stream_config.video_width,
                    "height": stream_config.video_height,
                    "framerate": stream_config.video_framerate,
                    "bitrate": stream_config.video_bitrate,
                },
                "audio": {"enabled": stream_config.audio_enabled},
            },
        },
    }
    try:
        await controller._send_command(command)
        if not controller._reader:
            return None
        header = await asyncio.wait_for(controller._reader.readexactly(4), timeout=timeout)
        length = int.from_bytes(header, "big")
        if length <= 0 or length > 65536:
            logger.warning("SmartGlass 会话响应长度异常: %s", length)
            return None
        body = await asyncio.wait_for(controller._reader.readexactly(length), timeout=timeout)
        text = body.decode("utf-8", errors="replace")
        return json.loads(text)
    except asyncio.TimeoutError:
        logger.warning("SmartGlass RequestStream 响应超时")
        return None
    except json.JSONDecodeError as exc:
        logger.warning("SmartGlass 会话响应非 JSON: %s", exc)
        return None
    except Exception as exc:
        logger.warning("SmartGlass RequestStream 失败: %s", exc)
        return None


async def perform_dtls_srtp_handshake(
    endpoints: LanMediaEndpoints,
    timeout: Optional[float] = None,
) -> Optional[SRTPKeyMaterial]:
    """在 UDP 上与 Xbox 执行 DTLS-PSK 握手并导出 SRTP 密钥（RFC 5764）。"""
    cfg = _lan_stream_config()
    timeout = timeout or cfg["handshake_timeout_sec"]

    if not endpoints.psk:
        logger.error("DTLS-PSK 缺少 PSK，无法握手")
        return None

    client = DTLSPSKClient(
        psk=endpoints.psk,
        psk_identity=endpoints.psk_identity,
    )
    ok = await client.connect(
        endpoints.xbox_ip,
        endpoints.dtls_port,
        timeout=timeout,
    )
    if not ok:
        logger.error(
            "DTLS 握手失败: %s:%s state=%s",
            endpoints.xbox_ip,
            endpoints.dtls_port,
            client.state.value,
        )
        return None

    keys = client.get_srtp_keys()
    client.close()
    if keys:
        logger.info(
            "DTLS-SRTP 密钥已导出 (dtls=%s:%s rtp_port=%s)",
            endpoints.xbox_ip,
            endpoints.dtls_port,
            endpoints.rtp_port,
        )
    return keys


def srtp_keys_to_dict(keys: SRTPKeyMaterial) -> Dict[str, bytes]:
    """转为 stream_controller.start_video_receiver 使用的字典。"""
    return {
        "send_key": keys.send_key[:16],
        "recv_key": keys.recv_key[:16],
        "send_salt": keys.send_salt,
        "recv_salt": keys.recv_salt,
    }


async def establish_lan_media_security(
    controller: "XboxStreamController",
    stream_config: "StreamConfig",
    xbox_ip: str,
    auth_token: Optional[str] = None,
    user_hash: Optional[str] = None,
) -> tuple[bool, Optional[Dict[str, bytes]], str, LanMediaEndpoints]:
    """
    完整 LAN 媒体安全建立：RequestStream → DTLS-SRTP → 返回 SRTP 密钥。

    返回: (success, srtp_keys_dict, message, endpoints)
    """
    session_resp = await request_streaming_session(controller, stream_config)
    if session_resp:
        endpoints = parse_stream_session_response(session_resp, xbox_ip)
    else:
        cfg = _lan_stream_config()
        endpoints = LanMediaEndpoints(
            xbox_ip=xbox_ip,
            dtls_port=cfg["dtls_port"],
            rtp_port=cfg["rtp_port"],
        )
        logger.info("未收到 RequestStream 响应，使用默认端口 dtls/rtp=%s", endpoints.dtls_port)

    if not endpoints.psk and auth_token and user_hash:
        endpoints.psk = derive_psk_from_tokens(auth_token, user_hash, xbox_ip)
        logger.warning("使用 XSTS 派生 PSK 兜底（应优先使用 SmartGlass 会话 PSK）")

    if xsrp_bridge.is_xsrp_available():
        logger.info("检测到 xsrpwrapper；媒体密钥仍由 Python DTLS-PSK 导出（libxsrp 不暴露 SRTP 材料）")

    key_material = await perform_dtls_srtp_handshake(endpoints)
    if not key_material:
        return False, None, "DTLS-SRTP 握手失败", endpoints

    return True, srtp_keys_to_dict(key_material), "DTLS-SRTP 握手成功", endpoints


async def wait_for_first_rtp_packet(
    controller: "XboxStreamController",
    timeout: Optional[float] = None,
) -> bool:
    """等待首包 RTP/SRTP，用于 Step2 成功门控。"""
    cfg = _lan_stream_config()
    timeout = timeout or cfg["first_frame_timeout_sec"]
    session = getattr(controller, "_rtp_session", None)
    if session is None:
        return False

    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        stats = session.get_stats()
        if stats.get("packets_received", 0) > 0:
            return True
        await asyncio.sleep(0.2)
    return False
