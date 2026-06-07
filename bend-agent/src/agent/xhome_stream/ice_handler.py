"""
Teredo ICE candidate enrichment for xHome WebRTC (XStreamingDesktop aligned).

Synthesizes host candidates from Teredo IPv6 (client4:9002 / udpPort) when present.
"""

import re
import socket
import struct
from typing import List, Optional, Tuple

from ..core.config import config
from ..core.logger import get_logger

_logger = get_logger("ice_handler")

_TEREDO_RE = re.compile(
    r"candidate:(\S+)\s+\d+\s+udp\s+\d+\s+([0-9a-f:.]+)\s+(\d+)",
    re.IGNORECASE,
)


def is_enabled() -> bool:
    return bool(config.get("xhome_stream.enable_teredo_ice_rewrite", True))


def _inspect_teredo(ipv6: str) -> Optional[Tuple[str, int]]:
    """Decode Teredo client IPv4 and mapped UDP port (RFC 4380)."""
    try:
        packed = socket.inet_pton(socket.AF_INET6, ipv6)
        if packed[:4] != b"\x20\x01\x00\x00":
            return None
        port = struct.unpack("!H", bytes(b ^ 0xFF for b in packed[10:12]))[0]
        client4 = socket.inet_ntoa(bytes(b ^ 0xFF for b in packed[12:16]))
        return client4, port or 3074
    except Exception as exc:
        _logger.debug("Teredo inspect failed for %s: %s", ipv6, exc)
        return None


def enrich_teredo_candidates(candidates: List[str]) -> List[str]:
    """XStreamingDesktop-style host candidate synthesis from Teredo lines."""
    if not is_enabled() or not candidates:
        return list(candidates)

    enriched: List[str] = []
    for raw in candidates:
        line = raw[2:] if raw.startswith("a=") else raw
        enriched.append(line)

        parts = line.split()
        if len(parts) < 6:
            continue
        ip = parts[4]
        if not ip.startswith("2001"):
            continue
        teredo = _inspect_teredo(ip)
        if not teredo:
            continue
        client4, udp_port = teredo
        enriched.append(f"candidate:9002 1 UDP 2130706431 {client4} 9002 typ host")
        enriched.append(f"candidate:9003 1 UDP 2130706430 {client4} {udp_port} typ host")

    return enriched


def rewrite_candidate(candidate: str, public_ip: Optional[str] = None) -> str:
    if not is_enabled() or not public_ip or not candidate:
        return candidate
    if "teredo" not in candidate.lower() and "2001:0000" not in candidate:
        return candidate

    def _repl(m: re.Match) -> str:
        return f"candidate:{m.group(1)} 1 udp 2130706431 {public_ip} {m.group(3)} typ srflx"

    return _TEREDO_RE.sub(_repl, candidate)


def rewrite_sdp(sdp: str, public_ip: Optional[str] = None) -> str:
    """Rewrite SDP answer; enrich Teredo ICE lines when enabled."""
    if not sdp:
        return sdp

    lines: List[str] = []
    candidates: List[str] = []
    for line in sdp.splitlines():
        if line.startswith("a=candidate:"):
            candidates.append(line[2:])
        else:
            lines.append(line)

    if is_enabled() and candidates:
        candidates = enrich_teredo_candidates(candidates)

    for cand in candidates:
        if public_ip:
            cand = rewrite_candidate(cand, public_ip)
        lines.append(f"a={cand}")

    body = "\r\n".join(lines)
    return body + ("\r\n" if sdp.endswith("\r\n") else "")


def extract_public_ip_from_candidates(candidates: List[str]) -> Optional[str]:
    for c in candidates:
        if "typ srflx" in c and "." in c:
            parts = c.split()
            for i, p in enumerate(parts):
                if p == "typ" and i >= 4:
                    ip = parts[i - 2]
                    if "." in ip and not ip.startswith("127."):
                        return ip
    return None
