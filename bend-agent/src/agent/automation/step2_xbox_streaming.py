"""
步骤二：Xbox LAN 串流连接

GSSV 云端设备列表 + SmartGlass UDP 发现 + serverId 交集；
逐台 LAN 握手（SmartGlass + RTP），失败换下一台。
"""

import asyncio
from typing import Callable, Optional, Dict, Any, List

from ..core.task_logger import get_task_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext, Step2Result, XboxInfo, TaskStepStatus
from ..xbox.xbox_host_matcher import XboxHostMatcher, XboxMatchResult, XboxInfo as MatcherXboxInfo

DEFAULT_PLAY_PATH = "v5/sessions/home/play"


def _account_platform(context: AgentTaskContext) -> str:
    """串流账号平台类型：xbox / playstation（由平台维护，用户自行选择）。"""
    return (getattr(context, "account_platform", None) or "xbox").strip().lower()


async def _discover_playstation_lan_step2(
    context: AgentTaskContext,
    task_logger,
    report_progress: Callable,
) -> Step2Result:
    """PlayStation 账号 Step2：按 platform 走 PS LAN 发现；串流未开放则标准报错。"""
    from ..api.platform_api_client import PlatformApiClient
    from ..playstation.ps_lan_discovery import discover_playstation_lan

    task_logger.info("Step2 PlayStation：按 platform=playstation 执行 LAN 发现")
    platform_client = PlatformApiClient()
    try:
        consoles = await discover_playstation_lan(platform_client)
    finally:
        await platform_client.close()

    if not consoles:
        fail_msg = "局域网未发现 PlayStation 主机（请确认平台类型、主机在同一 LAN，或 PS 发现尚未开放）"
        await report_progress(
            context.task_id,
            "STEP2",
            "FAILED",
            fail_msg,
            errorCode="LAN_NO_HOST",
            hostAttempts=[],
        )
        return Step2Result(
            success=False,
            error_code="LAN_NO_HOST",
            message=fail_msg,
        )

    fail_msg = "PlayStation 串流尚未开放，当前仅支持 Xbox LAN 串流"
    await report_progress(
        context.task_id,
        "STEP2",
        "FAILED",
        fail_msg,
        errorCode="PS_STREAM_NOT_SUPPORTED",
        hostAttempts=[],
        intersectionCount=len(consoles),
    )
    return Step2Result(
        success=False,
        error_code="PS_STREAM_NOT_SUPPORTED",
        message=fail_msg,
    )


def _pipeline_diagnostic_from_context(context: AgentTaskContext) -> Dict[str, Any]:
    """构建 TaskDetail 管道诊断（LAN SmartGlass + RTP）。"""
    session = getattr(context, "xbox_session", None)
    first_w = int(getattr(context, "stream_width", 0) or 0)
    first_h = int(getattr(context, "stream_height", 0) or 0)
    if first_w <= 0 or first_h <= 0:
        ctrl = getattr(context, "_video_stream_controller", None)
        if ctrl and getattr(ctrl, "_latest_shape", None):
            first_w, first_h = ctrl._latest_shape

    capture_mode = getattr(context, "_video_capture_mode", "") or ""
    first_ok_modes = ("rtp", "direct")
    first_frame = "ok" if capture_mode in first_ok_modes else "pending"

    input_state = None
    input_ok = False
    if session is not None:
        input_state = getattr(session, "input_channel_state", None)
        if input_state is None and hasattr(session, "is_input_channel_healthy"):
            input_ok = session.is_input_channel_healthy()
            input_state = "open" if input_ok else "closed"
        else:
            input_ok = input_state == "open"

    diag: Dict[str, Any] = {
        "auth": "ok",
        "discovery": "ok" if context.current_xbox else "pending",
        "firstFrame": first_frame,
        "inputDc": "ok" if input_ok else ("pending" if input_state is None else "fail"),
        "firstFrameSize": f"{first_w}x{first_h}" if first_w and first_h else None,
        "inputChannelState": input_state,
        "streamMode": "lan",
        "frameCaptureMode": capture_mode or None,
    }

    smartglass_ok = bool(
        getattr(context, "_smartglass_enabled", False)
        or (session is not None and getattr(session, "is_connected", False))
    )
    dtls_ok = bool(getattr(context, "_lan_srtp_keys", None))
    diag["lanConnect"] = "ok" if smartglass_ok else "pending"
    diag["dtlsSrtp"] = "ok" if dtls_ok else "pending"
    diag["lanIp"] = getattr(context.current_xbox, "ip_address", None) if context.current_xbox else None
    if getattr(context, "_lan_rtp_port", None):
        diag["rtpPort"] = context._lan_rtp_port

    return diag


