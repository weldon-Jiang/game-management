"""Xbox Step2 核心：GSSV∩LAN 发现 + 逐台租约与 LAN 握手。"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

from ..api.platform_api_client import PlatformApiClient
from ..core.config import config as app_config
from ..gssv.base_uri import resolve_gssv_base_uri
from ..task.task_context import AgentTaskContext, Step2Result, TaskStepStatus, XboxInfo
from .console_lease import (
    is_host_occupied_by_server_id,
    release_server_id,
    try_acquire_server_id,
)
from .lan_connect import cleanup_lan_connect_attempt, connect_to_xbox_lan
from .pipeline_diagnostic import pipeline_diagnostic_from_context
from .xbox_host_matcher import XboxHostMatcher, XboxMatchResult, XboxInfo as MatcherXboxInfo

DEFAULT_PLAY_PATH = "v5/sessions/home/play"


def matcher_xbox_to_context(matcher_xbox: MatcherXboxInfo) -> XboxInfo:
    """将 matcher 的 XboxInfo 映射为 task_context.XboxInfo。"""
    server_id = matcher_xbox.id or matcher_xbox.device_id
    platform_host_id = getattr(matcher_xbox, "platform_host_id", "") or ""
    return XboxInfo(
        id=server_id,
        platform_host_id=platform_host_id,
        name=matcher_xbox.name,
        ip_address=matcher_xbox.ip_address,
        live_id=matcher_xbox.live_id or matcher_xbox.device_id,
        mac_address=matcher_xbox.mac_address,
        play_path=matcher_xbox.play_path or DEFAULT_PLAY_PATH,
        power_state=matcher_xbox.power_state,
        console_type=matcher_xbox.console_type,
    )


def format_xbox_match_message(match_result: XboxMatchResult) -> str:
    reason = match_result.match_reason or "Xbox主机匹配失败"
    msg = f"[{match_result.error_code}] {reason}" if match_result.error_code else reason
    suggestion = (match_result.error_details or {}).get("suggestion")
    if suggestion:
        msg += f"; 解决方案: {suggestion}"
    return msg


def per_host_attempt_timeout_sec() -> float:
    return float(app_config.get("lan_stream.per_host_attempt_timeout_sec", 45))


def get_gs_token(context: AgentTaskContext) -> Optional[str]:
    if context.xbox_tokens and hasattr(context.xbox_tokens, "gs_token"):
        token = context.xbox_tokens.gs_token
        if token:
            return token
    return None


async def discover_intersection_and_connect_lan(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step2Result:
    """云端∩LAN 交集发现 + 按序逐台占用检测与 LAN 握手。"""
    gs_token = get_gs_token(context)
    if not gs_token:
        return Step2Result(
            success=False,
            error_code="NO_GS_TOKEN",
            message="无可用的 gsToken，请重新执行步骤一",
        )

    platform_client = PlatformApiClient()
    try:
        matcher = XboxHostMatcher(
            gs_token,
            gssv_base_uri=resolve_gssv_base_uri(context),
            platform_client=platform_client,
        )
        discovery_err = await matcher.discover_cloud_and_lan()
    finally:
        await platform_client.close()

    if discovery_err is not None:
        fail_msg = format_xbox_match_message(discovery_err)
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
            fail_msg = "指定 Xbox 主机不在局域网或未开机"
            error_code = "ASSIGNED_HOST_NOT_FOUND"
        elif context.platform_xbox_hosts:
            fail_msg = "绑定主机与局域网发现无交集"
            error_code = "BOUND_HOSTS_NOT_FOUND"
        elif not context.auto_match_host:
            fail_msg = "未指定 Xbox 主机且已禁用自动匹配"
            error_code = "NO_ASSIGNED_HOST"
        else:
            fail_msg = "无可用 Xbox 主机候选"
            error_code = "NO_CANDIDATES"
        context.update_step_status("step2", TaskStepStatus.FAILED, fail_msg)
        await report_progress(
            context.task_id,
            "STEP2",
            "FAILED",
            fail_msg,
            errorCode=error_code,
            hostAttempts=[],
        )
        return Step2Result(success=False, error_code=error_code, message=fail_msg)

    per_host_timeout = per_host_attempt_timeout_sec()
    host_attempts: List[Dict[str, Any]] = []

    await report_progress(
        context.task_id,
        "STEP2",
        "RUNNING",
        f"发现 {len(candidates)} 台可串流主机，开始逐台握手",
        hostAttempts=host_attempts,
        intersectionCount=len(candidates),
    )

    for idx, candidate in enumerate(candidates, start=1):
        if check_cancel():
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        server_id = candidate.device_id or candidate.id
        attempt: Dict[str, Any] = {
            "index": idx,
            "serverId": server_id,
            "name": candidate.name,
            "ip": candidate.ip_address,
            "status": "trying",
        }
        task_logger.info(
            "尝试主机 %s/%s: %s @ %s (serverId=%s)",
            idx, len(candidates), candidate.name, candidate.ip_address, server_id,
        )

        powered = matcher._is_powered_on(candidate.power_state)
        if not powered and matcher._can_wakeup(candidate.power_state):
            wakeup_payload = await matcher._ensure_powered_on(candidate, wakeup=True, wakeup_timeout=30)
            if not wakeup_payload["ok"]:
                attempt["status"] = "wakeup_failed"
                attempt["errorCode"] = "WAKEUP_FAILED"
                attempt["message"] = wakeup_payload["result"].match_reason
                host_attempts.append(attempt)
                await report_progress(context.task_id, "STEP2", "RUNNING", attempt["message"], hostAttempts=host_attempts)
                continue
            powered = True

        if not powered and not matcher._can_wakeup(candidate.power_state):
            attempt["status"] = "offline"
            attempt["errorCode"] = "HOST_OFFLINE"
            attempt["message"] = f"主机未开机: {candidate.power_state}"
            host_attempts.append(attempt)
            await report_progress(context.task_id, "STEP2", "RUNNING", attempt["message"], hostAttempts=host_attempts)
            continue

        if await is_host_occupied_by_server_id(server_id, context, task_logger):
            attempt["status"] = "occupied"
            attempt["errorCode"] = "XBOX_OCCUPIED"
            attempt["message"] = f"主机 {candidate.name} 已被其他 Agent/任务占用"
            host_attempts.append(attempt)
            await report_progress(context.task_id, "STEP2", "RUNNING", attempt["message"], hostAttempts=host_attempts)
            continue

        if not await try_acquire_server_id(context, server_id, task_logger):
            attempt["status"] = "occupied"
            attempt["errorCode"] = "LEASE_DENIED"
            attempt["message"] = f"主机 {candidate.name} 租约申请失败（可能被其他 Agent 占用）"
            host_attempts.append(attempt)
            await report_progress(context.task_id, "STEP2", "RUNNING", attempt["message"], hostAttempts=host_attempts)
            continue

        context.current_xbox = matcher_xbox_to_context(candidate)
        cert = matcher.get_smartglass_certificate(server_id)
        if cert:
            context._smartglass_certificate = cert

        context.update_step_status("step2", TaskStepStatus.RUNNING, f"正在连接 {candidate.name}...")

        try:
            connect_ok, connect_details = await asyncio.wait_for(
                connect_to_xbox_lan(context, task_logger, stream_logger),
                timeout=per_host_timeout,
            )
        except asyncio.TimeoutError:
            connect_ok = False
            connect_details = {
                "errorCode": "HOST_ATTEMPT_TIMEOUT",
                "errorMessage": f"单台主机握手超时（{per_host_timeout}s）",
            }

        if connect_ok:
            attempt["status"] = "success"
            attempt["message"] = "LAN 串流握手成功"
            host_attempts.append(attempt)
            context._lan_direct = True
            context.assigned_xbox = context.current_xbox
            success_msg = f"Xbox LAN 串流连接成功: {candidate.name} ({candidate.ip_address})"
            context.update_step_status("step2", TaskStepStatus.COMPLETED, success_msg)
            pipeline = pipeline_diagnostic_from_context(context)
            await report_progress(
                context.task_id,
                "STEP2",
                "COMPLETED",
                success_msg,
                hostAttempts=host_attempts,
                selectedServerId=server_id,
                pipelineDiagnostic=pipeline,
                firstFrameReady=pipeline.get("firstFrame") == "ok",
                firstFrameSize=pipeline.get("firstFrameSize"),
                inputChannelState=pipeline.get("inputChannelState"),
            )
            bind_client = PlatformApiClient()
            try:
                current = context.current_xbox
                await bind_client.ensure_host_binding(
                    context.streaming_account_id,
                    context.task_id,
                    host_id=getattr(current, "platform_host_id", None) or None,
                    server_id=server_id,
                    platform="xbox",
                    name=getattr(current, "name", None),
                    ip_address=getattr(current, "ip_address", None),
                )
            finally:
                await bind_client.close()
            return Step2Result(success=True, message=success_msg, xbox_info=context.current_xbox)

        await cleanup_lan_connect_attempt(context, task_logger)
        await release_server_id(context, server_id, task_logger)
        error_code = connect_details.get("errorCode", "XBOX_CONNECT_FAILED")
        error_msg = connect_details.get("errorMessage", f"连接 {candidate.name} 失败")
        attempt["status"] = "connect_failed"
        attempt["errorCode"] = error_code
        attempt["message"] = error_msg
        host_attempts.append(attempt)
        await report_progress(
            context.task_id,
            "STEP2",
            "RUNNING",
            f"主机 {candidate.name} 失败，尝试下一台",
            hostAttempts=host_attempts,
            lastErrorCode=error_code,
        )

    fail_msg = f"全部 {len(candidates)} 台候选主机串流失败"
    context.update_step_status("step2", TaskStepStatus.FAILED, fail_msg)
    await report_progress(
        context.task_id,
        "STEP2",
        "FAILED",
        fail_msg,
        errorCode="ALL_HOSTS_FAILED",
        hostAttempts=host_attempts,
    )
    return Step2Result(success=False, error_code="ALL_HOSTS_FAILED", message=fail_msg)
