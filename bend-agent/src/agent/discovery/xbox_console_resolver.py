"""Xbox 主机发现/串流握手门面（xblive→xsrp；MSAL→legacy step2）。"""

from dataclasses import dataclass
from typing import Callable, Optional

from ..core.account_logger import get_stream_logger
from ..core.task_logger import get_task_logger
from ..task.task_context import AgentTaskContext, XboxInfo


@dataclass
class XboxConsoleResolveResult:
    success: bool
    xbox_info: Optional[XboxInfo] = None
    message: str = ""
    error_code: Optional[str] = None


def _resolve_xbox_step2_discover():
    from ..auth.step2_router import resolve_step2_execute_streaming

    return resolve_step2_execute_streaming()


async def resolve_xbox_console_target(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Optional[Callable] = None,
) -> XboxConsoleResolveResult:
    """Xbox：按 auth.provider 走 xsrp 或 legacy Step2。"""
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)

    if check_cancel():
        return XboxConsoleResolveResult(success=False, error_code="CANCELLED", message="Cancelled")

    async def _report(*args, **kwargs):
        if report_progress:
            await report_progress(*args, **kwargs)

    discover_fn = _resolve_xbox_step2_discover()
    result = await discover_fn(context, check_cancel, _report)
    if not result.success:
        return XboxConsoleResolveResult(
            success=False,
            message=result.message,
            error_code=result.error_code or "XBOX_MATCH_FAILED",
        )
    return XboxConsoleResolveResult(success=True, xbox_info=context.current_xbox)