def _matcher_xbox_to_context(matcher_xbox: MatcherXboxInfo) -> XboxInfo:
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


def _format_xbox_match_message(match_result: XboxMatchResult) -> str:
    """根据 XboxMatchResult 字段格式化匹配失败/成功消息。"""
    reason = match_result.match_reason or "Xbox主机匹配失败"
    if match_result.error_code:
        msg = f"[{match_result.error_code}] {reason}"
    else:
        msg = reason
    suggestion = (match_result.error_details or {}).get("suggestion")
    if suggestion:
        msg += f"; 解决方案: {suggestion}"
    return msg


def _per_host_attempt_timeout_sec() -> float:
    from ..core.config import config as app_config

    return float(app_config.get("lan_stream.per_host_attempt_timeout_sec", 45))


async def _cleanup_lan_connect_attempt(context: AgentTaskContext, task_logger) -> None:
    """单台握手失败后清理部分会话，避免影响下一条主机。"""
    session = getattr(context, "xbox_session", None)
    if session and hasattr(session, "disconnect"):
        try:
            await session.disconnect()
        except Exception as exc:
            task_logger.debug("清理 LAN 会话异常: %s", exc)
    context.xbox_session = None
    for attr in (
        "_smartglass_enabled",
        "_smartglass_udp_connected",
        "_lan_srtp_keys",
        "_lan_rtp_port",
        "_lan_endpoints",
        "_rtp_available",
        "_video_mode",
        "_video_capture_mode",
    ):
        if hasattr(context, attr):
            setattr(context, attr, None if attr != "_rtp_available" else False)


async def _is_xbox_occupied_by_server_id(
    server_id: str,
    context: AgentTaskContext,
    task_logger,
) -> bool:
    """只读占用检测：Redis 租约 + DB 锁；本 task 重入不算占用。"""
    if not server_id:
        return False
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            status = await api_client.get_xbox_status_by_device_id(server_id)
        finally:
            await api_client.close()
    except Exception as e:
        task_logger.warning("占用检测：无法连接平台（%s）: %s", server_id, e)
        return False

    if not status:
        return False

    if not _lease_blocks_task(status, context.task_id):
        return False

    holder_agent = status.get("leaseHolderAgentId") or status.get("lockedByAgentId")
    holder_task = status.get("leaseHolderTaskId") or status.get("lockedByTaskId")
    task_logger.info(
        "主机 %s 已被占用 holderAgent=%s holderTask=%s",
        server_id,
        holder_agent,
        holder_task,
    )
    return True


def _lease_blocks_task(status: dict, task_id: str) -> bool:
    """True 表示租约/锁存在且非本 task 重入。"""
    if status.get("leaseActive") or status.get("locked"):
        holder_task = status.get("leaseHolderTaskId") or status.get("lockedByTaskId")
        if holder_task and holder_task == task_id:
            return False
        return True
    return False


