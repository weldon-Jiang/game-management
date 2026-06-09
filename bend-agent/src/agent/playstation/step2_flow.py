"""
PlayStation Step2 核心流程：发现 → 匹配 → 租约探测。

串流握手尚未实现；匹配成功后仍返回 PS_STREAM_NOT_SUPPORTED，并释放试探性租约。
"""

from typing import Any, Callable, Dict, List

from ..api.platform_api_client import PlatformApiClient
from ..task.task_context import AgentTaskContext, Step2Result
from .context_mapper import ps_console_to_task_context
from .pipeline_diagnostic import pipeline_diagnostic_from_context
from .ps_console_lease import (
    is_host_occupied_by_device_id,
    release_device_id,
    try_acquire_device_id,
)
from .ps_host_matcher import PsHostMatcher


async def discover_and_match_playstation_hosts(
    context: AgentTaskContext,
    task_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step2Result:
    """PS Step2：LAN 发现 + 候选排序 + 占用/租约检测。"""
    platform_client = PlatformApiClient()
    try:
        matcher = PsHostMatcher(platform_client=platform_client)
        discovery_err = await matcher.discover_lan()
    finally:
        await platform_client.close()

    if discovery_err is not None:
        fail_msg = discovery_err.message
        if discovery_err.error_code:
            fail_msg = f"[{discovery_err.error_code}] {fail_msg}"
        suggestion = (discovery_err.error_details or {}).get("suggestion")
        if suggestion:
            fail_msg += f"; 解决方案: {suggestion}"
        await report_progress(
            context.task_id,
            "STEP2",
            "FAILED",
            fail_msg,
            errorCode=discovery_err.error_code,
            hostAttempts=[],
        )
        return Step2Result(
            success=False,
            error_code=discovery_err.error_code or "DISCOVERY_FAILED",
            message=fail_msg,
        )

    candidates = matcher.build_candidates(context)
    if not candidates:
        if context.assigned_xbox:
            fail_msg = "指定 PlayStation 主机不在局域网或未开机"
            error_code = "ASSIGNED_HOST_NOT_FOUND"
        elif not context.auto_match_host:
            fail_msg = "未指定 PlayStation 主机且已禁用自动匹配"
            error_code = "NO_ASSIGNED_HOST"
        else:
            fail_msg = "无可用 PlayStation 主机候选"
            error_code = "LAN_NO_HOST"
        await report_progress(
            context.task_id,
            "STEP2",
            "FAILED",
            fail_msg,
            errorCode=error_code,
            hostAttempts=[],
        )
        return Step2Result(success=False, error_code=error_code, message=fail_msg)

    host_attempts: List[Dict[str, Any]] = []
    await report_progress(
        context.task_id,
        "STEP2",
        "RUNNING",
        f"发现 {len(candidates)} 台 PlayStation 主机，检测占用",
        hostAttempts=host_attempts,
        intersectionCount=len(candidates),
    )

    selected_device_id = None
    for idx, candidate in enumerate(candidates, start=1):
        if check_cancel():
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        device_id = candidate.device_id
        attempt: Dict[str, Any] = {
            "index": idx,
            "serverId": device_id,
            "name": candidate.name,
            "ip": candidate.ip_address,
            "status": "trying",
        }
        task_logger.info(
            "PS 候选 %s/%s: %s @ %s (deviceId=%s, %s)",
            idx,
            len(candidates),
            candidate.name,
            candidate.ip_address,
            device_id,
            candidate.power_state,
        )

        if await is_host_occupied_by_device_id(device_id, context, task_logger):
            attempt["status"] = "occupied"
            attempt["errorCode"] = "PS_HOST_OCCUPIED"
            attempt["message"] = f"主机 {candidate.name} 已被其他 Agent/任务占用"
            host_attempts.append(attempt)
            await report_progress(
                context.task_id, "STEP2", "RUNNING", attempt["message"], hostAttempts=host_attempts
            )
            continue

        if not await try_acquire_device_id(context, device_id, task_logger):
            attempt["status"] = "occupied"
            attempt["errorCode"] = "LEASE_DENIED"
            attempt["message"] = f"主机 {candidate.name} 租约申请失败"
            host_attempts.append(attempt)
            await report_progress(
                context.task_id, "STEP2", "RUNNING", attempt["message"], hostAttempts=host_attempts
            )
            continue

        context.current_xbox = ps_console_to_task_context(candidate)
        context.assigned_xbox = context.current_xbox
        selected_device_id = device_id
        attempt["status"] = "matched"
        attempt["message"] = "主机匹配成功（串流尚未开放）"
        host_attempts.append(attempt)
        break

    if not selected_device_id:
        fail_msg = f"全部 {len(candidates)} 台 PlayStation 主机不可用（占用或租约失败）"
        await report_progress(
            context.task_id,
            "STEP2",
            "FAILED",
            fail_msg,
            errorCode="ALL_HOSTS_UNAVAILABLE",
            hostAttempts=host_attempts,
        )
        return Step2Result(
            success=False,
            error_code="ALL_HOSTS_UNAVAILABLE",
            message=fail_msg,
        )

    fail_msg = "PlayStation 串流尚未开放，当前仅支持 Xbox LAN 串流"
    pipeline = pipeline_diagnostic_from_context(context)
    await report_progress(
        context.task_id,
        "STEP2",
        "FAILED",
        fail_msg,
        errorCode="PS_STREAM_NOT_SUPPORTED",
        hostAttempts=host_attempts,
        intersectionCount=len(candidates),
        selectedServerId=selected_device_id,
        pipelineDiagnostic=pipeline,
    )

    # 串流占位：chiaki_connect / ps_stream_controller 待后续实现；此处仅验证发现+租约后释放
    await release_device_id(context, selected_device_id, task_logger)

    return Step2Result(
        success=False,
        error_code="PS_STREAM_NOT_SUPPORTED",
        message=fail_msg,
    )
