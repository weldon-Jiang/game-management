"""
步骤二：PlayStation LAN（薄编排层）。

核心逻辑位于 playstation/step2_flow.py 及 playstation/* 模块。
"""

import asyncio
from typing import Callable

from ...core.account_logger import get_stream_logger
from ...core.task_logger import get_task_logger
from ...playstation.step2_flow import discover_and_match_playstation_hosts
from ...task.task_context import AgentTaskContext, Step2Result, TaskStepStatus


async def discover_playstation_lan_step2(
    context: AgentTaskContext,
    task_logger,
    report_progress: Callable,
) -> Step2Result:
    """PlayStation Step2 发现/匹配（供 discovery 门面调用）。"""
    return await discover_and_match_playstation_hosts(
        context,
        task_logger,
        lambda: False,
        report_progress,
    )


async def step2_execute_playstation_streaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step2Result:
    """PlayStation 账号 Step2 入口。"""
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)
    task_logger.info("=== 步骤二：PlayStation LAN 发现 ===")
    stream_logger.info("=== 开始 PlayStation LAN 发现 ===")

    context.update_step_status("step2", TaskStepStatus.RUNNING, "正在匹配 PlayStation 主机...")
    await report_progress(context.task_id, "STEP2", "RUNNING", "正在匹配 PlayStation 主机...")

    try:
        if check_cancel():
            context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        return await discover_and_match_playstation_hosts(
            context, task_logger, check_cancel, report_progress,
        )

    except asyncio.CancelledError:
        context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
        return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as exc:
        error_msg = f"步骤二执行超时: {exc}"
        task_logger.error(error_msg, exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(exc))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="TIMEOUT", message=error_msg)

    except Exception as exc:
        error_msg = f"步骤二异常: {exc}"
        task_logger.error(error_msg, exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(exc))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="STEP2_ERROR", message=error_msg)
