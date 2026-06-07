"""
步骤二：Xbox串流连接
====================

功能说明：
- 通过云端 API 匹配 Xbox 主机（对齐 streaming/xsplayer.py）
- 校验 Xbox 主机是否已被其他任务串流
- 创建 PlaySession 并执行 SDP 握手建立云端串流
- 回传主机信息到平台并标记防止抢夺

方法拆分：
- step2_execute_streaming(): 执行串流主流程
- _match_xbox_host(): 匹配 Xbox 主机（纯云端）
- _connect_to_xbox(): PlaySession + SDP 串流连接
- _create_play_session(): 创建 PlaySession
- _exchange_sdp(): SDP 握手
- _bind_xbox_to_platform(): 绑定 Xbox 到平台（防止抢夺）
- _check_xbox_availability(): 检查 Xbox 主机是否可用（未被其他任务占用）

作者：技术团队
版本：6.0

版本历史：
- 5.0: 云端 + 局域网交集匹配
- 6.0: 对齐 streaming 纯云端发现与 PlaySession+SDP 串流，移除 SmartGlass 硬依赖
"""

import asyncio
from typing import Callable, Optional, Dict, Any, List

from ..core.logger import get_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext, Step2Result, XboxInfo, TaskStepStatus
from ..xbox.xbox_host_matcher import XboxHostMatcher, XboxMatchResult, XboxInfo as MatcherXboxInfo

DEFAULT_PLAY_PATH = "v5/sessions/home/play"


def _matcher_xbox_to_context(matcher_xbox: MatcherXboxInfo) -> XboxInfo:
    """将 matcher 的 XboxInfo 映射为 task_context.XboxInfo。"""
    return XboxInfo(
        id=matcher_xbox.id or matcher_xbox.device_id,
        name=matcher_xbox.name,
        ip_address=matcher_xbox.ip_address,
        live_id=matcher_xbox.live_id or matcher_xbox.device_id,
        mac_address=matcher_xbox.mac_address,
        play_path=matcher_xbox.play_path or DEFAULT_PLAY_PATH,
        power_state=matcher_xbox.power_state,
        console_type=matcher_xbox.console_type,
    )


