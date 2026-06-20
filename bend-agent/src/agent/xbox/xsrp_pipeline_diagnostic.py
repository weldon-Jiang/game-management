"""xsrp 栈管道诊断（TaskDetail pipelineDiagnostic）。"""

from typing import Any, Dict, Optional

from ..task.task_context import AgentTaskContext


def pipeline_diagnostic_from_context(
    context: AgentTaskContext,
    *,
    step3_merged: Optional[bool] = None,
) -> Dict[str, Any]:
    session = getattr(context, "xbox_session", None)
    first_w = int(getattr(context, "stream_width", 0) or 0)
    first_h = int(getattr(context, "stream_height", 0) or 0)
    capture_mode = getattr(context, "_video_capture_mode", "") or "direct"
    stream_mode = getattr(context, "_stream_mode", None) or "xsrp_cloud"

    input_state = None
    input_ok = False
    if session is not None:
        input_state = getattr(session, "input_channel_state", None)
        if input_state is None and hasattr(session, "is_input_channel_healthy"):
            input_ok = session.is_input_channel_healthy()
            input_state = "open" if input_ok else "closed"
        else:
            input_ok = input_state == "open"

    first_frame = "ok" if capture_mode == "direct" and first_w and first_h else "pending"
    if getattr(context, "frame_capture", None) is not None and first_frame == "pending":
        first_frame = "ok"

    runtime = getattr(context, "_stream_runtime", None)
    capture_pump = "pending"
    if runtime is not None and runtime.is_capture_running:
        capture_pump = "ok"
    elif getattr(context, "_step3_init_completed", False):
        capture_pump = "ok"

    display = "pending"
    if getattr(context, "sdl_window", None) is not None:
        display = "ok"
    elif getattr(context, "_step3_init_completed", False) and not getattr(
        context, "enable_window_display", True
    ):
        display = "ok"

    merged = step3_merged
    if merged is None:
        merged = bool(getattr(context, "_step3_init_completed", False))

    current_xbox = getattr(context, "current_xbox", None)

    diag: Dict[str, Any] = {
        "auth": "ok",
        "discovery": "ok" if current_xbox else "pending",
        "gssvPlay": "ok" if current_xbox else "pending",
        "webrtc": "ok" if session and getattr(session, "is_connected", False) else "pending",
        "firstFrame": first_frame,
        "firstFrameSize": f"{first_w}x{first_h}" if first_w and first_h else None,
        "capturePump": capture_pump,
        "inputDc": "ok" if input_ok else ("pending" if input_state is None else "fail"),
        "inputChannelState": input_state,
        "display": display,
        "streamRuntime": "ok" if getattr(context, "_step3_init_completed", False) else "pending",
        "streamMode": stream_mode,
        "frameCaptureMode": capture_mode,
        "streamingStack": getattr(context, "_streaming_stack", "xsrp"),
        "platform": "xbox",
        "decodeMode": "webrtc_direct",
        "step3Merged": merged,
    }
    if getattr(context, "_input_pump", None) is not None:
        pump = context._input_pump
        if getattr(pump, "running", False):
            diag["inputPump"] = "ok"
    return diag
