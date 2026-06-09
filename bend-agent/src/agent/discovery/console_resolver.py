"""主机发现路由：按 platform 委托 Xbox / PlayStation 独立 resolver。"""

from dataclasses import dataclass
from typing import Callable, Optional

from ..automation.platform_util import account_platform
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
    """按 account_platform 路由，不含任何平台协议细节。"""
    if account_platform(context) == "playstation":
        from .ps_console_resolver import resolve_ps_console_target

        resolved = await resolve_ps_console_target(context, check_cancel, report_progress)
        return ConsoleResolveResult(
            success=resolved.success,
            xbox_info=resolved.console_info,
            message=resolved.message,
            error_code=resolved.error_code,
        )

    from .xbox_console_resolver import resolve_xbox_console_target

    resolved = await resolve_xbox_console_target(context, check_cancel, report_progress)
    return ConsoleResolveResult(
        success=resolved.success,
        xbox_info=resolved.xbox_info,
        message=resolved.message,
        error_code=resolved.error_code,
    )