def _format_xbox_match_message(match_result: XboxMatchResult) -> str:
    """Format Xbox match failure/success message from XboxMatchResult fields."""
    reason = match_result.match_reason or "Xbox主机匹配失败"
    if match_result.error_code:
        msg = f"[{match_result.error_code}] {reason}"
    else:
        msg = reason
    suggestion = (match_result.error_details or {}).get("suggestion")
    if suggestion:
        msg += f"; 解决方案: {suggestion}"
    return msg


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
    logger = get_logger(f'step2_streaming_{context.task_id}')
    stream_logger = get_stream_logger(context.streaming_account_email)
    logger.info("=== 步骤二：开始Xbox串流连接 ===")
    stream_logger.info("=== 开始Xbox串流连接 ===")
    
    logger.info("=== Token 验证 ===")
    logger.info(f"context.microsoft_tokens: {context.microsoft_tokens is not None}")
    logger.info(f"context.xbox_tokens: {context.xbox_tokens is not None}")
    if context.microsoft_tokens:
        if hasattr(context.microsoft_tokens, 'access_token'):
            logger.info(f"microsoft_tokens.access_token 存在，长度: {len(context.microsoft_tokens.access_token) if context.microsoft_tokens.access_token else 0}")
        else:
            logger.warning("microsoft_tokens 对象没有 access_token 属性")
    if context.xbox_tokens:
        if hasattr(context.xbox_tokens, 'user_token'):
            logger.info(f"xbox_tokens.user_token 存在，长度: {len(context.xbox_tokens.user_token) if context.xbox_tokens.user_token else 0}")
        if hasattr(context.xbox_tokens, 'xsts_token'):
            logger.info(f"xbox_tokens.xsts_token 存在，长度: {len(context.xbox_tokens.xsts_token) if context.xbox_tokens.xsts_token else 0}")
        if hasattr(context.xbox_tokens, 'user_hash'):
            logger.info(f"xbox_tokens.user_hash: {context.xbox_tokens.user_hash}")
    logger.info("=== Token 验证完成 ===")
    
    context.update_step_status("step2", TaskStepStatus.RUNNING, "正在匹配Xbox主机...")
    await report_progress(context.task_id, "STEP2", "RUNNING", "正在匹配Xbox主机...")

    try:
        if check_cancel():
            logger.info("任务被取消，步骤二终止")
            stream_logger.info("任务被取消")
            context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        from ..discovery.console_resolver import resolve_console_target
        from ..xhome_stream.session_connect import establish_webrtc_stream

        resolved = await resolve_console_target(context, check_cancel, report_progress)
        if not resolved.success:
            fail_msg = resolved.message
            logger.error(f"Xbox主机匹配失败: {fail_msg}")
            stream_logger.error(f"Xbox主机匹配失败: {fail_msg}")
            context.update_step_status("step2", TaskStepStatus.FAILED, fail_msg)
            await report_progress(context.task_id, "STEP2", "FAILED", fail_msg)
            return Step2Result(
                success=False,
                error_code=resolved.error_code or "XBOX_MATCH_FAILED",
                message=fail_msg,
            )

        logger.info(
            f"Xbox匹配成功: {context.current_xbox.name} (serverId={context.current_xbox.id})"
        )
        stream_logger.info(
            f"Xbox匹配成功: {context.current_xbox.name} (serverId={context.current_xbox.id})"
        )

        if check_cancel():
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step2", TaskStepStatus.RUNNING,
                                  f"正在连接{context.current_xbox.name}...")
        stream_logger.info(f"正在连接Xbox: {context.current_xbox.name}")

        connect_success, connect_details = await establish_webrtc_stream(
            context, check_cancel, report_progress
        )

        if not connect_success:
            error_code = connect_details.get("errorCode", "XBOX_CONNECT_FAILED")
            error_msg = connect_details.get(
                "errorMessage",
                f"连接 Xbox 失败: {context.current_xbox.name}",
            )
            logger.error(error_msg)
            stream_logger.error(error_msg)
            context.update_step_status("step2", TaskStepStatus.FAILED, error_msg)
            await report_progress(
                context.task_id, "STEP2", "FAILED", error_msg,
                {
                    "xboxServerId": context.current_xbox.id,
                    "xboxName": context.current_xbox.name,
                    "errorCode": error_code,
                }
            )
            return Step2Result(success=False, error_code=error_code, message=error_msg)

        success_msg = f"Xbox串流连接成功: {context.current_xbox.name}"
        logger.info(success_msg)
        stream_logger.info(success_msg)
        context.update_step_status("step2", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP2", "COMPLETED", success_msg)

        return Step2Result(success=True, message=success_msg, xbox_info=context.current_xbox)

    except asyncio.CancelledError:
        logger.info("步骤二被取消")
        stream_logger.info("步骤二被取消")
        context.update_step_status("step2", TaskStepStatus.SKIPPED, "任务被取消")
        return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as e:
        error_msg = f"步骤二执行超时: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="TIMEOUT", message=error_msg)

    except ConnectionError as e:
        error_msg = f"步骤二网络连接失败: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="CONNECTION_ERROR", message=error_msg)

    except ValueError as e:
        error_msg = f"步骤二参数错误: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="VALUE_ERROR", message=error_msg)

    except Exception as e:
        error_msg = f"步骤二执行异常: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step2", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
        return Step2Result(success=False, error_code="EXCEPTION", message=error_msg)


async def _match_xbox_host(
    context: AgentTaskContext,
    logger,
    stream_logger,
    check_cancel: Callable[[], bool]
) -> XboxMatchResult:
    """
    匹配Xbox主机（智能匹配 + 自动唤醒）

    匹配流程：
    1. 如果指定了Xbox主机：先校验云端授权 → 再校验局域网在线 → 再校验未占用
    2. 如果未指定：取云端授权与局域网在线的交集，过滤占用主机后随机选择
    3. 选中的主机若处于待机状态，自动唤醒

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号日志记录器
    - check_cancel: 取消检查函数

    返回：
    - XboxMatchResult: 包含匹配结果的对象
    """
    gs_token = _get_gs_token(context)

    if not gs_token:
        error_msg = "无可用的 gsToken，无法进行 Xbox 匹配，请重新执行步骤一获取 xHome Token"
        logger.error(error_msg)
        return XboxMatchResult(
            success=False,
            xbox_info=None,
            match_reason=error_msg,
            error_code="NO_TOKEN",
            error_details={"suggestion": "重新运行步骤一完成流媒体账号登录"},
        )

    # 占用检测回调：只读检查（不锁定），平台不可达时返回 False
    async def _occupancy_checker(xbox) -> bool:
        xbox_id = xbox.id or xbox.live_id or xbox.mac_address
        if not xbox_id:
            return False
        return await _is_xbox_occupied(xbox_id, context, logger)

    assigned = context.assigned_xbox
    if assigned is not None:
        logger.info(f"检测到指定的 Xbox 主机: {assigned.name} "
                    f"(id={assigned.id or assigned.live_id})")
    else:
        logger.info("未指定Xbox主机，开始智能匹配...")
        stream_logger.info("未指定Xbox主机，开始智能匹配...")

    match_result = await _smart_match_xbox_with_wakeup(
        context,
        gs_token,
        logger,
        stream_logger,
        assigned_xbox=assigned,
        check_occupancy=_occupancy_checker,
        wakeup_enabled=True,
        wakeup_timeout=30,
    )

    if match_result and match_result.success and match_result.xbox_info:
        xbox_info = match_result.xbox_info
        stream_logger.info(f"匹配成功: {xbox_info.name}")
        if not match_result.match_reason:
            match_result.match_reason = f"Xbox 匹配: {xbox_info.name}"
        return match_result

    if match_result:
        return match_result
    return XboxMatchResult(
        success=False,
        xbox_info=None,
        match_reason="没有找到可用的授权 Xbox 主机",
        error_code="UNKNOWN",
    )


async def _discover_xbox_devices(context: AgentTaskContext, logger, stream_logger) -> List[XboxInfo]:
    """
    发现局域网中的Xbox设备

    参数：
    - context: 任务上下文（包含认证 token）
    - logger: 日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - List[XboxInfo]: Xbox设备列表
    """
    try:
        from ..xbox.xbox_discovery import XboxDiscovery

        discovery = XboxDiscovery()

        gs_token = None
        
        if context.xbox_tokens:
            if hasattr(context.xbox_tokens, 'gs_token') and context.xbox_tokens.gs_token:
                gs_token = context.xbox_tokens.gs_token
                logger.info(f"从 xbox_tokens 获取 gs_token 成功，长度: {len(gs_token)}")
            else:
                logger.warning("xbox_tokens 存在但无有效的 gs_token")
        elif context.microsoft_tokens:
            if hasattr(context.microsoft_tokens, 'access_token') and context.microsoft_tokens.access_token:
                gs_token = context.microsoft_tokens.access_token
                logger.warning("使用旧的 access_token（不是 gs_token），Xbox Live API 可能返回 401")
                logger.info(f"从 microsoft_tokens 获取 access_token 成功，长度: {len(gs_token)}")
            else:
                logger.warning("microsoft_tokens 存在但无有效的 access_token")
        else:
            logger.warning("context.microsoft_tokens 和 xbox_tokens 都为空")
            
        if gs_token:
            logger.info("已获取 gs_token，将使用云端发现Xbox")
            discovery.set_access_token(gs_token)
        else:
            logger.warning("无可用访问令牌，云端发现将被跳过，只能使用SSDP/局域网发现")

        devices = await discovery.discover(use_cloud_first=True)

        xbox_list = []
        for device in devices:
            if hasattr(device, 'ip_address'):
                xbox_info = XboxInfo(
                    id=device.device_id or "",
                    name=device.name or "Xbox",
                    ip_address=device.ip_address,
                    live_id=device.live_id or "",
                    mac_address=""
                )
            else:
                xbox_info = XboxInfo(
                    id=device.get("id", ""),
                    name=device.get("name", "Xbox"),
                    ip_address=device.get("ip", ""),
                    live_id=device.get("live_id", ""),
                    mac_address=device.get("mac", "")
                )
            xbox_list.append(xbox_info)

        logger.info(f"Xbox发现完成: {len(xbox_list)} 台")
        return xbox_list

    except asyncio.TimeoutError as e:
        logger.error(f"Xbox发现超时: {e}")
        return []
    except ConnectionError as e:
        logger.error(f"Xbox发现网络错误: {e}")
        return []
    except Exception as e:
        logger.error(f"Xbox发现异常: {e}")
        return []


async def _test_xbox_connection(ip_address: str, logger) -> bool:
    """
    测试Xbox连接

    参数：
    - ip_address: Xbox IP地址
    - logger: 日志记录器

    返回：
    - bool: 是否在线
    """
    try:
        import socket

        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex((ip_address, 5050))
        sock.close()

        online = result == 0
        logger.info(f"Xbox {ip_address} 连接测试: {'在线' if online else '离线'}")
        return online

    except asyncio.TimeoutError as e:
        logger.error(f"Xbox连接测试超时: {ip_address} - {e}")
        return False
    except ConnectionError as e:
        logger.error(f"Xbox连接测试网络错误: {ip_address} - {e}")
        return False
    except Exception as e:
        logger.error(f"Xbox连接测试异常: {ip_address} - {e}")
        return False


async def _connect_to_xbox(context: AgentTaskContext, logger, stream_logger) -> tuple:
    """
    通过云端 PlaySession + SDP 连接到 Xbox（对齐 streaming/xsplayer.py）

    返回：
    - tuple: (success: bool, details: dict)
    """
    connect_details: Dict[str, Any] = {
        "playSessionEnabled": False,
        "sdpEnabled": False,
        "gpuAvailable": False,
        "gpuType": "unknown",
        "errorCode": "",
        "errorMessage": "",
    }

    try:
        context.xbox_session = None
        xbox_info = context.current_xbox

        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.0: 云端串流连接（PlaySession + SDP）                   │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        logger.info(
            f"目标 Xbox: {xbox_info.name} (serverId={xbox_info.id}, "
            f"playPath={xbox_info.play_path or DEFAULT_PLAY_PATH})"
        )
        stream_logger.info(f"开始云端串流: {xbox_info.name} (serverId={xbox_info.id})")

        session = await _create_play_session(context, logger, stream_logger)
        connect_details["playSessionEnabled"] = session is not None
        context._play_session_enabled = session is not None

        if not session:
            connect_details["errorCode"] = "PLAY_SESSION_FAILED"
            connect_details["errorMessage"] = f"PlaySession 创建失败: {xbox_info.name}"
            logger.error(connect_details["errorMessage"])
            stream_logger.error(connect_details["errorMessage"])
            return False, connect_details

        logger.info(f"PlaySession 创建成功: {session.session_id}")
        stream_logger.info(f"PlaySession 创建成功: {session.session_id}")

        sdp_success = await _exchange_sdp(context, session, logger, stream_logger)
        connect_details["sdpEnabled"] = sdp_success
        context._sdp_enabled = sdp_success

        if not sdp_success:
            connect_details["errorCode"] = "SDP_EXCHANGE_FAILED"
            connect_details["errorMessage"] = f"SDP 握手失败: {xbox_info.name}"
            logger.error(connect_details["errorMessage"])
            stream_logger.error(connect_details["errorMessage"])
            return False, connect_details

        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.3: 初始化 GPU 解码器（供后续步骤使用）                 │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        gpu_success = await _init_gpu_decoder(context, logger, stream_logger)
        connect_details["gpuAvailable"] = gpu_success
        connect_details["gpuType"] = getattr(context, '_gpu_type', 'cpu')

        media_ok = await _establish_cloud_media_session(context, logger, stream_logger)
        connect_details["mediaChannelEnabled"] = media_ok
        context._media_channel_enabled = media_ok

        if media_ok:
            video_ok = await _start_cloud_video_receiver(context, logger, stream_logger)
            connect_details["videoReceiverEnabled"] = video_ok
        else:
            connect_details["videoReceiverEnabled"] = False
            logger.warning("云端媒体通道未建立，步骤三将尝试降级捕获模式")

        logger.info(f"✓ Xbox 云端串流连接成功: {xbox_info.name}")
        stream_logger.info(f"Xbox 云端串流连接成功: {xbox_info.name}")
        return True, connect_details

    except asyncio.TimeoutError as e:
        connect_details["errorCode"] = "TIMEOUT"
        connect_details["errorMessage"] = f"连接 Xbox 超时: {e}"
        logger.error(connect_details["errorMessage"])
        stream_logger.error(connect_details["errorMessage"])
        return False, connect_details
    except ConnectionError as e:
        connect_details["errorCode"] = "CONNECTION_ERROR"
        connect_details["errorMessage"] = f"连接 Xbox 网络错误: {e}"
        logger.error(connect_details["errorMessage"])
        stream_logger.error(connect_details["errorMessage"])
        return False, connect_details
    except ValueError as e:
        connect_details["errorCode"] = "VALUE_ERROR"
        connect_details["errorMessage"] = f"连接 Xbox 参数错误: {e}"
        logger.error(connect_details["errorMessage"])
        stream_logger.error(connect_details["errorMessage"])
        return False, connect_details
    except Exception as e:
        connect_details["errorCode"] = "EXCEPTION"
        connect_details["errorMessage"] = f"连接 Xbox 异常: {e}"
        logger.error(connect_details["errorMessage"])
        stream_logger.error(connect_details["errorMessage"])
        return False, connect_details


async def _create_play_session(context: AgentTaskContext, logger, stream_logger):
    """
    创建 PlaySession（参考 streaming/xsplayer.py）

    使用匹配阶段已选中的 serverId 与 playPath，不再二次发现。

    返回：
    - PlaySession 对象或 None
    """
    try:
        from ..xbox.play_session import XboxPlaySessionManager, PlaySessionConfig

        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.1: 创建 PlaySession                                    │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        stream_logger.info("开始创建 PlaySession...")

        gssv_base = _get_gssv_base_uri(context)
        play_session_mgr = XboxPlaySessionManager(base_url=gssv_base)
        context._play_session_manager = play_session_mgr

        ms_token = _get_gs_token(context)
        if not ms_token:
            logger.warning("无可用的 gsToken，无法创建 PlaySession")
            return None

        logger.info(f"使用 gs_token 创建 PlaySession，长度: {len(ms_token)}")
        play_session_mgr.set_access_token(ms_token)

        xbox_info = context.current_xbox
        if not xbox_info or not xbox_info.id:
            logger.warning("当前上下文无有效的 Xbox serverId")
            return None

        server_id = xbox_info.id
        play_path = xbox_info.play_path or DEFAULT_PLAY_PATH

        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.2: 连接 Xbox 云端服务器                                │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        logger.info(
            f"目标服务器: serverId={server_id}, playPath={play_path}, "
            f"consoleType={xbox_info.console_type or 'Unknown'}, "
            f"powerState={xbox_info.power_state or 'Unknown'}"
        )
        stream_logger.info(
            f"Xbox 服务器: {xbox_info.console_type or 'Xbox'} "
            f"({xbox_info.power_state or 'Unknown'})"
        )

        session = await play_session_mgr.create_session(
            server_id=server_id,
            play_path=play_path,
            config=PlaySessionConfig(
                nano_version="V3;WebrtcTransport.dll",
                os_name="windows",
                sdk_type="web",
                use_ice_connection=False,
                locale="en-US",
            ),
        )

        if not session:
            logger.warning("PlaySession 创建失败")
            return None

        context._play_session_session_id = session.session_id
        context._play_session_session_path = session.session_path
        return session

    except asyncio.TimeoutError as e:
        logger.error(f"PlaySession 创建超时: {e}")
        stream_logger.error(f"PlaySession 创建超时: {e}")
        return None
    except ConnectionError as e:
        logger.error(f"PlaySession 创建网络错误: {e}")
        stream_logger.error(f"PlaySession 创建网络错误: {e}")
        return None
    except ValueError as e:
        logger.error(f"PlaySession 创建参数错误: {e}")
        stream_logger.error(f"PlaySession 创建参数错误: {e}")
        return None
    except Exception as e:
        logger.error(f"PlaySession 创建异常: {e}")
        stream_logger.error(f"PlaySession 创建异常: {e}")
        return None


async def _exchange_sdp(context: AgentTaskContext, session, logger, stream_logger) -> bool:
    """
    SDP握手建立WebRTC连接（参考streaming项目）

    功能说明：
    - 创建WebRTC Offer
    - 与Xbox交换SDP
    - 建立完整的WebRTC连接

    优化点：
    1. 直接使用 session 对象（已包含 session_path）
    2. 支持异步 202 响应自动轮询
    3. SDP 响应自动从 exchangeResponse.sdp 提取

    参数：
    - context: 任务上下文
    - session: PlaySession对象
    - logger: 日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        from ..xbox.webrtc_handler import XboxWebRTCHandler, WebRTCConfig

        logger.info("开始SDP握手...")
        stream_logger.info("开始SDP握手...")

        webrtc = XboxWebRTCHandler(WebRTCConfig(
            audio_enabled=True,
            video_enabled=True,
            video_width=1280,
            video_height=720,
            video_framerate=30
        ))
        context._webrtc_handler = webrtc

        sdp_offer = await webrtc.create_offer_async()
        if not sdp_offer:
            logger.warning("WebRTC Offer创建失败")
            return False

        logger.debug(f"WebRTC Offer SDP创建成功，长度: {len(sdp_offer)}")

        play_session_mgr = context._play_session_manager
        if not play_session_mgr or not play_session_mgr._access_token:
            logger.warning("无有效的 PlaySession 管理器，跳过 SDP 交换")
            return False

        if play_session_mgr._current_session:
            play_session_mgr._current_session.sdp_offer = sdp_offer

        sdp_answer = await play_session_mgr.exchange_sdp(sdp_offer=sdp_offer)

        if not sdp_answer:
            logger.warning("SDP Answer获取失败")
            return False

        answer_ok = await webrtc.handle_answer_async(sdp_answer)
        if not answer_ok:
            logger.warning("WebRTC Answer处理失败")
            return False

        logger.info("SDP握手完成")
        stream_logger.info("SDP握手完成")

        return True

    except asyncio.TimeoutError as e:
        logger.error(f"SDP握手超时: {e}")
        stream_logger.error(f"SDP握手超时: {e}")
        return False
    except ConnectionError as e:
        logger.error(f"SDP握手网络错误: {e}")
        stream_logger.error(f"SDP握手网络错误: {e}")
        return False
    except ValueError as e:
        logger.error(f"SDP握手参数错误: {e}")
        stream_logger.error(f"SDP握手参数错误: {e}")
        return False
    except Exception as e:
        logger.error(f"SDP握手异常: {e}")
        stream_logger.error(f"SDP握手异常: {e}")
        return False


async def _establish_cloud_media_session(context: AgentTaskContext, logger, stream_logger) -> bool:
    """
    在 SDP 交换后建立 WebRTC 媒体会话（视频 track + input DataChannel）。
    """
    try:
        webrtc = getattr(context, '_webrtc_handler', None)
        if not webrtc:
            logger.warning("WebRTC handler 不可用，跳过媒体通道建立")
            return False

        offer_sdp = webrtc.local_sdp
        answer_sdp = webrtc.remote_sdp
        if not offer_sdp or not answer_sdp:
            logger.warning("SDP 不完整，无法建立媒体通道")
            return False

        from ..xbox.cloud_stream_session import CloudStreamSession, AIORTC_AVAILABLE

        if not AIORTC_AVAILABLE:
            logger.warning("aiortc 未安装，无法建立云端媒体通道")
            return False

        cloud_session = await webrtc.create_cloud_session(
            offer_sdp=offer_sdp,
            answer_sdp=answer_sdp,
            gamepad_index=0,
        )
        if not cloud_session:
            logger.warning("CloudStreamSession 创建失败")
            return False

        context.xbox_session = cloud_session
        context._cloud_stream_session = cloud_session

        def _on_input_channel_closed():
            logger.warning("input DataChannel 已关闭，后续操作将尝试自动重连")
            context._input_channel_needs_reconnect = True

        if hasattr(cloud_session, "on_input_channel_close"):
            cloud_session.on_input_channel_close(_on_input_channel_closed)

        for attempt in range(5):
            if getattr(cloud_session, "is_connected", False):
                break
            await asyncio.sleep(0.2)

        if hasattr(cloud_session, "wait_for_input_channel"):
            await cloud_session.wait_for_input_channel(timeout=10.0)

        if hasattr(cloud_session, "send_keepalive"):
            for _ in range(3):
                await cloud_session.send_keepalive()
                await asyncio.sleep(0.2)

        cloud_session.attach_existing_tracks()
        logger.info("云端 WebRTC 媒体会话已建立（video + input DataChannel）")
        if stream_logger:
            stream_logger.info("云端 WebRTC 媒体会话已建立")
        return True

    except Exception as exc:
        logger.warning(f"建立云端媒体会话失败: {exc}")
        if stream_logger:
            stream_logger.warning(f"建立云端媒体会话失败: {exc}")
        return False


async def reconnect_cloud_stream_session(
    context: AgentTaskContext,
    logger,
    stream_logger,
) -> bool:
    """
    在保留 PlaySession 的前提下重建 WebRTC 媒体会话（修复 input DataChannel closed）。

    用于步骤四微软登录后输入通道断开等场景，无需重新匹配 Xbox 主机。
    """
    play_session_mgr = getattr(context, "_play_session_manager", None)
    if not play_session_mgr or not play_session_mgr._current_session:
        logger.error("无有效 PlaySession，无法重连 WebRTC 输入通道")
        return False

    old_session = getattr(context, "_cloud_stream_session", None) or context.xbox_session
    if old_session and hasattr(old_session, "disconnect"):
        try:
            await old_session.disconnect()
        except Exception as exc:
            logger.warning(f"断开旧 CloudStreamSession 时异常: {exc}")

    try:
        from ..xbox.webrtc_handler import XboxWebRTCHandler, WebRTCConfig

        logger.info("重连：创建新 WebRTC Offer...")
        webrtc = XboxWebRTCHandler(WebRTCConfig(
            audio_enabled=True,
            video_enabled=True,
            video_width=1280,
            video_height=720,
            video_framerate=30,
        ))
        context._webrtc_handler = webrtc

        sdp_offer = await webrtc.create_offer_async()
        if not sdp_offer:
            logger.error("重连：WebRTC Offer 创建失败")
            return False

        sdp_answer = await play_session_mgr.exchange_sdp(sdp_offer=sdp_offer)
        if (
            not sdp_answer
            and getattr(play_session_mgr, "_last_sdp_error_code", None) == "AgentNotListening"
        ):
            logger.warning(
                "重连：当前 PlaySession 不再监听 SDP，重建 PlaySession 后重试"
            )
            current_session = play_session_mgr._current_session
            xbox_info = context.current_xbox
            server_id = (
                getattr(current_session, "server_id", None)
                or (xbox_info.id if xbox_info else None)
            )
            play_path = (
                getattr(current_session, "play_path", None)
                or (xbox_info.play_path if xbox_info else None)
                or DEFAULT_PLAY_PATH
            )
            if not server_id:
                logger.error("重连：缺少 Xbox serverId，无法重建 PlaySession")
                return False

            from ..xbox.play_session import PlaySessionConfig

            new_session = await play_session_mgr.create_session(
                server_id=server_id,
                play_path=play_path,
                config=PlaySessionConfig(
                    nano_version="V3;WebrtcTransport.dll",
                    os_name="windows",
                    sdk_type="web",
                    use_ice_connection=False,
                ),
            )
            if not new_session:
                logger.error("重连：重建 PlaySession 失败")
                return False

            sdp_answer = await play_session_mgr.exchange_sdp(sdp_offer=sdp_offer)
        if not sdp_answer:
            logger.error("重连：SDP Answer 获取失败")
            return False

        if not await webrtc.handle_answer_async(sdp_answer):
            logger.error("重连：WebRTC Answer 处理失败")
            return False

        media_ok = await _establish_cloud_media_session(context, logger, stream_logger)
        if not media_ok:
            logger.error("重连：云端媒体会话建立失败")
            return False

        video_ok = await _start_cloud_video_receiver(context, logger, stream_logger)
        if not video_ok:
            logger.warning("重连：视频接收未就绪，但 input 通道可能已恢复")

        if stream_logger:
            stream_logger.info("WebRTC 输入通道重连完成")
        logger.info("WebRTC 输入通道重连完成")
        return True

    except Exception as exc:
        logger.error(f"重连 WebRTC 输入通道异常: {exc}")
        if stream_logger:
            stream_logger.error(f"重连 WebRTC 输入通道异常: {exc}")
        return False


async def _start_cloud_video_receiver(context: AgentTaskContext, logger, stream_logger) -> bool:
    """
    启动云端 WebRTC 视频接收并配置步骤三捕获模式。
    """
    try:
        cloud_session = getattr(context, '_cloud_stream_session', None) or context.xbox_session
        if not cloud_session:
            return False

        await cloud_session.start_video_receiver(mode="webrtc")
        cloud_session.attach_existing_tracks()

        first_frame = None
        if hasattr(cloud_session, "get_frame"):
            first_frame = await cloud_session.get_frame(timeout=8.0)

        from ..vision.webrtc_frame_controller import WebRTCFrameController

        webrtc_controller = WebRTCFrameController(cloud_session)
        context._webrtc_frame_controller = webrtc_controller
        context._video_capture_mode = "webrtc"
        context._video_mode = "webrtc"
        context._rtp_available = False

        if first_frame is not None:
            logger.info(f"WebRTC 首帧已就绪: {first_frame.shape[1]}x{first_frame.shape[0]}")
            if stream_logger:
                stream_logger.info("WebRTC 首帧已就绪")
        else:
            logger.warning("WebRTC 首帧未在超时内到达，步骤四将依赖后续重试")
            if stream_logger:
                stream_logger.warning("WebRTC 首帧未在超时内到达")

        logger.info("WebRTC 视频帧控制器已就绪")
        if stream_logger:
            stream_logger.info("WebRTC 视频帧接收已启用")
        return True

    except Exception as exc:
        logger.warning(f"启动云端视频接收失败: {exc}")
        if stream_logger:
            stream_logger.warning(f"启动云端视频接收失败: {exc}")
        context._video_capture_mode = "fallback"
        return False


async def _init_gpu_decoder(context: AgentTaskContext, logger, stream_logger) -> bool:
    """
    初始化GPU解码器（优化一）

    功能说明：
    - 检测系统GPU类型
    - 初始化GPU解码器
    - 将GPU信息存储到context供步骤三使用

    参数：
    - context: 任务上下文
    - logger: 日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        from ..vision.gpu_decoder import gpu_detector, GPUType

        gpu_type = gpu_detector.detect()
        gpu_info = gpu_detector.get_capabilities()

        logger.info(f"GPU检测结果: {gpu_type.value}")
        stream_logger.info(f"GPU类型: {gpu_type.value}")

        if gpu_type != GPUType.CPU:
            decoder_name = gpu_detector.get_decoder_name()
            logger.info(f"可用GPU解码器: {decoder_name}")
            stream_logger.info(f"将使用GPU硬件解码: {decoder_name}")
            context._gpu_available = True
            context._gpu_type = gpu_type.value
            context._gpu_decoder = decoder_name
        else:
            logger.info("无可用GPU，将使用CPU解码")
            stream_logger.info("将使用CPU软解码")
            context._gpu_available = False
            context._gpu_type = "cpu"
            context._gpu_decoder = "libx264"

        return True

    except Exception as e:
        logger.warning(f"GPU初始化失败，将使用窗口截图模式: {e}")
        stream_logger.warning(f"GPU初始化失败: {e}")
        context._gpu_available = False
        context._gpu_type = "cpu"
        context._gpu_decoder = "libx264"
        return True


async def _init_video_stream_controller(context: AgentTaskContext, logger, stream_logger) -> bool:
    """
    初始化视频流控制器（方案C优化）

    功能说明：
    - 创建高性能视频流控制器
    - 支持RTP视频流接收
    - 支持win32gui直接捕获
    - 提供多线程解码加速

    参数：
    - context: 任务上下文
    - logger: 日志记录器
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

        logger.info("初始化视频流控制器...")
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
                    logger.info("视频流控制器（RTP模式）初始化成功")
                    stream_logger.info("RTP视频流接收已启用")
                    return True
                else:
                    logger.warning("视频流控制器初始化失败，尝试win32gui模式")

        direct_capture = DirectCaptureController()
        context._direct_capture = direct_capture
        context._video_capture_mode = "direct"
        logger.info("直接捕获控制器已初始化")
        stream_logger.info("win32gui直接捕获模式已启用")

        return True

    except Exception as e:
        logger.warning(f"视频流控制器初始化失败: {e}")
        stream_logger.warning(f"视频流控制器初始化失败: {e}")
        context._video_capture_mode = "fallback"
        return True


async def _start_video_receiver(context: AgentTaskContext, logger, stream_logger) -> bool:
    """
    启动视频流接收器（方案3：混合模式）

    功能说明：
    - 支持两种视频流接收模式：RTP 和 win32gui
    - RTP模式：直接接收Xbox视频流，性能更好
    - win32gui模式：从Xbox Streaming窗口截图，兼容性更好
    - 优先尝试RTP，失败时自动降级到win32gui

    参数：
    - context: 任务上下文
    - logger: 日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        if not context.xbox_session:
            logger.warning("Xbox会话未初始化，跳过视频流接收器启动")
            return False

        logger.info("开始初始化视频流接收器...")
        stream_logger.info("开始初始化视频流接收器...")

        srtp_keys = None
        webrtc_handler = getattr(context, '_webrtc_handler', None)
        if webrtc_handler:
            srtp_keys = getattr(webrtc_handler, '_srtp_keys', None)

        video_success = await context.xbox_session.start_video_receiver(
            mode="auto",
            port=50500,
            srtp_keys=srtp_keys
        )

        video_mode = context.xbox_session.video_mode
        logger.info(f"视频流接收器初始化完成，模式: {video_mode}")
        stream_logger.info(f"视频流接收器初始化完成，模式: {video_mode}")

        context._video_mode = video_mode
        context._rtp_available = video_mode == "rtp"

        if video_mode == "rtp":
            logger.info("使用RTP视频流接收，性能更优")
            stream_logger.info("RTP视频流接收已启用")
        else:
            logger.info("使用win32gui截图模式，兼容性更强")
            stream_logger.info("win32gui截图模式已启用")

        await _init_video_stream_controller(context, logger, stream_logger)

        return True

    except Exception as e:
        logger.warning(f"视频流接收器初始化失败: {e}")
        stream_logger.warning(f"视频流接收器初始化失败: {e}")
        context._video_mode = "win32gui"
        context._rtp_available = False
        context._video_capture_mode = "fallback"
        return True


async def _check_xbox_availability(context: AgentTaskContext, xbox_host_id: str) -> bool:
    """
    检查Xbox主机是否可用（未被其他任务或Agent占用）

    检查逻辑（跨Agent场景）：
    1. 通过平台API获取主机状态和锁定信息
    2. 检查主机是否已被其他Agent锁定
    3. 检查主机是否已被本Agent的其他任务占用
    4. 尝试通过平台API锁定主机（原子操作）
    5. 更新本地调度器状态

    参数：
    - context: 任务上下文
    - xbox_host_id: Xbox主机ID（可以是数据库ID或Xbox序列号）

    返回：
    - bool: 是否可用
    """
    logger = get_logger(f'step2_streaming_{context.task_id}')

    # 步骤1: 通过平台API检查主机状态
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        status = await api_client.get_xbox_host_status(xbox_host_id)

        # 如果主机在数据库中不存在，说明还没注册，返回可用
        if status is None:
            logger.info(f"平台未找到Xbox主机 {xbox_host_id}，将直接使用发现的Xbox")
            return True

        # 检查是否已被锁定
        locked_by_agent = status.get('lockedByAgentId')
        lock_expires = status.get('lockExpiresTime')

        if locked_by_agent:
            # 获取当前Agent ID
            from ..core.credentials_provider import get_credentials
            current_agent_id, _ = get_credentials()

            # 如果被其他Agent锁定，拒绝使用
            if locked_by_agent != current_agent_id:
                logger.warning(f"平台检测到Xbox主机 {xbox_host_id} 已被Agent {locked_by_agent} 锁定")
                return False
            else:
                logger.debug(f"Xbox主机 {xbox_host_id} 已被本Agent锁定")
    except Exception as e:
        logger.warning(f"无法连接平台检查主机状态: {e}")
        # 如果无法连接平台，继续尝试本地检查，但记录警告

    # 步骤2: 通过平台API尝试锁定主机（跨Agent安全）
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        locked = await api_client.lock_xbox_host(xbox_host_id)

        if not locked:
            logger.warning(f"平台锁定Xbox主机 {xbox_host_id} 失败（主机可能不存在或已被其他Agent锁定）")
            # 返回 False，等待平台有 Xbox 主机记录后再使用
            return False
        logger.info(f"成功通过平台锁定Xbox主机: {xbox_host_id}")
    except Exception as e:
        logger.warning(f"尝试锁定主机失败: {e}")
        return False

    # 步骤3: 更新本地调度器状态
    try:
        from ..task.task_executor import task_executor

        if task_executor and hasattr(task_executor, 'scheduler'):
            scheduler = task_executor.scheduler
            await scheduler.acquire_xbox_host(xbox_host_id, context.task_id)
    except Exception as e:
        logger.debug(f"更新本地调度器状态失败: {e}")

    logger.info(f"Xbox主机 {xbox_host_id} 可用")
    return True


async def _is_xbox_occupied(xbox_host_id: str, context: AgentTaskContext, logger) -> bool:
    """
    只读占用检测：判断 Xbox 主机是否被其他串流账号/Agent 占用。

    与 ``_check_xbox_availability`` 的区别：
    - 本函数不执行 lock，仅查询；适用于 matcher 在选择阶段做过滤
    - 平台 API 不可达时返回 False（降级为不阻塞匹配，与 matcher 行为一致）

    Args:
        xbox_host_id: Xbox 主机 ID
        context: 任务上下文
        logger: 日志记录器

    Returns:
        bool: True 表示被其他 Agent/任务占用；False 表示空闲或无法判断
    """
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        status = await api_client.get_xbox_host_status(xbox_host_id)
    except Exception as e:
        logger.warning(f"占用检测：无法连接平台（{xbox_host_id}）: {e}")
        return False

    if status is None:
        # 平台无记录，按空闲处理
        return False

    locked_by_agent = status.get('lockedByAgentId')
    if not locked_by_agent:
        return False

    try:
        from ..core.credentials_provider import get_credentials
        current_agent_id, _ = get_credentials()
    except Exception:
        current_agent_id = None

    if current_agent_id and locked_by_agent == current_agent_id:
        # 已被本 Agent 其他任务锁定 → 视为占用
        return True

    if locked_by_agent != current_agent_id:
        # 被其他 Agent 锁定
        return True

    return False


async def _release_xbox_host(context: AgentTaskContext):
    """
    释放Xbox主机的串流权限（跨Agent场景）

    参数：
    - context: 任务上下文
    """
    logger = get_logger(f'step2_streaming_{context.task_id}')
    
    if context.current_xbox:
        xbox_host_id = context.current_xbox.id
        if xbox_host_id:
            # 步骤1: 通过平台API解锁主机
            try:
                from ..api.platform_api_client import PlatformApiClient
                
                api_client = PlatformApiClient()
                await api_client.unlock_xbox_host(xbox_host_id)
                logger.info(f"成功通过平台解锁Xbox主机: {xbox_host_id}")
            except Exception as e:
                logger.warning(f"通过平台解锁主机失败: {e}")
            
            # 步骤2: 更新本地调度器状态
            try:
                from ..task.task_executor import task_executor
                
                if task_executor and hasattr(task_executor, 'scheduler'):
                    scheduler = task_executor.scheduler
                    await scheduler.release_xbox_host(xbox_host_id, context.task_id)
            except Exception as e:
                logger.debug(f"更新本地调度器状态失败: {e}")


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


async def _smart_match_xbox_with_wakeup(
    context: AgentTaskContext,
    gs_token: str,
    logger,
    stream_logger,
    assigned_xbox: Optional[XboxInfo] = None,
    check_occupancy: Optional[Callable[[XboxInfo], "asyncio.Future[bool]"]] = None,
    wakeup_enabled: bool = True,
    wakeup_timeout: int = 30
) -> XboxMatchResult:
    """
    智能匹配 Xbox 主机（包含自动唤醒功能）

    v4.0 流程（streaming 云端单路径）：
    1. 获取云端授权的 Xbox 主机列表（必须至少有一个）
    2. 指定主机：云端授权 → 占用校验 → 唤醒
    3. 自动匹配：云端列表筛选电源状态 → 过滤占用 → 随机选择
    4. 选中的主机若处于待机状态，通过云端 API 自动唤醒

    Args:
        context: 任务上下文
        gs_token: Xbox Live gsToken
        logger: 日志记录器
        stream_logger: 流媒体账号日志
        assigned_xbox: 任务指定的 Xbox 主机（可选）
        check_occupancy: 占用检测异步回调（可选）
        wakeup_enabled: 是否启用自动唤醒
        wakeup_timeout: 唤醒超时时间（秒）

    Returns:
        XboxMatchResult: 包含匹配结果或详细错误信息的对象
    """
    try:
        matcher = XboxHostMatcher(gs_token, gssv_base_uri=_get_gssv_base_uri(context))

        logger.info("="*60)
        if assigned_xbox is not None:
            logger.info("Xbox 主机指定匹配（自动唤醒模式）")
        else:
            logger.info("Xbox 主机智能匹配（自动唤醒模式）")
        logger.info("="*60)
        logger.info(f"唤醒功能: {'启用' if wakeup_enabled else '禁用'}")
        if wakeup_enabled:
            logger.info(f"唤醒超时: {wakeup_timeout} 秒")
        logger.info("")

        match_result = await matcher.find_best_match(
            assigned_xbox=assigned_xbox,
            check_occupancy=check_occupancy,
            wakeup=wakeup_enabled,
            wakeup_timeout=wakeup_timeout
        )
        
        # 处理匹配结果
        if not match_result or not match_result.xbox_info:
            # 匹配失败，记录详细错误信息
            error_code = match_result.error_code if match_result else "UNKNOWN"
            error_reason = match_result.match_reason if match_result else "未知错误"
            
            logger.error("\n" + "="*60)
            logger.error("Xbox 主机匹配失败")
            logger.error("="*60)
            logger.error(f"错误码: {error_code}")
            logger.error(f"失败原因: {error_reason}")
            
            # 根据错误码生成详细的解决方案
            if match_result and match_result.error_details:
                logger.error("\n详细信息:")
                for key, value in match_result.error_details.items():
                    logger.error(f"  {key}: {value}")
                
                if "suggestion" in match_result.error_details:
                    logger.error(f"\n解决方案: {match_result.error_details['suggestion']}")
            
            logger.error("="*60)
            
            # 记录到流媒体账号日志
            stream_logger.error(f"Xbox 主机匹配失败: {error_reason}")
            if match_result and match_result.error_details:
                if "suggestion" in match_result.error_details:
                    stream_logger.error(f"解决方案: {match_result.error_details['suggestion']}")
            
            return match_result
        
        xbox = match_result.xbox_info
        
        logger.info("\n" + "="*60)
        logger.info("Xbox 主机匹配结果")
        logger.info("="*60)
        logger.info(f"设备名称: {xbox.name}")
        logger.info(f"设备 ID: {xbox.device_id[:16]}...")
        logger.info(f"PlayPath: {xbox.play_path or DEFAULT_PLAY_PATH}")
        logger.info(f"主机类型: {xbox.console_type}")
        logger.info(f"电源状态: {xbox.power_state}")
        logger.info(f"匹配优先级: {match_result.priority.name}")
        logger.info(f"匹配原因: {match_result.match_reason}")
        logger.info("="*60)
        
        stream_logger.info(f"Xbox 主机匹配成功: {xbox.name}")
        return match_result
        
    except Exception as e:
        logger.error(f"智能匹配 Xbox 失败: {e}", exc_info=True)
        stream_logger.error(f"智能匹配 Xbox 失败: {e}")
        
        # 返回包含错误信息的 XboxMatchResult
        return XboxMatchResult(
            xbox_info=None,
            match_reason=f"智能匹配异常: {str(e)}",
            error_code="SMART_MATCH_EXCEPTION",
            error_details={"exception": str(e)}
        )


async def _wakeup_assigned_xbox(
    gs_token: str,
    xbox: XboxInfo,
    logger
):
    """
    唤醒指定的 Xbox 主机
    
    Args:
        gs_token: Xbox Live gsToken
        xbox: Xbox 主机信息
        logger: 日志记录器
        
    Returns:
        XboxWakeupResult
    """
    try:
        matcher = XboxHostMatcher(gs_token)
        wakeup_result = await matcher._wakeup_xbox(xbox, timeout=30)  # noqa: SLF001
        return wakeup_result
    except Exception as e:
        logger.error(f"唤醒 Xbox 失败: {e}", exc_info=True)
        from ..xbox.xbox_host_matcher import XboxWakeupResult
        return XboxWakeupResult(
            success=False,
            xbox_info=xbox,
            wakeup_method="none",
            attempts=0,
            wait_time_seconds=0,
            error_message=str(e)
        )


def _print_no_match_help(logger, error_code: str = "", error_details: Dict[str, Any] = None):
    """打印无可用 Xbox 的帮助信息
    
    Args:
        logger: 日志记录器
        error_code: 错误码
        error_details: 错误详情字典
    """
    if error_details is None:
        error_details = {}
    
    logger.warning("\n" + "="*60)
    logger.warning("Xbox 主机匹配失败 - 可能的原因和解决方案")
    logger.warning("="*60)
    
    if error_code == "CLOUD_NO_AUTHORIZED":
        logger.warning("\n原因: 云端未发现已授权的 Xbox 主机")
        logger.warning("\n解决方案:")
        logger.warning("1. 请在 Xbox 应用中添加并授权此流媒体账号")
        logger.warning("   - 打开 Xbox 应用")
        logger.warning("   - 进入 '连接' 页面")
        logger.warning("   - 添加并授权您的 Xbox 主机")
        logger.warning("")
        logger.warning("2. 确保 Xbox 主机已绑定到您的 Microsoft 账号")
        logger.warning("")
        logger.warning("3. 检查账号是否有权限访问该 Xbox 主机")
        logger.warning("")
        logger.warning("4. 确认流媒体账号已正确登录")
    elif error_code == "NO_AVAILABLE_HOST":
        cloud_count = error_details.get("cloud_authorized_count", 0)
        powered_count = error_details.get("powered_on_count", 0)
        standby_count = error_details.get("standby_count", 0)

        logger.warning(
            f"\n原因: 云端授权 {cloud_count} 台，但无可用主机 "
            f"(开机 {powered_count} 台, 可唤醒 {standby_count} 台)"
        )
        logger.warning("\n解决方案:")
        logger.warning("1. 请确保 Xbox 主机已开机或处于可远程唤醒状态")
        logger.warning("")
        logger.warning("2. 检查 Xbox 电源模式设置（建议使用 Instant-On）")
        logger.warning("")
        logger.warning("3. 确认流媒体账号已在 Xbox 应用中授权该主机")
    elif error_code == "WAKEUP_FAILED":
        xbox_name = error_details.get("xbox_name", "未知")
        logger.warning(f"\n原因: Xbox {xbox_name} 唤醒失败")
        logger.warning("\n解决方案:")
        logger.warning("1. 手动开机 Xbox 主机")
        logger.warning("")
        logger.warning("2. 检查 Xbox 网络设置，确保 Xbox 可被远程唤醒")
        logger.warning("")
        logger.warning("3. 检查 Xbox 电源模式，确保不是 '节能' 模式")
    elif error_code == "WAKEUP_DISABLED":
        xbox_name = error_details.get("xbox_name", "未知")
        logger.warning(f"\n原因: Xbox {xbox_name} 处于待机模式，唤醒功能已禁用")
        logger.warning("\n解决方案:")
        logger.warning("1. 手动开机 Xbox 主机")
        logger.warning("")
        logger.warning("2. 或重新启动任务并启用唤醒功能")
    else:
        logger.warning("\n原因: 没有找到可用的授权 Xbox 主机")
        logger.warning("\n可能的原因:")
        logger.warning("1. 流媒体账号未绑定任何 Xbox 主机")
        logger.warning("   → 请在 Xbox 应用中添加并授权此账号")
        logger.warning("")
        logger.warning("2. Xbox 主机未连接到网络")
        logger.warning("   → 检查 Xbox 网络设置")
        logger.warning("")
        logger.warning("3. Xbox 主机处于 Energy-Saving 模式")
        logger.warning("   → 请改为 Instant-On 模式（设置 > 电源 > 启动模式）")
        logger.warning("")
        logger.warning("4. gsToken 已过期，需要重新认证")
        logger.warning("   → 重新运行步骤一进行账号登录")
    
    logger.warning("="*60)

