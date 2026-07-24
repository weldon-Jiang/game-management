"""
步骤二（xblive/xsrp 栈）：GSSV 发现 + play/WebRTC 串流握手 + 解码首帧 + 输入通道。

与 step1_xblive_login.py 配套；对齐 streaming/xsrp OpenStreaming 的 GSSV/WebRTC 段。
"""

import asyncio
from typing import Callable

from ...core.account_logger import get_stream_logger
from ...core.task_logger import get_task_logger
from ...task.task_context import AgentTaskContext, Step2Result, TaskStepStatus
from ...xbox.step2_xsrp_connect import discover_and_connect_xsrp


async def step2_execute_xsrp_streaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step2Result:
    """xblive/xsrp Step2 入口。"""
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)
    task_logger.info("=== 步骤二（xsrp）：开始 GSSV 发现与串流握手 ===")
    stream_logger.info("=== 步骤二（xsrp）：开始 GSSV 发现与串流握手 ===")

    context.update_step_status("step2", TaskStepStatus.RUNNING, "xsrp 正在发现 Xbox 主机...")
    await report_progress(
        context.task_id, "STEP2", "RUNNING", "xsrp 正在发现 Xbox 主机...",
        streamingStack="xsrp",
    )

    try:
        if check_cancel():
            context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        return await discover_and_connect_xsrp(
            context, task_logger, stream_logger, check_cancel, report_progress,
        )

    except asyncio.CancelledError:
        context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
        return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as exc:
        error_msg = f"xsrp 步骤二超时: {exc}"
        task_logger.error(error_msg, exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(exc))
        await report_progress(
            context.task_id, "STEP2", "FAILED", error_msg, streamingStack="xsrp",
        )
        return Step2Result(success=False, error_code="TIMEOUT", message=error_msg)

    except Exception as exc:
        error_msg = f"xsrp 步骤二异常: {exc}"
        task_logger.error(error_msg, exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(exc))
        await report_progress(
            context.task_id, "STEP2", "FAILED", error_msg, streamingStack="xsrp",
        )
        return Step2Result(success=False, error_code="EXCEPTION", message=error_msg)