async def _try_acquire_xbox_server_id(
    context: AgentTaskContext,
    server_id: str,
    task_logger,
) -> bool:
    """握手前申请跨 Agent 串流租约（Redis + 平台 CAS）。"""
    if not server_id:
        return False

    try:
        from ..task.automation_scheduler import get_active_scheduler

        scheduler = get_active_scheduler()
        if scheduler:
            local_ok = await scheduler.acquire_xbox_host(server_id, context.task_id)
            if not local_ok:
                task_logger.warning("本地调度器：主机 %s 已被占用", server_id)
                return False
    except Exception as e:
        task_logger.debug("本地调度器占用检查失败: %s", e)

    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            platform_locked = await api_client.lock_xbox_by_device_id(
                server_id, context.task_id
            )
        finally:
            await api_client.close()
        if not platform_locked:
            task_logger.warning("平台串流租约申请失败 serverId=%s", server_id)
            await _release_local_xbox_host(server_id, context.task_id, task_logger)
            return False
        task_logger.info("平台串流租约已持有 serverId=%s task=%s", server_id, context.task_id)
        context._stream_lease_server_id = server_id  # type: ignore[attr-defined]
        return True
    except Exception as e:
        task_logger.warning("平台锁定 serverId=%s 异常: %s", server_id, e)
        await _release_local_xbox_host(server_id, context.task_id, task_logger)
        return False


async def _release_local_xbox_host(server_id: str, task_id: str, task_logger) -> None:
    try:
        from ..task.automation_scheduler import get_active_scheduler

        scheduler = get_active_scheduler()
        if scheduler:
            await scheduler.release_xbox_host(server_id, task_id)
    except Exception as e:
        task_logger.debug("释放本地调度器占用失败: %s", e)


async def _release_xbox_server_id(
    context: AgentTaskContext,
    server_id: str,
    task_logger,
) -> None:
    """释放平台 Redis 租约与本地调度器占用。"""
    if not server_id:
        return
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            unlocked = await api_client.unlock_xbox_by_device_id(server_id, context.task_id)
        finally:
            await api_client.close()
        if unlocked:
            task_logger.info("已释放平台串流租约 serverId=%s", server_id)
    except Exception as e:
        task_logger.warning("释放平台租约失败 serverId=%s: %s", server_id, e)
    await _release_local_xbox_host(server_id, context.task_id, task_logger)
    if getattr(context, "_stream_lease_server_id", None) == server_id:
        context._stream_lease_server_id = None  # type: ignore[attr-defined]


