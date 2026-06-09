"""PlayStation 主机发现门面（委托 playstation/step2_flow）。"""

from dataclasses import dataclass
from typing import Callable, Optional

from ..core.task_logger import get_task_logger
from ..playstation.step2_flow import discover_and_match_playstation_hosts
from ..task.task_context import AgentTaskContext, XboxInfo


@dataclass
class PsConsoleResolveResult:
    success: bool
    console_info: Optional[XboxInfo] = None
    message: str = ""
    error_code: Optional[str] = None


async def resolve_ps_console_target(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Optional[Callable] = None,
) -> PsConsoleResolveResult:
    """PlayStation：Chiaki LAN 发现 + 匹配（串流未开放时 success=False）。"""
    task_logger = get_task_logger(context.task_id)

    if check_cancel():
        return PsConsoleResolveResult(success=False, error_code="CANCELLED", message="Cancelled")

    async def _report(*args, **kwargs):
        if report_progress:
            await report_progress(*args, **kwargs)

    result = await discover_and_match_playstation_hosts(
        context, task_logger, check_cancel, _report,
    )
    if not result.success:
        return PsConsoleResolveResult(
            success=False,
            message=result.message,
            error_code=result.error_code or "PS_MATCH_FAILED",
            console_info=context.current_xbox,
        )
    return PsConsoleResolveResult(success=True, console_info=context.current_xbox)
