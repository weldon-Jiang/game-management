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
版本：4.0

版本历史：
- 3.0: 集成PlaySession管理和SDP握手功能
- 4.0: 集成混合模式视频流接收（方案3）
"""

import asyncio
import random
from typing import Callable, Optional, Dict, Any, List

from ..core.logger import get_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext, Step2Result, XboxInfo, TaskStepStatus


class XboxMatchResult:
    """Xbox主机匹配结果"""
    def __init__(self, success: bool, xbox_info: XboxInfo = None, 
                 match_type: str = "", message: str = ""):
        self.success = success
        self.xbox_info = xbox_info
        self.match_type = match_type
        self.message = message


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
            logger.error(f"Xbox主机匹配失败: {match_result.message}")
            stream_logger.error(f"Xbox主机匹配失败: {match_result.message}")
            context.update_step_status("step2", TaskStepStatus.FAILED, match_result.message)
            await report_progress(context.task_id, "STEP2", "FAILED", match_result.message)
            return Step2Result(success=False, error_code="XBOX_MATCH_FAILED",
                             message=match_result.message)

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
                   f"匹配方式: {match_result.match_type}")
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
    匹配Xbox主机

    匹配逻辑：
    1. 如果指定了Xbox主机，直接使用
    2. 如果未指定，发现在线Xbox并匹配
    3. 多匹配时随机选择

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号日志记录器
    - check_cancel: 取消检查函数

    返回：
    - XboxMatchResult: 包含匹配结果的对象
    """
    if context.assigned_xbox:
        logger.info(f"使用指定的Xbox主机: {context.assigned_xbox.name} "
                   f"({context.assigned_xbox.ip_address})")
        stream_logger.info(f"使用指定的Xbox主机: {context.assigned_xbox.name}")

        online = await _test_xbox_connection(context.assigned_xbox.ip_address, logger)
        if online:
            return XboxMatchResult(
                success=True,
                xbox_info=context.assigned_xbox,
                match_type="assigned",
                message="使用指定的Xbox主机"
            )
        else:
            return XboxMatchResult(
                success=False,
                xbox_info=None,
                match_type="assigned",
                message=f"指定的Xbox主机不在线: {context.assigned_xbox.ip_address}"
            )

    logger.info("未指定Xbox主机，开始自动匹配...")
    stream_logger.info("未指定Xbox主机，开始自动匹配...")
    discovered_xboxes = await _discover_xbox_devices(logger)

    if not discovered_xboxes:
        return XboxMatchResult(
            success=False,
            xbox_info=None,
            match_type="discover",
            message="局域网未发现Xbox主机"
        )

    logger.info(f"发现 {len(discovered_xboxes)} 个Xbox主机")
    stream_logger.info(f"发现 {len(discovered_xboxes)} 个Xbox主机")

    if len(discovered_xboxes) == 1:
        selected = discovered_xboxes[0]
        logger.info(f"只有一台Xbox，直接选择: {selected.name}")
        stream_logger.info(f"只有一台Xbox，直接选择: {selected.name}")
        return XboxMatchResult(
            success=True,
            xbox_info=selected,
            match_type="discovered",
            message=f"发现Xbox: {selected.name}"
        )

    selected = random.choice(discovered_xboxes)
    logger.info(f"多台Xbox，随机选择: {selected.name} ({selected.ip_address})")
    stream_logger.info(f"多台Xbox，随机选择: {selected.name}")
    return XboxMatchResult(
        success=True,
        xbox_info=selected,
        match_type="random_selected",
        message=f"随机选择Xbox: {selected.name}"
    )


async def _discover_xbox_devices(logger) -> List[XboxInfo]:
    """
    发现局域网中的Xbox设备

    参数：
    - logger: 日志记录器

    返回：
    - List[XboxInfo]: Xbox设备列表
    """
    try:
        from ..xbox.xbox_discovery import XboxDiscovery

        discovery = XboxDiscovery()
        devices = await discovery.discover()

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

        logger.info(f"开始连接Xbox: {xbox_info.ip_address}")
        stream_logger.info(f"开始连接Xbox: {xbox_info.name} ({xbox_info.ip_address})")

        success = await xbox_controller.connect_with_token(
            xbox_ip=xbox_info.ip_address,
            xbox_token=xbox_token,
            user_hash=user_hash
        )

        if not success:
            logger.error(f"Xbox连接失败: {xbox_info.ip_address}")
            stream_logger.error(f"Xbox连接失败: {xbox_info.ip_address}")
            return False, connect_details

        logger.info(f"Xbox基础连接成功: {xbox_info.name}")
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

        logger.info(f"Xbox连接成功: {xbox_info.name}")
        stream_logger.info(f"Xbox连接成功: {xbox_info.name}")

        gpu_success = await _init_gpu_decoder(context, logger, stream_logger)
        connect_details["gpuAvailable"] = gpu_success
        connect_details["gpuType"] = getattr(context, '_gpu_type', 'cpu')
        
        video_success = await _start_video_receiver(context, logger, stream_logger)
        connect_details["videoMode"] = getattr(context, '_video_mode', 'win32gui')

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
    - 使用Xbox Live API创建流播放会话
    - 支持WebRTC SDP握手
    - 管理会话生命周期

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

        logger.info("开始创建PlaySession...")
        stream_logger.info("开始创建PlaySession...")

        play_session_mgr = XboxPlaySessionManager()
        context._play_session_manager = play_session_mgr

        ms_token = None
        if context.microsoft_tokens and hasattr(context.microsoft_tokens, 'access_token'):
            ms_token = context.microsoft_tokens.access_token
        elif context.xbox_tokens and hasattr(context.xbox_tokens, 'access_token'):
            ms_token = context.xbox_tokens.access_token

        if not ms_token:
            logger.warning("无可用的访问令牌，跳过PlaySession创建")
            return False

        play_session_mgr.set_access_token(ms_token)

        servers = await play_session_mgr.discover_servers()
        if not servers:
            logger.warning("未发现Xbox服务器，可能不在Xbox Live网络中")
            return False

        server_id = servers[0].get('serverId', '')
        if not server_id:
            logger.warning("服务器响应中无serverId")
            return False

        logger.info(f"发现Xbox服务器: {server_id}")
        stream_logger.info(f"发现Xbox服务器: {server_id}")

        session = await play_session_mgr.create_session(
            server_id=server_id,
            config=PlaySessionConfig(
                nano_version="V3;WebrtcTransport.dll",
                os_name="windows",
                sdk_type="web"
            )
        )

        if not session:
            logger.warning("PlaySession创建失败")
            return False

        logger.info(f"PlaySession创建成功: {session.session_id}")
        stream_logger.info(f"PlaySession创建成功: {session.session_id}")
        
        context._play_session_manager = play_session_mgr
        context._play_session_session_id = session.session_id
        
        sdp_success = await _exchange_sdp(
            context, session, logger, stream_logger
        )
        context._sdp_enabled = sdp_success

        if sdp_success:
            logger.info("SDP握手成功")
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

        sdp_answer = await play_session_mgr.exchange_sdp(
            session_id=session.session_id,
            sdp_offer=sdp_offer
        )

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