async def discover_intersection_and_connect_lan(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step2Result:
    """
    云端∩LAN 交集发现 + 按序逐台占用检测与 LAN 握手（失败换下一台）。
    按 streaming_account.platform 分流：xbox → SmartGlass；playstation → PS LAN（占位）。
    """
    if _account_platform(context) == "playstation":
        return await _discover_playstation_lan_step2(context, task_logger, report_progress)

    gs_token = _get_gs_token(context)
    if not gs_token:
        return Step2Result(
            success=False,
            error_code="NO_GS_TOKEN",
            message="无可用的 gsToken，请重新执行步骤一",
        )

    from ..api.platform_api_client import PlatformApiClient

    platform_client = PlatformApiClient()
    try:
        matcher = XboxHostMatcher(
            gs_token,
            gssv_base_uri=_get_gssv_base_uri(context),
            platform_client=platform_client,
        )
        discovery_err = await matcher.discover_cloud_and_lan()
    finally:
        await platform_client.close()
    if discovery_err is not None:
        fail_msg = _format_xbox_match_message(discovery_err)
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

    intersections = matcher.build_intersection()
    per_host_timeout = _per_host_attempt_timeout_sec()
    host_attempts: List[Dict[str, Any]] = []

    await report_progress(
        context.task_id,
        "STEP2",
        "RUNNING",
        f"发现 {len(intersections)} 台可串流主机，开始逐台握手",
        hostAttempts=host_attempts,
        intersectionCount=len(intersections),
    )

    for idx, candidate in enumerate(intersections, start=1):
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
            idx,
            len(intersections),
            candidate.name,
            candidate.ip_address,
            server_id,
        )
        stream_logger.info(
            f"尝试串流主机 [{idx}/{len(intersections)}]: {candidate.name} ({candidate.ip_address})"
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
                    context.task_id,
                    "STEP2",
                    "RUNNING",
                    attempt["message"],
                    hostAttempts=host_attempts,
                )
                continue
            powered = True

        if not powered and not matcher._can_wakeup(candidate.power_state):
            attempt["status"] = "offline"
            attempt["errorCode"] = "HOST_OFFLINE"
            attempt["message"] = f"主机未开机: {candidate.power_state}"
            host_attempts.append(attempt)
            await report_progress(
                context.task_id,
                "STEP2",
                "RUNNING",
                attempt["message"],
                hostAttempts=host_attempts,
            )
            continue

        if await _is_xbox_occupied_by_server_id(server_id, context, task_logger):
            attempt["status"] = "occupied"
            attempt["errorCode"] = "XBOX_OCCUPIED"
            attempt["message"] = f"主机 {candidate.name} 已被其他 Agent/任务占用"
            host_attempts.append(attempt)
            await report_progress(
                context.task_id,
                "STEP2",
                "RUNNING",
                attempt["message"],
                hostAttempts=host_attempts,
            )
            continue

        if not await _try_acquire_xbox_server_id(context, server_id, task_logger):
            attempt["status"] = "occupied"
            attempt["errorCode"] = "LEASE_DENIED"
            attempt["message"] = f"主机 {candidate.name} 租约申请失败（可能被其他 Agent 占用）"
            host_attempts.append(attempt)
            await report_progress(
                context.task_id,
                "STEP2",
                "RUNNING",
                attempt["message"],
                hostAttempts=host_attempts,
            )
            continue

        context.current_xbox = _matcher_xbox_to_context(candidate)
        cert = matcher.get_smartglass_certificate(server_id)
        if cert:
            context._smartglass_certificate = cert

        context.update_step_status(
            "step2",
            TaskStepStatus.RUNNING,
            f"正在连接 {candidate.name}...",
        )

        try:
            connect_ok, connect_details = await asyncio.wait_for(
                _connect_to_xbox_lan(context, task_logger, stream_logger),
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
            success_msg = (
                f"Xbox LAN 串流连接成功: {candidate.name} ({candidate.ip_address})"
            )
            task_logger.info(success_msg)
            stream_logger.info(success_msg)
            context.update_step_status("step2", TaskStepStatus.COMPLETED, success_msg)
            pipeline = _pipeline_diagnostic_from_context(context)
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
            return Step2Result(success=True, message=success_msg, xbox_info=context.current_xbox)

        await _cleanup_lan_connect_attempt(context, task_logger)
        await _release_xbox_server_id(context, server_id, task_logger)
        error_code = connect_details.get("errorCode", "XBOX_CONNECT_FAILED")
        error_msg = connect_details.get(
            "errorMessage",
            f"连接 {candidate.name} 失败",
        )
        attempt["status"] = "connect_failed"
        attempt["errorCode"] = error_code
        attempt["message"] = error_msg
        host_attempts.append(attempt)
        task_logger.warning("主机 %s 握手失败: %s", candidate.name, error_msg)
        stream_logger.warning(f"主机 {candidate.name} 握手失败: {error_msg}")
        await report_progress(
            context.task_id,
            "STEP2",
            "RUNNING",
            f"主机 {candidate.name} 失败，尝试下一台",
            hostAttempts=host_attempts,
            lastErrorCode=error_code,
        )

    fail_msg = f"全部 {len(intersections)} 台交集主机串流失败"
    task_logger.error(fail_msg)
    stream_logger.error(fail_msg)
    context.update_step_status("step2", TaskStepStatus.FAILED, fail_msg)
    await report_progress(
        context.task_id,
        "STEP2",
        "FAILED",
        fail_msg,
        errorCode="ALL_HOSTS_FAILED",
        hostAttempts=host_attempts,
    )
    return Step2Result(
        success=False,
        error_code="ALL_HOSTS_FAILED",
        message=fail_msg,
    )


async def step2_execute_streaming(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str], None]
) -> Step2Result:
    """
    步骤二执行：Xbox串流连接

    流程：
    1. 检查是否指定了Xbox主机
       - 已指定：直接使用指定主机
       - 未指定：解析串流账号已登录的Xbox信息，匹配局域网在线Xbox
    2. 如果多个Xbox匹配，随机选择一个
    3. 建立与Xbox的串流连接
    4. 回传主机信息到平台并标记

    参数：
    - context: 任务上下文（包含第一步的认证结果）
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数

    返回：
    - Step2Result: 包含Xbox连接结果的Step2Result
    """
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)
    task_logger.info("=== 步骤二：开始Xbox串流连接 ===")
    stream_logger.info("=== 开始Xbox串流连接 ===")
    
    task_logger.info("=== Token 验证 ===")
    task_logger.info(f"context.microsoft_tokens: {context.microsoft_tokens is not None}")
    task_logger.info(f"context.xbox_tokens: {context.xbox_tokens is not None}")
    if context.microsoft_tokens:
        if hasattr(context.microsoft_tokens, 'access_token'):
            task_logger.info(f"microsoft_tokens.access_token 存在，长度: {len(context.microsoft_tokens.access_token) if context.microsoft_tokens.access_token else 0}")
        else:
            task_logger.warning("microsoft_tokens 对象没有 access_token 属性")
    if context.xbox_tokens:
        if hasattr(context.xbox_tokens, 'user_token'):
            task_logger.info(f"xbox_tokens.user_token 存在，长度: {len(context.xbox_tokens.user_token) if context.xbox_tokens.user_token else 0}")
        if hasattr(context.xbox_tokens, 'xsts_token'):
            task_logger.info(f"xbox_tokens.xsts_token 存在，长度: {len(context.xbox_tokens.xsts_token) if context.xbox_tokens.xsts_token else 0}")
        if hasattr(context.xbox_tokens, 'user_hash'):
            task_logger.info(f"xbox_tokens.user_hash: {context.xbox_tokens.user_hash}")
    task_logger.info("=== Token 验证完成 ===")
    
    platform_label = "PlayStation" if _account_platform(context) == "playstation" else "Xbox"
    context.update_step_status("step2", TaskStepStatus.RUNNING, f"正在匹配{platform_label}主机...")
    await report_progress(context.task_id, "STEP2", "RUNNING", f"正在匹配{platform_label}主机...")

    try:
        if check_cancel():
            task_logger.info("任务被取消，步骤二终止")
            stream_logger.info("任务被取消")
            context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        return await discover_intersection_and_connect_lan(
            context,
            task_logger,
            stream_logger,
            check_cancel,
            report_progress,
        )

    except asyncio.CancelledError:
        # CancelledError 只标记本步骤跳过，调度器负责统一释放当前任务资源。
        task_logger.info("步骤二被取消")
        stream_logger.info("步骤二被取消")
        context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
        return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as e:
        error_msg = f"步骤二执行超时: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="TIMEOUT", message=error_msg)

    except ConnectionError as e:
        error_msg = f"步骤二网络连接失败: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="CONNECTION_ERROR", message=error_msg)

    except ValueError as e:
        error_msg = f"步骤二参数错误: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="VALUE_ERROR", message=error_msg)

    except Exception as e:
        error_msg = f"步骤二执行异常: {str(e)}"
        task_logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="EXCEPTION", message=error_msg)

