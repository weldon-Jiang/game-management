"""WebRTC 串流建立（PlaySession + SDP），与发现分离。"""

from typing import Any, Callable, Dict, Optional, Tuple

from ..core.account_logger import get_stream_logger
from ..core.logger import get_logger
from ..task.task_context import AgentTaskContext


async def establish_webrtc_stream(
    context: AgentTaskContext,
    check_cancel: Optional[Callable[[], bool]] = None,
    report_progress: Optional[Callable] = None,
) -> Tuple[bool, Dict[str, Any]]:
    """在已匹配主机上打开 PlaySession 并协商 WebRTC。"""
    from ..automation.step2_xbox_streaming import _connect_to_xbox

    logger = get_logger(f"xhome_connect_{context.task_id}")
    stream_logger = get_stream_logger(context.streaming_account_email)

    if check_cancel and check_cancel():
        return False, {"errorCode": "CANCELLED", "errorMessage": "Cancelled"}

    if not context.current_xbox and context.assigned_xbox:
        context.current_xbox = context.assigned_xbox

    ok, details = await _connect_to_xbox(context, logger, stream_logger)
    return ok, details or {}


async def reconnect_webrtc_stream(
    context: AgentTaskContext,
    logger=None,
    stream_logger=None,
) -> bool:
    """复用 PlaySession / 重建并重新协商 SDP。"""
    from ..automation.step2_xbox_streaming import reconnect_cloud_stream_session

    log = logger or get_logger(f"xhome_reconnect_{context.task_id}")
    slog = stream_logger or get_stream_logger(context.streaming_account_email)
    return await reconnect_cloud_stream_session(context, log, slog)
