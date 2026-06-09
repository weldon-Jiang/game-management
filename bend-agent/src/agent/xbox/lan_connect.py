"""Xbox LAN 串流连接：SmartGlass + DTLS-SRTP + RTP（从 automation 迁出）。"""

import asyncio
from typing import Any, Dict, Tuple

from ..core.config import config as app_config
from ..task.task_context import AgentTaskContext
from .lan_media_session import establish_lan_media_security, wait_for_first_rtp_packet
from .smartglass_connect import connect_smartglass_udp
from .stream_controller import StreamConfig, XboxStreamController


async def cleanup_lan_connect_attempt(context: AgentTaskContext, task_logger) -> None:
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


async def connect_to_xbox_lan(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
) -> Tuple[bool, Dict[str, Any]]:
    """通过局域网 SmartGlass + RTP 连接 Xbox。"""
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

        task_logger.info("目标 Xbox: %s @ %s:%s (serverId=%s)", xbox_info.name, xbox_info.ip_address, port, xbox_info.id)
        stream_logger.info(f"开始 LAN 串流: {xbox_info.name} @ {xbox_info.ip_address}")

        controller = XboxStreamController()
        xsts_token = None
        user_hash = None
        if context.xbox_tokens:
            xsts_token = getattr(context.xbox_tokens, "xsts_token", None)
            user_hash = getattr(context.xbox_tokens, "user_hash", None)

        connect_details["authTokenType"] = "xsts" if xsts_token else "none"

        if (
            bool(app_config.get("lan_stream.smartglass_udp_connect", True))
            and xsts_token
            and user_hash
        ):
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
            return False, connect_details

        stream_config = StreamConfig(
            xbox_ip=xbox_info.ip_address,
            xbox_port=port,
            audio_enabled=False,
        )
        if not await controller.start_stream(stream_config):
            connect_details["errorCode"] = "STREAM_START_FAILED"
            connect_details["errorMessage"] = "SmartGlass 串流启动失败"
            return False, connect_details

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
            return False, connect_details

        context._lan_srtp_keys = srtp_keys
        context._lan_rtp_port = lan_endpoints.rtp_port
        context._lan_endpoints = lan_endpoints
        context.xbox_session = controller
        context._lan_direct = True

        video_ok = await start_video_receiver(context, task_logger, stream_logger)
        connect_details["rtpEnabled"] = bool(getattr(context, "_rtp_available", False))
        connect_details["videoMode"] = getattr(context, "_video_mode", "unknown")
        if not video_ok:
            connect_details["errorCode"] = "VIDEO_RECEIVER_FAILED"
            connect_details["errorMessage"] = "LAN 视频接收器启动失败"
            return False, connect_details

        first_rtp = await wait_for_first_rtp_packet(controller)
        connect_details["firstRtpPacket"] = first_rtp
        if not first_rtp:
            connect_details["errorCode"] = "FIRST_RTP_TIMEOUT"
            connect_details["errorMessage"] = "DTLS 成功但未收到首包 RTP/SRTP"
            return False, connect_details

        task_logger.info("✓ Xbox LAN 串流连接成功: %s", xbox_info.ip_address)
        stream_logger.info(f"Xbox LAN 串流连接成功: {xbox_info.ip_address}")
        return True, connect_details

    except asyncio.TimeoutError as exc:
        connect_details["errorCode"] = "TIMEOUT"
        connect_details["errorMessage"] = f"LAN 连接 Xbox 超时: {exc}"
        return False, connect_details
    except Exception as exc:
        connect_details["errorCode"] = "EXCEPTION"
        connect_details["errorMessage"] = f"LAN 连接 Xbox 异常: {exc}"
        task_logger.error(connect_details["errorMessage"], exc_info=True)
        return False, connect_details


async def init_video_stream_controller(context: AgentTaskContext, task_logger, stream_logger) -> bool:
    """初始化视频流控制器（RTP / 直接捕获）。"""
    try:
        from ..vision.video_stream_controller import (
            DirectCaptureController,
            VideoStreamConfig,
            VideoStreamController,
        )

        if context._rtp_available and context.xbox_session:
            rtp_session = getattr(context.xbox_session, "_rtp_session", None)
            if rtp_session:
                video_config = VideoStreamConfig(
                    width=1280,
                    height=720,
                    framerate=30,
                    bitrate=5000000,
                    codec="H264",
                    rtp_port=50500,
                )
                video_controller = VideoStreamController()
                success = await video_controller.start(video_config, rtp_session)
                if success:
                    context._video_stream_controller = video_controller
                    context._video_capture_mode = "rtp"
                    return True

        direct_capture = DirectCaptureController()
        context._direct_capture = direct_capture
        context._video_capture_mode = "direct"
        return True
    except Exception as exc:
        task_logger.warning("视频流控制器初始化失败: %s", exc)
        context._video_capture_mode = "fallback"
        return True


async def start_video_receiver(context: AgentTaskContext, task_logger, stream_logger) -> bool:
    """启动 LAN RTP 视频接收器。"""
    try:
        if not context.xbox_session:
            return False

        srtp_keys = getattr(context, "_lan_srtp_keys", None)
        rtp_port = getattr(context, "_lan_rtp_port", None) or int(
            app_config.get("lan_stream.rtp_port", 50500)
        )

        video_success = await context.xbox_session.start_video_receiver(
            mode="rtp",
            port=rtp_port,
            srtp_keys=srtp_keys,
            allow_fallback=False,
        )

        video_mode = context.xbox_session.video_mode
        context._video_mode = video_mode
        context._rtp_available = video_mode == "rtp"
        await init_video_stream_controller(context, task_logger, stream_logger)
        return video_success
    except Exception as exc:
        task_logger.warning("视频流接收器初始化失败: %s", exc)
        context._video_mode = "win32gui"
        context._rtp_available = False
        context._video_capture_mode = "fallback"
        return False