async def _connect_to_xbox_lan(context: AgentTaskContext, task_logger, stream_logger) -> tuple:
    """
    通过局域网 SmartGlass + RTP 连接 Xbox（匹配阶段已拿到 ip_address）。

    返回：
    - tuple: (success: bool, details: dict)
    """
    connect_details: Dict[str, Any] = {
        "streamMode": "lan",
        "smartglassEnabled": False,
        "rtpEnabled": False,
        "lanIp": "",
        "errorCode": "",
        "errorMessage": "",
    }

    try:
        xbox_info = context.current_xbox
        if not xbox_info or not xbox_info.ip_address:
            connect_details["errorCode"] = "NO_LAN_IP"
            connect_details["errorMessage"] = "缺少局域网 IP，无法 SmartGlass 握手"
            return False, connect_details

        connect_details["lanIp"] = xbox_info.ip_address
        port = 5050

        from ..core.config import config as app_config
        from ..xbox.stream_controller import XboxStreamController, StreamConfig

        task_logger.info("┌─────────────────────────────────────────────────────────────┐")
        task_logger.info("│ 步骤2.0: 局域网串流连接（SmartGlass + RTP）                  │")
        task_logger.info("└─────────────────────────────────────────────────────────────┘")
        task_logger.info(
            f"目标 Xbox: {xbox_info.name} @ {xbox_info.ip_address}:{port} "
            f"(serverId={xbox_info.id})"
        )
        stream_logger.info(f"开始 LAN 串流: {xbox_info.name} @ {xbox_info.ip_address}")

        controller = XboxStreamController()
        xsts_token = None
        user_hash = None
        if context.xbox_tokens:
            xsts_token = getattr(context.xbox_tokens, "xsts_token", None)
            user_hash = getattr(context.xbox_tokens, "user_hash", None)

        connect_details["authTokenType"] = "xsts" if xsts_token else "none"

        # OpenXbox SmartGlass UDP Connect（0xCC00）— 主机 XSTS 授权
        if (
            bool(app_config.get("lan_stream.smartglass_udp_connect", True))
            and xsts_token
            and user_hash
        ):
            from ..xbox.smartglass_connect import connect_smartglass_udp

            cert = getattr(context, "_smartglass_certificate", None)
            udp_result = await connect_smartglass_udp(
                xbox_info.ip_address,
                user_hash,
                xsts_token,
                certificate=cert,
            )
            connect_details["smartglassUdpConnect"] = udp_result.success
            connect_details["smartglassUdpMessage"] = udp_result.message
            if udp_result.success:
                context._smartglass_udp_connected = True
                task_logger.info("✓ SmartGlass UDP Connect (XSTS): %s", udp_result.message)
            else:
                task_logger.warning("SmartGlass UDP Connect 未成功: %s", udp_result.message)

        if xsts_token and user_hash:
            connected = await controller.connect_with_token(
                xbox_info.ip_address, xsts_token, user_hash, port
            )
        else:
            task_logger.warning("无 XSTS/userhash，尝试基础 SmartGlass 握手")
            connected = await controller.connect(xbox_info.ip_address, port)

        connect_details["smartglassEnabled"] = connected
        context._smartglass_enabled = connected
        if not connected:
            connect_details["errorCode"] = "SMARTGLASS_CONNECT_FAILED"
            connect_details["errorMessage"] = f"SmartGlass 连接失败: {xbox_info.ip_address}"
            task_logger.error(connect_details["errorMessage"])
            stream_logger.error(connect_details["errorMessage"])
            return False, connect_details

        stream_config = StreamConfig(
            xbox_ip=xbox_info.ip_address,
            xbox_port=port,
            audio_enabled=False,
        )
        if not await controller.start_stream(stream_config):
            connect_details["errorCode"] = "STREAM_START_FAILED"
            connect_details["errorMessage"] = "SmartGlass 串流启动失败"
            task_logger.error(connect_details["errorMessage"])
            return False, connect_details

        from ..xbox.lan_media_session import (
            establish_lan_media_security,
            wait_for_first_rtp_packet,
        )

        task_logger.info("┌─────────────────────────────────────────────────────────────┐")
        task_logger.info("│ 步骤2.1: DTLS-SRTP 握手（对照 xsrp/libxsrp）               │")
        task_logger.info("└─────────────────────────────────────────────────────────────┘")

        dtls_ok, srtp_keys, dtls_msg, lan_endpoints = await establish_lan_media_security(
            controller,
            stream_config,
            xbox_info.ip_address,
            auth_token=xsts_token,
            user_hash=user_hash,
        )
        connect_details["dtlsEnabled"] = dtls_ok
        connect_details["dtlsMessage"] = dtls_msg
        connect_details["dtlsPort"] = lan_endpoints.dtls_port
        connect_details["rtpPort"] = lan_endpoints.rtp_port
        if not dtls_ok:
            connect_details["errorCode"] = "DTLS_SRTP_FAILED"
            connect_details["errorMessage"] = dtls_msg
            task_logger.error(connect_details["errorMessage"])
            stream_logger.error(connect_details["errorMessage"])
            return False, connect_details

        context._lan_srtp_keys = srtp_keys
        context._lan_rtp_port = lan_endpoints.rtp_port
        context._lan_endpoints = lan_endpoints
        task_logger.info(
            f"✓ DTLS-SRTP 握手成功 (dtls={lan_endpoints.dtls_port}, rtp={lan_endpoints.rtp_port})"
        )
        stream_logger.info(dtls_msg)

        context.xbox_session = controller
        context._lan_direct = True

        video_ok = await _start_video_receiver(context, task_logger, stream_logger)
        connect_details["rtpEnabled"] = bool(getattr(context, "_rtp_available", False))
        connect_details["videoMode"] = getattr(context, "_video_mode", "unknown")
        if not video_ok:
            connect_details["errorCode"] = "VIDEO_RECEIVER_FAILED"
            connect_details["errorMessage"] = "LAN 视频接收器启动失败"
            task_logger.error(connect_details["errorMessage"])
            return False, connect_details

        first_rtp = await wait_for_first_rtp_packet(controller)
        connect_details["firstRtpPacket"] = first_rtp
        if not first_rtp:
            connect_details["errorCode"] = "FIRST_RTP_TIMEOUT"
            connect_details["errorMessage"] = "DTLS 成功但未收到首包 RTP/SRTP"
            task_logger.warning(connect_details["errorMessage"])
            stream_logger.warning(connect_details["errorMessage"])
            return False, connect_details

        task_logger.info(f"✓ Xbox LAN 串流连接成功: {xbox_info.ip_address}")
        stream_logger.info(f"Xbox LAN 串流连接成功: {xbox_info.ip_address}")
        return True, connect_details

    except asyncio.TimeoutError as e:
        connect_details["errorCode"] = "TIMEOUT"
        connect_details["errorMessage"] = f"LAN 连接 Xbox 超时: {e}"
        task_logger.error(connect_details["errorMessage"])
        return False, connect_details
    except Exception as e:
        connect_details["errorCode"] = "EXCEPTION"
        connect_details["errorMessage"] = f"LAN 连接 Xbox 异常: {e}"
        task_logger.error(connect_details["errorMessage"], exc_info=True)
        return False, connect_details

