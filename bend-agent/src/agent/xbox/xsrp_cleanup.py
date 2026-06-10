"""xsrp 栈资源清理（WebRTC / GSSV / 保活任务）。"""

from __future__ import annotations

from typing import Any

from ..core.logger import get_logger
from .xsrp_stream_keepalive import stop_xsrp_idle_keepalive


async def cleanup_xsrp_stream_context(context: Any, task_logger=None) -> None:
    """任务结束或失败时释放 xsrp 云端串流资源。"""
    log = task_logger or get_logger("xsrp_cleanup")
    await stop_xsrp_idle_keepalive(context)

    webrtc = getattr(context, "_cloud_webrtc", None)
    if webrtc and hasattr(webrtc, "close"):
        try:
            await webrtc.close()
        except Exception as exc:
            log.debug("close xsrp webrtc: %s", exc)

    gssv_client = getattr(context, "_gssv_client", None)
    if gssv_client and hasattr(gssv_client, "close"):
        try:
            await gssv_client.close()
        except Exception as exc:
            log.debug("close xsrp gssv client: %s", exc)

    context._cloud_webrtc = None
    context._gssv_client = None
    context._cloud_frame_controller = None
    context._direct_capture = None
    context._streaming_credentials = None
