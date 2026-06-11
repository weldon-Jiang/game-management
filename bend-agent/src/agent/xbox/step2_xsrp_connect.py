"""
xblive/xsrp 栈 Step2 核心：GSSV 云端发现 + 租约 + play/WebRTC 握手 + 首帧/输入。

对齐 streaming/xsrp.py OpenStreaming 的 GSSV/WebRTC 段（Python aiortc 实现）。
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional

from ..api.platform_api_client import PlatformApiClient
from ..core.config import config as app_config
from ..task.task_context import AgentTaskContext, Step2Result, TaskStepStatus, XboxInfo
from .console_lease import (
    is_host_occupied_by_server_id,
    release_server_id,
    try_acquire_server_id,
)
from .xsrp_pipeline_diagnostic import pipeline_diagnostic_from_context as _xsrp_pipeline_diag
from .streaming_credentials import (
    StreamingAuthError,
    StreamingAuthCredentials,
    apply_play_path_to_candidates,
    attach_streaming_credentials,
    prioritize_candidates_by_step1,
)
from .xbox_host_matcher import XboxHostMatcher, XboxMatchResult, XboxInfo as MatcherXboxInfo
from .xsrp_cloud_connect import cleanup_xsrp_cloud_attempt, connect_xsrp_cloud

DEFAULT_PLAY_PATH = "v5/sessions/home/play"


def matcher_xbox_to_context(matcher_xbox: MatcherXboxInfo) -> XboxInfo:
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
    return float(
        app_config.get(
            "gssv.cloud_webrtc_timeout_sec",
            app_config.get("lan_stream.per_host_attempt_timeout_sec", 90),
        )
    )


def _resolve_credentials(context: AgentTaskContext):
    try:
        creds = attach_streaming_credentials(context)
        context._streaming_stack = "xsrp"
        err = creds.validate_for_cloud()
        if err:
            return None, Step2Result(success=False, error_code="NO_GS_TOKEN", message=err)
        return creds, None
    except StreamingAuthError as exc:
        return None, Step2Result(
            success=False,
            error_code=exc.error_code,
            message=exc.message,
        )


async def discover_and_connect_xsrp(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step2Result:
    """
    xsrp Step2：GSSV 云端发现 → 逐台租约 → play/WebRTC → 解码首帧 + 输入通道。
    """
    creds, cred_err = _resolve_credentials(context)
    if cred_err is not None:
        return cred_err

    platform_client = PlatformApiClient()
    try:
        matcher = XboxHostMatcher(
            creds.gs_token,
            gssv_base_uri=creds.gssv_base_uri,
            platform_client=platform_client,
        )
        discovery_err = await matcher.discover_cloud_only()
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
            streamingStack="xsrp",
        )
        return Step2Result(
            success=False,
            error_code=discovery_err.error_code or "DISCOVERY_FAILED",
            message=fail_msg,
        )

    candidates = _build_xsrp_candidates(context, matcher, creds)
    if not candidates:
        fail_msg = "xsrp：GSSV 无可用 Xbox 主机候选"
        context.update_step_status("step2", TaskStepStatus.FAILED, fail_msg)
        await report_progress(
            context.task_id,
            "STEP2",
            "FAILED",
            fail_msg,
            errorCode="NO_XSRP_CANDIDATES",
            hostAttempts=[],
            streamingStack="xsrp",
        )
        return Step2Result(success=False, error_code="NO_XSRP_CANDIDATES", message=fail_msg)

    apply_play_path_to_candidates(candidates, creds)
    candidates = prioritize_candidates_by_step1(candidates, creds)
    if creds.step1_console_preloaded:
        task_logger.info(
            "xsrp Step1 已预查 serverId=%s，优先 GSSV play/WebRTC",
            creds.server_id,
        )

    per_host_timeout = per_host_attempt_timeout_sec()
    host_attempts: List[Dict[str, Any]] = []

    await report_progress(
        context.task_id,
        "STEP2",
        "RUNNING",
        f"xsrp 发现 {len(candidates)} 台主机，开始 GSSV play/WebRTC",
        hostAttempts=host_attempts,
        cloudCandidateCount=len(candidates),
        streamingStack="xsrp",
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
            "xsrp 尝试 %s/%s: %s (serverId=%s power=%s)",
            idx,
            len(candidates),
            candidate.name,
            server_id,
            candidate.power_state,
        )

        powered = matcher._is_powered_on(candidate.power_state)
        if not powered and matcher._can_wakeup(candidate.power_state):
            wakeup_payload = await matcher._ensure_powered_on(
                candidate, wakeup=True, wakeup_timeout=30
            )
            if not wakeup_payload["ok"]:
                attempt["status"] = "wakeup_failed"
                attempt["errorCode"] = "WAKEUP_FAILED"
                attempt["message"] = wakeup_payload["result"].match_reason
                host_attempts.append(attempt)
                await report_progress(
                    context.task_id, "STEP2", "RUNNING", attempt["message"],
                    hostAttempts=host_attempts, streamingStack="xsrp",
                )
                continue
            powered = True

        if not powered and not matcher._can_wakeup(candidate.power_state):
            attempt["status"] = "offline"
            attempt["errorCode"] = "HOST_OFFLINE"
            attempt["message"] = f"主机未开机: {candidate.power_state}"
            host_attempts.append(attempt)
            await report_progress(
                context.task_id, "STEP2", "RUNNING", attempt["message"],
                hostAttempts=host_attempts, streamingStack="xsrp",
            )
            continue

        if await is_host_occupied_by_server_id(server_id, context, task_logger):
            attempt["status"] = "occupied"
            attempt["errorCode"] = "XBOX_OCCUPIED"
            attempt["message"] = f"主机 {candidate.name} 已被其他 Agent/任务占用"
            host_attempts.append(attempt)
            await report_progress(
                context.task_id, "STEP2", "RUNNING", attempt["message"],
                hostAttempts=host_attempts, streamingStack="xsrp",
            )
            continue

        if not await try_acquire_server_id(context, server_id, task_logger):
            attempt["status"] = "occupied"
            attempt["errorCode"] = "LEASE_DENIED"
            attempt["message"] = f"主机 {candidate.name} 租约申请失败"
            host_attempts.append(attempt)
            await report_progress(
                context.task_id, "STEP2", "RUNNING", attempt["message"],
                hostAttempts=host_attempts, streamingStack="xsrp",
            )
            continue

        context.current_xbox = matcher_xbox_to_context(candidate)
        context.update_step_status(
            "step2", TaskStepStatus.RUNNING, f"xsrp 正在连接 {candidate.name}...",
        )

        try:
            connect_ok, connect_details = await asyncio.wait_for(
                connect_xsrp_cloud(context, creds, task_logger, stream_logger),
                timeout=per_host_timeout,
            )
        except asyncio.TimeoutError:
            connect_ok = False
            connect_details = {
                "errorCode": "HOST_ATTEMPT_TIMEOUT",
                "errorMessage": f"xsrp 单台握手超时（{per_host_timeout}s）",
            }

        if connect_ok:
            attempt["status"] = "success"
            attempt["message"] = "xsrp 串流握手成功"
            host_attempts.append(attempt)
            context._lan_direct = False
            context.assigned_xbox = context.current_xbox
            handshake_msg = f"xsrp WebRTC 握手成功: {candidate.name} ({server_id})"
            context.update_step_status(
                "step2", TaskStepStatus.RUNNING, f"{handshake_msg}，正在初始化串流环境...",
            )
            pipeline = _xsrp_pipeline_diag(context)
            await report_progress(
                context.task_id,
                "STEP2",
                "RUNNING",
                handshake_msg,
                hostAttempts=host_attempts,
                selectedServerId=server_id,
                pipelineDiagnostic=pipeline,
                firstFrameReady=pipeline.get("firstFrame") == "ok",
                firstFrameSize=pipeline.get("firstFrameSize"),
                inputChannelState=pipeline.get("inputChannelState"),
                streamingStack="xsrp",
            )

            step3_result = await _run_xsrp_step3_after_connect(
                context, check_cancel, report_progress, task_logger, stream_logger,
            )
            if not step3_result.success:
                await cleanup_xsrp_cloud_attempt(context, task_logger)
                await release_server_id(context, server_id, task_logger)
                context.update_step_status("step2", TaskStepStatus.FAILED, step3_result.message)
                return Step2Result(
                    success=False,
                    error_code=step3_result.error_code or "STEP3_FAILED",
                    message=step3_result.message,
                )

            success_msg = f"xsrp 串流就绪: {candidate.name} ({server_id})"
            context.update_step_status("step2", TaskStepStatus.COMPLETED, success_msg)
            pipeline = _xsrp_pipeline_diag(context, step3_merged=True)
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
                streamingStack="xsrp",
                step3Merged=True,
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

        await cleanup_xsrp_cloud_attempt(context, task_logger)
        await release_server_id(context, server_id, task_logger)
        error_code = connect_details.get("errorCode", "XSRP_CONNECT_FAILED")
        error_msg = connect_details.get("errorMessage", f"xsrp 连接 {candidate.name} 失败")
        attempt["status"] = "connect_failed"
        attempt["errorCode"] = error_code
        attempt["message"] = error_msg
        host_attempts.append(attempt)
        await report_progress(
            context.task_id,
            "STEP2",
            "RUNNING",
            f"主机 {candidate.name} xsrp 失败，尝试下一台",
            hostAttempts=host_attempts,
            lastErrorCode=error_code,
            streamingStack="xsrp",
        )

    fail_msg = f"xsrp：全部 {len(candidates)} 台候选主机串流失败"
    context.update_step_status("step2", TaskStepStatus.FAILED, fail_msg)
    await report_progress(
        context.task_id,
        "STEP2",
        "FAILED",
        fail_msg,
        errorCode="ALL_HOSTS_FAILED",
        hostAttempts=host_attempts,
        streamingStack="xsrp",
    )
    return Step2Result(success=False, error_code="ALL_HOSTS_FAILED", message=fail_msg)


async def _run_xsrp_step3_after_connect(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
    task_logger,
    stream_logger,
):
    """
    Step2 握手成功后立即跑 Step3（对齐 streaming OpenStreaming 单链）。

    平台仍分别收到 STEP2/STEP3 进度；SessionPhase.READY 门闩不变。
    """
    from ..auth.step3_router import resolve_step3_streaming_init
    from ..task.task_context import Step3Result

    step3_init = resolve_step3_streaming_init()
    task_logger.info("xsrp Step2 握手完成，链接执行 Step3 串流环境初始化")
    stream_logger.info("xsrp Step2→Step3 执行层合并：开始串流环境初始化")
    result = await step3_init(context, check_cancel, report_progress)
    if isinstance(result, Step3Result):
        return result
    success = bool(getattr(result, "success", False))
    return Step3Result(
        success=success,
        message=getattr(result, "message", ""),
        error_code=getattr(result, "error_code", None),
    )


def _build_xsrp_candidates(
    context: AgentTaskContext,
    matcher: XboxHostMatcher,
    creds: StreamingAuthCredentials,
) -> List[MatcherXboxInfo]:
    """优先 GSSV 云端列表；Step1 预查主机可兜底单条候选。"""
    candidates = matcher.build_cloud_candidates(context)
    if candidates:
        return candidates
    if not creds.step1_console_preloaded or not creds.server_id:
        return []
    for xbox in matcher._authorized_xboxes:
        sid = matcher.normalize_server_id(xbox.device_id or xbox.id or "")
        if sid == creds.server_id:
            return [xbox]
    hint = MatcherXboxInfo(
        id=creds.server_id,
        device_id=creds.server_id,
        name=f"Xbox ({creds.server_id})",
        play_path=creds.play_path,
        power_state="On",
    )
    return [hint]