async def _init_video_stream_controller(context: AgentTaskContext, task_logger, stream_logger) -> bool:
    """
    初始化视频流控制器（方案C优化）

    功能说明：
    - 创建高性能视频流控制器
    - 支持RTP视频流接收
    - 支持win32gui直接捕获
    - 提供多线程解码加速

    参数：
    - context: 任务上下文
    - task_logger: 日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        from ..vision.video_stream_controller import (
            VideoStreamController, 
            DirectCaptureController,
            VideoStreamConfig
        )

        task_logger.info("初始化视频流控制器...")
        stream_logger.info("初始化视频流控制器...")

        if context._rtp_available and context.xbox_session:
            rtp_session = getattr(context.xbox_session, '_rtp_session', None)
            if rtp_session:
                video_config = VideoStreamConfig(
                    width=1280,
                    height=720,
                    framerate=30,
                    bitrate=5000000,
                    codec="H264",
                    rtp_port=50500
                )

                video_controller = VideoStreamController()
                success = await video_controller.start(video_config, rtp_session)

                if success:
                    context._video_stream_controller = video_controller
                    context._video_capture_mode = "rtp"
                    task_logger.info("视频流控制器（RTP模式）初始化成功")
                    stream_logger.info("RTP视频流接收已启用")
                    return True
                else:
                    task_logger.warning("视频流控制器初始化失败，尝试win32gui模式")

        direct_capture = DirectCaptureController()
        context._direct_capture = direct_capture
        context._video_capture_mode = "direct"
        task_logger.info("直接捕获控制器已初始化")
        stream_logger.info("win32gui直接捕获模式已启用")

        return True

    except Exception as e:
        task_logger.warning(f"视频流控制器初始化失败: {e}")
        stream_logger.warning(f"视频流控制器初始化失败: {e}")
        context._video_capture_mode = "fallback"
        return True


async def _start_video_receiver(context: AgentTaskContext, task_logger, stream_logger) -> bool:
    """
    启动视频流接收器（方案3：混合模式）

    功能说明：
    - 支持两种视频流接收模式：RTP 和 win32gui
    - RTP模式：直接接收Xbox视频流，性能更好
    - win32gui模式：从Xbox Streaming窗口截图，兼容性更好
    - 优先尝试RTP，失败时自动降级到win32gui

    参数：
    - context: 任务上下文
    - task_logger: 日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        if not context.xbox_session:
            task_logger.warning("Xbox会话未初始化，跳过视频流接收器启动")
            return False

        task_logger.info("开始初始化视频流接收器...")
        stream_logger.info("开始初始化视频流接收器...")

        srtp_keys = getattr(context, "_lan_srtp_keys", None)
        rtp_port = getattr(context, "_lan_rtp_port", rtp_port)

        video_success = await context.xbox_session.start_video_receiver(
            mode="rtp",
            port=rtp_port,
            srtp_keys=srtp_keys,
            allow_fallback=False,
        )

        video_mode = context.xbox_session.video_mode
        task_logger.info(f"视频流接收器初始化完成，模式: {video_mode}")
        stream_logger.info(f"视频流接收器初始化完成，模式: {video_mode}")

        context._video_mode = video_mode
        context._rtp_available = video_mode == "rtp"

        if video_mode == "rtp":
            task_logger.info("使用RTP视频流接收，性能更优")
            stream_logger.info("RTP视频流接收已启用")
        elif video_mode == "win32gui":
            task_logger.info("使用win32gui截图模式，兼容性更强")
            stream_logger.info("win32gui截图模式已启用")

        await _init_video_stream_controller(context, task_logger, stream_logger)

        return video_success

    except Exception as e:
        task_logger.warning(f"视频流接收器初始化失败: {e}")
        stream_logger.warning(f"视频流接收器初始化失败: {e}")
        context._video_mode = "win32gui"
        context._rtp_available = False
        context._video_capture_mode = "fallback"
        return False


async def _release_xbox_host(context: AgentTaskContext):
    """释放 Xbox 串流租约（跨 Agent）。"""
    task_logger = get_task_logger(context.task_id)
    server_id = getattr(context, "_stream_lease_server_id", None)
    if not server_id and context.current_xbox:
        server_id = context.current_xbox.id
    if server_id:
        await _release_xbox_server_id(context, server_id, task_logger)


def _get_gs_token(context: AgentTaskContext) -> Optional[str]:
    """从上下文获取 gsToken（Xbox Live 云端 API 专用，不可用 access_token 替代）"""
    if context.xbox_tokens and hasattr(context.xbox_tokens, 'gs_token'):
        token = context.xbox_tokens.gs_token
        if token:
            return token
    return None


def _get_gssv_base_uri(context: AgentTaskContext) -> str:
    from ..gssv.base_uri import resolve_gssv_base_uri

    return resolve_gssv_base_uri(context)
