"""
步骤二路由：按 account_platform 分发至 Xbox 或 PlayStation 实现。

Xbox 统一走 xblive/xsrp 云端 GSSV 串流（step2_xsrp）。
"""

from typing import Callable

from ..task.task_context import AgentTaskContext, Step2Result
from .platform_util import account_platform


async def step2_execute_streaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step2Result:
    """Step2 统一入口。"""
    if account_platform(context) == "playstation":
        from .step2_playstation_streaming import step2_execute_playstation_streaming

        return await step2_execute_playstation_streaming(
            context, check_cancel, report_progress
        )

    from ..auth.step2_router import resolve_step2_execute_streaming

    execute = resolve_step2_execute_streaming()
    return await execute(context, check_cancel, report_progress)
