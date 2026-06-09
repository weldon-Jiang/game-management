"""
步骤二路由：按 account_platform 分发至 Xbox 或 PlayStation 实现。

StreamingAccountTask 与 discovery 门面统一 import 本模块的 step2_execute_streaming。
"""

from typing import Callable

from ..task.task_context import AgentTaskContext, Step2Result
from .platform_util import account_platform


async def step2_execute_streaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step2Result:
    """Step2 统一入口：xbox → SmartGlass；playstation → Chiaki UDP。"""
    if account_platform(context) == "playstation":
        from .step2_playstation_streaming import step2_execute_playstation_streaming

        return await step2_execute_playstation_streaming(
            context, check_cancel, report_progress
        )

    from .step2_xbox_streaming import step2_execute_xbox_streaming

    return await step2_execute_xbox_streaming(context, check_cancel, report_progress)
