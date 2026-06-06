"""
步骤二：Xbox串流连接
====================

功能说明：
- 根据条件匹配Xbox主机
- 校验Xbox主机是否已被其他任务串流
- 建立与Xbox的串流连接
- 创建PlaySession（参考streaming项目）
- 可选：SDP握手建立WebRTC连接
- 可选：启动RTP视频流接收（方案3）
- 回传主机信息到平台并标记防止抢夺

方法拆分：
- step2_execute_streaming(): 执行串流主流程
- _match_xbox_host(): 匹配Xbox主机
- _connect_to_xbox(): 连接到Xbox主机
- _create_play_session(): 创建PlaySession（新增）
- _exchange_sdp(): SDP握手（新增，可选）
- _start_video_receiver(): 启动视频流接收（方案3新增）
- _bind_xbox_to_platform(): 绑定Xbox到平台（防止抢夺）
- _report_progress(): 上报进度到平台
- _check_xbox_availability(): 检查Xbox主机是否可用（未被其他任务占用）

作者：技术团队
版本：5.0

版本历史：
- 3.0: 集成PlaySession管理和SDP握手功能
- 4.0: 集成混合模式视频流接收（方案3）
- 5.0: 优化 Xbox 发现逻辑（云端授权必须存在 + 局域网在线必须存在 + 随机选择）
"""

import asyncio
import json
import random
import time
from typing import Callable, Optional, Dict, Any, List

from ..core.logger import get_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext, Step2Result, XboxInfo, TaskStepStatus
from ..xbox.xbox_host_matcher import XboxHostMatcher, XboxMatchResult

# 注意: XboxMatchResult 现在从 xbox_host_matcher 导入，包含详细的错误信息

_DEBUG_LOG_PATH = r"d:\auto-xbox\team-management\debug-e7595f.log"


