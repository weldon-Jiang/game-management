"""GSSV 串流模式解析。"""

from __future__ import annotations

from ..core.config import config


def get_stream_mode() -> str:
    """返回 lan | cloud，默认 cloud（Route B）。"""
    mode = str(config.get("gssv.stream_mode", "cloud") or "cloud").strip().lower()
    return mode if mode in ("lan", "cloud") else "cloud"


def is_cloud_stream_mode() -> bool:
    return get_stream_mode() == "cloud"
