"""xblive/xsrp 栈专用：GSSV play + WebRTC 串流握手（消费 Step1 StreamingAuthCredentials）。"""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from ..gssv.client import GssvClient
from ..gssv.cloud_play_session import GssvCloudPlaySession
from ..gssv.cloud_webrtc import AIORTC_AVAILABLE, GssvWebRtcSession
from ..task.task_context import AgentTaskContext
from .cloud_stream_controller import CloudStreamController
from .streaming_credentials import StreamingAuthCredentials, StreamingAuthError, get_streaming_credentials


class XsrpCloudFrameController:
    """WebRTC 解码帧供 Step3 VideoFrameCapture direct 模式读取。"""

    def __init__(self, webrtc: GssvWebRtcSession):
        self._webrtc = webrtc

    async def get_frame(self, timeout: float = 1.0):
        return await self._webrtc.get_latest_frame(timeout=timeout)


async def cleanup_xsrp_cloud_attempt(context: AgentTaskContext, task_logger) -> None:
    """单台 xsrp 云端握手失败后清理部分会话。"""
    session = getattr(context, "xbox_session", None)
    if session and hasattr(session, "disconnect"):
        try:
            await session.disconnect()
        except Exception as exc:
            task_logger.debug("清理 xsrp cloud 会话异常: %s", exc)

    webrtc = getattr(context, "_cloud_webrtc", None)
    if webrtc and hasattr(webrtc, "close"):
        try:
            await webrtc.close()
        except Exception as exc:
            task_logger.debug("清理 xsrp webrtc 异常: %s", exc)

    gssv_client = getattr(context, "_gssv_client", None)
    if gssv_client and hasattr(gssv_client, "close"):
        try:
            await gssv_client.close()
        except Exception as exc:
            task_logger.debug("清理 xsrp gssv client 异常: %s", exc)

    context.xbox_session = None
    context._cloud_webrtc = None
    context._gssv_client = None
    context._cloud_frame_controller = None
    for attr in (
        "_direct_capture",
        "_video_mode",
        "_video_capture_mode",
        "_rtp_available",
        "_stream_mode",
    ):
        if hasattr(context, attr):
            setattr(context, attr, None if attr != "_rtp_available" else False)


async def connect_xsrp_cloud(
    context: AgentTaskContext,
    creds: StreamingAuthCredentials,
    task_logger,
    stream_logger,
) -> Tuple[bool, Dict[str, Any]]:
    """
    xsrp 栈云端串流：play → Provisioned → WebRTC → 首帧 → 输入通道。

    对齐 libxsrp OpenStreaming 在 XblAuth 换票之后的 GSSV/WebRTC 段。
    """
    connect_details: Dict[str, Any] = {
        "streamMode": "xsrp_cloud",
        "streamingStack": "xsrp",
        "errorCode": "",
        "errorMessage": "",
    }

    if not AIORTC_AVAILABLE:
        connect_details["errorCode"] = "AIORTC_MISSING"
        connect_details["errorMessage"] = "未安装 aiortc/av，无法走 xsrp 云端 WebRTC"
        return False, connect_details

    xbox_info = context.current_xbox
    if not xbox_info:
        connect_details["errorCode"] = "NO_XBOX"
        connect_details["errorMessage"] = "缺少目标 Xbox 主机信息"
        return False, connect_details

    cloud_err = creds.validate_for_cloud()
    if cloud_err:
        connect_details["errorCode"] = "NO_GS_TOKEN"
        connect_details["errorMessage"] = cloud_err
        return False, connect_details

    server_id = xbox_info.id or xbox_info.live_id or creds.server_id or ""
    play_path = xbox_info.play_path or creds.play_path or "v5/sessions/home/play"
    base_uri = creds.gssv_base_uri

    task_logger.info(
        "xsrp 云端串流: %s serverId=%s baseUri=%s auth=%s",
        xbox_info.name,
        server_id,
        base_uri,
        creds.auth_provider,
    )
    stream_logger.info(f"xsrp 云端串流: {xbox_info.name} ({server_id})")

    client = GssvClient(base_uri, creds.gs_token)
    context._gssv_client = client
    context._streaming_stack = "xsrp"
    webrtc: Optional[GssvWebRtcSession] = None

    try:
        play_session = GssvCloudPlaySession(client, client.endpoints)
        play_ctx = await play_session.create_and_wait(server_id, play_path)
        connect_details["sessionId"] = play_ctx.session_id
        connect_details["sessionPath"] = play_ctx.session_path
        connect_details["provisionState"] = play_ctx.state

        webrtc = GssvWebRtcSession(client, play_ctx)
        context._cloud_webrtc = webrtc
        await webrtc.connect()

        from .xsrp_access_input_loop import reset_controller_write_stats

        reset_controller_write_stats(context)

        first_frame = await webrtc.wait_first_frame()
        connect_details["firstFrame"] = first_frame
        if not first_frame:
            connect_details["errorCode"] = "XSRP_FIRST_FRAME_TIMEOUT"
            connect_details["errorMessage"] = "WebRTC 已连接但未收到首帧"
            return False, connect_details

        controller = CloudStreamController(
            webrtc,
            server_name=xbox_info.name,
            server_id=server_id,
        )
        context.xbox_session = controller
        context._stream_mode = "xsrp_cloud"
        context._video_mode = "cloud"
        context._rtp_available = False
        context._video_capture_mode = "direct"
        frame_ctrl = XsrpCloudFrameController(webrtc)
        context._direct_capture = frame_ctrl
        context._cloud_frame_controller = frame_ctrl

        frame = await frame_ctrl.get_frame(timeout=2.0)
        if frame is not None:
            h, w = frame.shape[:2]
            context.stream_width = w
            context.stream_height = h
            connect_details["firstFrameSize"] = f"{w}x{h}"

        connect_details["inputChannelState"] = controller.input_channel_state
        connect_details["decodeMode"] = "webrtc_direct"
        task_logger.info("✓ xsrp 云端串流成功: %s", server_id)
        stream_logger.info(f"xsrp 云端串流成功: {xbox_info.name}")
        return True, connect_details

    except Exception as exc:
        connect_details["errorCode"] = "XSRP_CONNECT_FAILED"
        connect_details["errorMessage"] = str(exc)
        task_logger.error("xsrp 云端串流失败: %s", exc, exc_info=True)
        if webrtc:
            try:
                await webrtc.close()
            except Exception:
                pass
        try:
            await client.close()
        except Exception:
            pass
        context._cloud_webrtc = None
        context._gssv_client = None
        return False, connect_details


def require_xsrp_credentials(context: AgentTaskContext) -> StreamingAuthCredentials:
    """解析 Step1 凭证；失败抛 StreamingAuthError。"""
    return get_streaming_credentials(context)
