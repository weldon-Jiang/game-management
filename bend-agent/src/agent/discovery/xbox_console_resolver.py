"""Xbox 主机发现/串流握手门面（委托 xbox/step2_discover_connect）。"""

from dataclasses import dataclass
from typing import Callable, Optional

from ..core.account_logger import get_stream_logger
from ..core.task_logger import get_task_logger
from ..task.task_context import AgentTaskContext, XboxInfo
from ..xbox.step2_discover_connect import discover_intersection_and_connect_lan


@dataclass
class XboxConsoleResolveResult:
    success: bool
    xbox_info: Optional[XboxInfo] = None
    message: str = ""
    error_code: Optional[str] = None


async def resolve_xbox_console_target(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Optional[Callable] = None,
) -> XboxConsoleResolveResult:
    """Xbox：GSSV∩LAN 发现 + LAN 握手。"""
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)

    if check_cancel():
        return XboxConsoleResolveResult(success=False, error_code="CANCELLED", message="Cancelled")

    async def _report(*args, **kwargs):
        if report_progress:
            await report_progress(*args, **kwargs)

    result = await discover_intersection_and_connect_lan(
        context, task_logger, stream_logger, check_cancel, _report,
    )
    if not result.success:
        return XboxConsoleResolveResult(
            success=False,
            message=result.message,
            error_code=result.error_code or "XBOX_MATCH_FAILED",
        )
    return XboxConsoleResolveResult(success=True, xbox_info=context.current_xbox)