def _debug_log(hypothesis_id: str, location: str, message: str, data: Dict[str, Any]) -> None:
    # #region agent log
    try:
        with open(_DEBUG_LOG_PATH, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "sessionId": "e7595f",
                "hypothesisId": hypothesis_id,
                "location": location,
                "message": message,
                "data": data,
                "timestamp": int(time.time() * 1000),
            }, ensure_ascii=False) + "\n")
    except Exception:
        pass
    # #endregion


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

        match_result = await _match_xbox_host(context, logger, stream_logger, check_cancel)

        if not match_result.success:
            fail_msg = _format_xbox_match_message(match_result)
            # #region agent log
            _debug_log("C", "step2_xbox_streaming.py:step2_execute_streaming",
                       "match failed reporting", {
                           "error_code": match_result.error_code,
                           "match_reason": match_result.match_reason,
                           "fail_msg": fail_msg,
                       })
            # #endregion
            logger.error(f"Xbox主机匹配失败: {fail_msg}")
            stream_logger.error(f"Xbox主机匹配失败: {fail_msg}")
            context.update_step_status("step2", TaskStepStatus.FAILED, fail_msg)
            await report_progress(context.task_id, "STEP2", "FAILED", fail_msg)
            return Step2Result(
                success=False,
                error_code=match_result.error_code or "XBOX_MATCH_FAILED",
                message=fail_msg,
            )

        # 校验Xbox主机是否已被其他任务占用
        xbox_id = match_result.xbox_info.id or match_result.xbox_info.live_id or match_result.xbox_info.mac_address
        if xbox_id:
            available = await _check_xbox_availability(context, xbox_id)
            if not available:
                error_msg = f"Xbox主机 {match_result.xbox_info.name} 已被其他任务占用"
                logger.error(error_msg)
                stream_logger.error(error_msg)
                context.update_step_status("step2", TaskStepStatus.FAILED, error_msg)
                await report_progress(context.task_id, "STEP2", "FAILED", error_msg)
                return Step2Result(success=False, error_code="XBOX_OCCUPIED",
                                 message=error_msg)

        context.current_xbox = match_result.xbox_info
        logger.info(f"Xbox匹配成功: {match_result.xbox_info.name} "
                   f"({match_result.xbox_info.ip_address}), "
                   f"匹配原因: {match_result.match_reason}")
        stream_logger.info(f"Xbox匹配成功: {match_result.xbox_info.name} "
                          f"({match_result.xbox_info.ip_address})")

        if check_cancel():
            return Step2Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step2", TaskStepStatus.RUNNING,
                                  f"正在连接{context.current_xbox.name}...")
        stream_logger.info(f"正在连接Xbox: {context.current_xbox.name}")

        connect_success, connect_details = await _connect_to_xbox(context, logger, stream_logger)

        if not connect_success:
            error_msg = f"连接Xbox失败: {context.current_xbox.ip_address}"
            logger.error(error_msg)
            stream_logger.error(error_msg)
            context.update_step_status("step2", TaskStepStatus.FAILED, error_msg)
            await report_progress(
                context.task_id, "STEP2", "FAILED", error_msg,
                {
                    "xboxIp": context.current_xbox.ip_address,
                    "xboxName": context.current_xbox.name,
                    "errorCode": "XBOX_CONNECT_FAILED"
                }
            )
            return Step2Result(success=False, error_code="XBOX_CONNECT_FAILED",
                             message=error_msg)

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
    
    优化逻辑：
    1. 如果指定了Xbox主机，验证授权并检测是否需要唤醒
    2. 如果未指定，使用智能匹配：
       a) 先获取云端授权的 Xbox 列表
       b) 再发现本地在线的 Xbox
       c) 智能匹配并返回最优选择
       d) 如果是待机状态，自动唤醒
    
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
        error_msg = "无可用的 gsToken，无法进行 Xbox 匹配"
        logger.error(error_msg)
        return XboxMatchResult(
            success=False,
            xbox_info=None,
            match_reason=error_msg,
            error_code="NO_TOKEN",
        )
    
    if context.assigned_xbox:
        logger.info(f"使用指定的Xbox主机: {context.assigned_xbox.name} "
                   f"({context.assigned_xbox.ip_address})")
        stream_logger.info(f"使用指定的Xbox主机: {context.assigned_xbox.name}")
        
        online = await _test_xbox_connection(context.assigned_xbox.ip_address, logger)
        if online:
            logger.info("指定的 Xbox 主机在线")
            return XboxMatchResult(
                success=True,
                xbox_info=context.assigned_xbox,
                match_reason="使用指定的Xbox主机",
            )
        else:
            logger.warning(f"指定的Xbox主机不在线: {context.assigned_xbox.ip_address}")
            
            if context.assigned_xbox.power_state == "Standby":
                logger.info("Xbox 处于待机模式，尝试唤醒...")
                wakeup_result = await _wakeup_assigned_xbox(
                    gs_token, 
                    context.assigned_xbox, 
                    logger
                )
                
                if wakeup_result.success:
                    logger.info(f"✓ Xbox 唤醒成功: {context.assigned_xbox.name}")
                    return XboxMatchResult(
                        success=True,
                        xbox_info=context.assigned_xbox,
                        match_reason=f"唤醒 Xbox 成功: {context.assigned_xbox.name}",
                    )
                else:
                    error_msg = f"唤醒 Xbox 失败: {wakeup_result.error_message}"
                    logger.error(error_msg)
                    return XboxMatchResult(
                        success=False,
                        xbox_info=None,
                        match_reason=error_msg,
                        error_code="ASSIGNED_WAKEUP_FAILED",
                    )
            
            return XboxMatchResult(
                success=False,
                xbox_info=None,
                match_reason=f"指定的Xbox主机不在线: {context.assigned_xbox.ip_address}",
                error_code="ASSIGNED_OFFLINE",
            )
    
    logger.info("未指定Xbox主机，开始智能匹配...")
    stream_logger.info("未指定Xbox主机，开始智能匹配...")
    
    match_result = await _smart_match_xbox_with_wakeup(
        context, 
        gs_token, 
        logger, 
        stream_logger,
        wakeup_enabled=True,
        wakeup_timeout=30
    )
    
    if match_result and match_result.success and match_result.xbox_info:
        xbox_info = match_result.xbox_info
        stream_logger.info(f"智能匹配成功: {xbox_info.name}")
        if not match_result.match_reason:
            match_result.match_reason = f"智能匹配 Xbox: {xbox_info.name}"
        return match_result
    else:
        # #region agent log
        _debug_log("A", "step2_xbox_streaming.py:_match_xbox_host",
                   "smart match failed branch", {
                       "has_match_result": match_result is not None,
                       "error_code": match_result.error_code if match_result else None,
                       "match_reason": match_result.match_reason if match_result else None,
                   })
        # #endregion
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
    连接到Xbox主机

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - tuple: (success: bool, details: dict)
    """
    connect_details = {
        "playSessionEnabled": False,
        "sdpEnabled": False,
        "gpuAvailable": False,
        "gpuType": "unknown",
        "videoMode": "unknown"
    }
    
    try:
        from ..xbox.stream_controller import XboxStreamController, StreamConfig
        from ..xbox.play_session import XboxPlaySessionManager, PlaySessionConfig
        from ..xbox.webrtc_handler import XboxWebRTCHandler, WebRTCConfig

        xbox_controller = XboxStreamController()
        context.xbox_session = xbox_controller

        xbox_info = context.current_xbox
        xbox_token = context.xbox_tokens.xsts_token
        user_hash = context.xbox_tokens.user_hash
        
        xbox_port = getattr(xbox_info, 'port', 5050)
        
        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.0: 连接 Xbox 主机                                    │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        logger.info(f"目标 Xbox: {xbox_info.name} ({xbox_info.ip_address}:{xbox_port})")
        logger.info(f"用户哈希: {user_hash[:20]}...")
        stream_logger.info(f"开始连接Xbox: {xbox_info.name} ({xbox_info.ip_address}:{xbox_port})")

        logger.info("执行 SmartGlass Token 握手...")
        success = await xbox_controller.connect_with_token(
            xbox_ip=xbox_info.ip_address,
            xbox_token=xbox_token,
            user_hash=user_hash,
            port=xbox_port
        )

        if not success:
            logger.error(f"Xbox SmartGlass 连接失败: {xbox_info.ip_address}")
            stream_logger.error(f"Xbox连接失败: {xbox_info.ip_address}")
            return False, connect_details

        logger.info(f"✓ Xbox SmartGlass 连接成功: {xbox_info.name}")
        stream_logger.info(f"Xbox基础连接成功: {xbox_info.name}")

        play_session_success = await _create_play_session(
            context, logger, stream_logger
        )
        connect_details["playSessionEnabled"] = play_session_success
        context._play_session_enabled = play_session_success

        if play_session_success:
            logger.info(f"PlaySession创建成功，已启用")
            stream_logger.info(f"PlaySession已启用")
        else:
            logger.warning(f"PlaySession创建失败，将使用基础连接: {xbox_info.name}")
            stream_logger.warning(f"PlaySession未启用")

        logger.info(f"✓ Xbox 连接成功: {xbox_info.name}")
        stream_logger.info(f"Xbox连接成功: {xbox_info.name}")

        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.4: 初始化 GPU 解码器                                  │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        gpu_success = await _init_gpu_decoder(context, logger, stream_logger)
        connect_details["gpuAvailable"] = gpu_success
        connect_details["gpuType"] = getattr(context, '_gpu_type', 'cpu')
        
        if gpu_success:
            logger.info(f"✓ GPU 解码器初始化成功: {getattr(context, '_gpu_type', 'unknown')}")
        else:
            logger.warning("✗ GPU 解码器初始化失败，将使用 CPU 解码")
        
        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.5: 启动视频接收器                                     │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        video_success = await _start_video_receiver(context, logger, stream_logger)
        connect_details["videoMode"] = getattr(context, '_video_mode', 'win32gui')
        
        if video_success:
            logger.info(f"✓ 视频接收器启动成功: {getattr(context, '_video_mode', 'unknown')}")
        else:
            logger.warning("✗ 视频接收器启动失败")

        return True, connect_details

    except asyncio.TimeoutError as e:
        logger.error(f"连接Xbox超时: {e}")
        stream_logger.error(f"连接Xbox超时: {e}")
        return False, connect_details
    except ConnectionError as e:
        logger.error(f"连接Xbox网络错误: {e}")
        stream_logger.error(f"连接Xbox网络错误: {e}")
        return False, connect_details
    except ValueError as e:
        logger.error(f"连接Xbox参数错误: {e}")
        stream_logger.error(f"连接Xbox参数错误: {e}")
        return False, connect_details
    except Exception as e:
        logger.error(f"连接Xbox异常: {e}")
        stream_logger.error(f"连接Xbox异常: {e}")
        return False, connect_details


async def _create_play_session(context: AgentTaskContext, logger, stream_logger) -> bool:
    """
    创建PlaySession（参考streaming项目）

    功能说明：
    - 使用 Xbox Live 云端 API 发现主机
    - 创建流播放会话并轮询 Provisioned 状态
    - 支持 WebRTC SDP 握手

    优化点：
    1. 优先使用 Xbox Live 云端 API 发现主机
    2. 使用 play_path 动态构建会话创建URL
    3. 轮询等待 Provisioned 状态
    4. SDP 响应从 exchangeResponse.sdp 提取

    参数：
    - context: 任务上下文
    - logger: 日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - bool: 是否成功
    """
    try:
        from ..xbox.play_session import XboxPlaySessionManager, PlaySessionConfig
        from ..xbox.webrtc_handler import XboxWebRTCHandler, WebRTCConfig

        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.1: 创建 PlaySession                                    │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        stream_logger.info("开始创建PlaySession...")

        play_session_mgr = XboxPlaySessionManager()
        context._play_session_manager = play_session_mgr

        ms_token = None
        if context.xbox_tokens and hasattr(context.xbox_tokens, 'gs_token') and context.xbox_tokens.gs_token:
            ms_token = context.xbox_tokens.gs_token
            logger.info(f"从 xbox_tokens 获取 gs_token 用于 PlaySession，长度: {len(ms_token)}")
        elif context.microsoft_tokens and hasattr(context.microsoft_tokens, 'access_token'):
            ms_token = context.microsoft_tokens.access_token
            logger.warning("使用旧的 access_token 用于 PlaySession")

        if not ms_token:
            logger.warning("无可用的访问令牌，跳过PlaySession创建")
            return False

        play_session_mgr.set_access_token(ms_token)

        logger.info("通过 Xbox Live API 发现服务器...")
        servers = await play_session_mgr.discover_servers()
        if not servers:
            logger.warning("未发现Xbox服务器，可能不在Xbox Live网络中")
            return False

        logger.info(f"发现 {len(servers)} 个Xbox服务器")
        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.2: 选择并连接 Xbox 服务器                              │")
        logger.info("└─────────────────────────────────────────────────────────────┘")

        server = servers[0]
        server_id = server.get('serverId', '')
        play_path = server.get('playPath', '')

        if not server_id:
            logger.warning("服务器响应中无serverId")
            return False

        if not play_path:
            logger.warning("服务器响应中无playPath")
            return False

        logger.info(f"选择Xbox服务器: serverId={server_id}, playPath={play_path}, "
                   f"consoleType={server.get('consoleType', 'Unknown')}, "
                   f"powerState={server.get('powerState', 'Unknown')}")
        stream_logger.info(f"Xbox服务器: {server.get('consoleType', 'Xbox')} "
                         f"({server.get('powerState', 'Unknown')})")

        logger.info("创建 PlaySession 连接...")
        session = await play_session_mgr.create_session(
            server_id=server_id,
            play_path=play_path,
            config=PlaySessionConfig(
                nano_version="V3;WebrtcTransport.dll",
                os_name="windows",
                sdk_type="web",
                use_ice_connection=False,
                locale="en-US"
            )
        )

        if not session:
            logger.warning("PlaySession创建失败")
            return False

        logger.info(f"PlaySession创建成功: sessionId={session.session_id}, "
                   f"sessionPath={session.session_path}")
        stream_logger.info(f"PlaySession创建成功: {session.session_id}")

        context._play_session_manager = play_session_mgr
        context._play_session_session_id = session.session_id
        context._play_session_session_path = session.session_path

        logger.info("┌─────────────────────────────────────────────────────────────┐")
        logger.info("│ 步骤2.3: 执行 SDP 握手                                       │")
        logger.info("└─────────────────────────────────────────────────────────────┘")
        sdp_success = await _exchange_sdp(
            context, session, logger, stream_logger
        )
        context._sdp_enabled = sdp_success

        if sdp_success:
            logger.info("SDP握手成功 ✓")
            stream_logger.info("SDP握手成功")
        else:
            logger.warning("SDP握手失败，连接可能不稳定")

        return True

    except asyncio.TimeoutError as e:
        logger.error(f"PlaySession创建超时: {e}")
        stream_logger.error(f"PlaySession创建超时: {e}")
        return False
    except ConnectionError as e:
        logger.error(f"PlaySession创建网络错误: {e}")
        stream_logger.error(f"PlaySession创建网络错误: {e}")
        return False
    except ValueError as e:
        logger.error(f"PlaySession创建参数错误: {e}")
        stream_logger.error(f"PlaySession创建参数错误: {e}")
        return False
    except Exception as e:
        logger.error(f"PlaySession创建异常: {e}")
        stream_logger.error(f"PlaySession创建异常: {e}")
        return False


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

        sdp_offer = webrtc.create_offer()
        if not sdp_offer:
            logger.warning("WebRTC Offer创建失败")
            return False

        logger.debug(f"WebRTC Offer SDP创建成功，长度: {len(sdp_offer)}")

        play_session_mgr = context._play_session_manager
        if not play_session_mgr or not play_session_mgr._access_token:
            logger.warning("无有效的PlaySession管理器，跳过SDP交换")
            return False

        sdp_answer = await play_session_mgr.exchange_sdp()

        if not sdp_answer:
            logger.warning("SDP Answer获取失败")
            return False

        webrtc.handle_answer(sdp_answer)
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
    """从上下文获取 gsToken"""
    if context.xbox_tokens and hasattr(context.xbox_tokens, 'gs_token'):
        return context.xbox_tokens.gs_token
    elif context.microsoft_tokens:
        return context.microsoft_tokens.access_token
    return None


async def _smart_match_xbox_with_wakeup(
    context: AgentTaskContext,
    gs_token: str,
    logger,
    stream_logger,
    wakeup_enabled: bool = True,
    wakeup_timeout: int = 30
) -> XboxMatchResult:
    """
    智能匹配 Xbox 主机（包含自动唤醒功能）
    
    优化后的匹配流程：
    1. 获取云端授权的 Xbox 主机列表（必须至少有一个）
    2. 发现局域网内的在线 Xbox 主机
    3. 过滤出同时在云端授权和局域网在线的 Xbox 主机（必须至少有一个）
    4. 如果有多个符合条件的主机，随机选择一个
    5. 如果选中的是待机状态，自动唤醒
    
    Args:
        context: 任务上下文
        gs_token: Xbox Live gsToken
        logger: 日志记录器
        stream_logger: 流媒体账号日志
        wakeup_enabled: 是否启用自动唤醒
        wakeup_timeout: 唤醒超时时间（秒）
        
    Returns:
        XboxMatchResult: 包含匹配结果或详细错误信息的对象
    """
    try:
        matcher = XboxHostMatcher(gs_token)
        
        logger.info("="*60)
        logger.info("Xbox 主机智能匹配（自动唤醒模式）")
        logger.info("="*60)
        logger.info(f"唤醒功能: {'启用' if wakeup_enabled else '禁用'}")
        if wakeup_enabled:
            logger.info(f"唤醒超时: {wakeup_timeout} 秒")
        logger.info("")
        
        match_result = await matcher.find_best_match(
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
        logger.info(f"本地 IP: {xbox.ip_address or '未知'}")
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
        wakeup_result = await matcher._wakeup_xbox(xbox, timeout=30)
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
    elif error_code == "NO_LOCAL_MATCH":
        cloud_count = error_details.get("cloud_authorized_count", 0)
        online_count = error_details.get("local_online_count", 0)
        standby_count = error_details.get("local_standby_count", 0)
        offline_count = error_details.get("local_offline_count", 0)
        
        logger.warning(f"\n原因: 云端授权 {cloud_count} 台，但局域网只有 {online_count} 台在线")
        logger.warning("\n解决方案:")
        logger.warning("1. 请确保 Xbox 主机已开机")
        logger.warning("")
        logger.warning("2. 检查 Xbox 网络设置:")
        logger.warning("   - 确保 Xbox 和 PC 在同一局域网")
        logger.warning("   - 检查 Xbox 的网络连接状态")
        logger.warning("")
        logger.warning("3. 如果 Xbox 处于待机模式，确保已开启远程唤醒功能")
        logger.warning("")
        logger.warning("4. 检查 Xbox 电源模式设置（建议使用 Instant-On）:")
        logger.warning("   - 设置 > 电源 > 启动模式")
        logger.warning("   - 选择 '即时开启'")
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

