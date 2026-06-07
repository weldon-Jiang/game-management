"""Console discovery + match (no WebRTC). Delegates to step2 match helpers until full migration."""

from dataclasses import dataclass
from typing import Any, Callable, Optional

from ..core.account_logger import get_stream_logger
from ..core.logger import get_logger
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
    """Match one authorized family Xbox; does not open PlaySession/WebRTC."""
    from ..automation.step2_xbox_streaming import (
        _check_xbox_availability,
        _format_xbox_match_message,
        _match_xbox_host,
        _matcher_xbox_to_context,
    )

    logger = get_logger(f"console_resolver_{context.task_id}")
    stream_logger = get_stream_logger(context.streaming_account_email)

    if check_cancel():
        return ConsoleResolveResult(success=False, error_code="CANCELLED", message="Cancelled")

    match_result = await _match_xbox_host(context, logger, stream_logger, check_cancel)
    if not match_result.success:
        fail_msg = _format_xbox_match_message(match_result)
        return ConsoleResolveResult(
            success=False,
            message=fail_msg,
            error_code=match_result.error_code or "XBOX_MATCH_FAILED",
        )

    xbox_id = (
        match_result.xbox_info.id
        or match_result.xbox_info.live_id
        or match_result.xbox_info.mac_address
    )
    if xbox_id and not await _check_xbox_availability(context, xbox_id):
        error_msg = f"Xbox主机 {match_result.xbox_info.name} 已被其他任务占用"
        return ConsoleResolveResult(
            success=False,
            message=error_msg,
            error_code="XBOX_OCCUPIED",
        )

    context.current_xbox = _matcher_xbox_to_context(match_result.xbox_info)
    context.assigned_xbox = context.current_xbox
    logger.info(
        "Console resolved: %s (serverId=%s)",
        context.current_xbox.name,
        context.current_xbox.id,
    )
    return ConsoleResolveResult(success=True, xbox_info=context.current_xbox)
