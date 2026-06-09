"""Xbox LAN 串流管道诊断（TaskDetail pipelineDiagnostic）。"""

from typing import Any, Dict

from ..task.task_context import AgentTaskContext


def pipeline_diagnostic_from_context(context: AgentTaskContext) -> Dict[str, Any]:
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
        "platform": "xbox",
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
