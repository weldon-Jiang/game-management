"""主机发现与 LAN 串流握手（GSSV ∩ SmartGlass UDP）。"""

from dataclasses import dataclass
from typing import Callable, Optional

from ..core.account_logger import get_stream_logger
from ..core.task_logger import get_task_logger
from ..task.task_context import AgentTaskContext, XboxInfo


@dataclass
class ConsoleResolveResult:
    success: bool
    xbox_info: Optional[XboxInfo] = None
    message: str = ""
    error_code: Optional[str] = None


async def resolve_console_target(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Optional[Callable] = None,
) -> ConsoleResolveResult:
    """云端∩LAN 交集发现 + 逐台 LAN 握手（与 step2 主流程一致）。"""
    from ..automation.step2_xbox_streaming import discover_intersection_and_connect_lan

    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)

    if check_cancel():
        return ConsoleResolveResult(success=False, error_code="CANCELLED", message="Cancelled")

    async def _report(*args, **kwargs):
        if report_progress:
            await report_progress(*args, **kwargs)

    result = await discover_intersection_and_connect_lan(
        context,
        task_logger,
        stream_logger,
        check_cancel,
        _report,
    )
    if not result.success:
        return ConsoleResolveResult(
            success=False,
            message=result.message,
            error_code=result.error_code or "XBOX_MATCH_FAILED",
        )

    return ConsoleResolveResult(success=True, xbox_info=context.current_xbox)
