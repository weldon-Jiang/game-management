"""
Step1~3 串流管道诊断 — 供平台 TaskDetail 展示（auth/discovery/lan/first_frame/input）。
"""

from typing import Any, Dict, Optional


def _step_status(ok: bool, detail: str = "") -> Dict[str, Any]:
    return {"status": "ok" if ok else "failed", "detail": detail or ("ok" if ok else "failed")}


async def collect_stream_pipeline_diagnostics(context: Any) -> Dict[str, Any]:
    """从 AgentTaskContext 收集管道五步状态。"""
    ms_tokens = getattr(context, "microsoft_tokens", None)
    auth_ok = bool(ms_tokens and getattr(ms_tokens, "access_token", None))
    auth_detail = "MSAL token ready" if auth_ok else "MSAL token missing"

    xbox = getattr(context, "current_xbox", None) or getattr(context, "assigned_xbox", None)
    discovery_ok = bool(xbox and (getattr(xbox, "ip_address", None) or getattr(xbox, "id", None)))
    discovery_detail = (
        f"{getattr(xbox, 'name', '')} @ {getattr(xbox, 'ip_address', '') or getattr(xbox, 'id', '')}"
        if discovery_ok
        else "console not matched"
    )

    session = getattr(context, "xbox_session", None)

    result: Dict[str, Any] = {
        "auth": _step_status(auth_ok, auth_detail),
        "discovery": _step_status(discovery_ok, discovery_detail),
        "frameCaptureMode": getattr(context, "_video_capture_mode", "unknown"),
        "streamMode": "lan",
    }

    lan_ok = bool(
        getattr(context, "_smartglass_enabled", False)
        or (session is not None and getattr(session, "is_connected", False))
    )
    lan_detail = getattr(xbox, "ip_address", "") if xbox else "no ip"
    result["lanConnect"] = _step_status(
        lan_ok, f"SmartGlass @ {lan_detail}" if lan_ok else "not connected"
    )

    frame = None
    capture = getattr(context, "frame_capture", None)
    if capture is not None:
        try:
            frame = await capture.capture_frame()
        except Exception:
            frame = None
    first_ok = frame is not None
    first_detail = "no frame"
    if frame is not None:
        w = getattr(frame, "width", None)
        h = getattr(frame, "height", None)
        if w and h:
            first_detail = f"{w}x{h}"
        elif hasattr(frame, "shape"):
            first_detail = f"{frame.shape[1]}x{frame.shape[0]}"
    result["firstFrame"] = _step_status(first_ok, first_detail)

    input_state: Optional[str] = None
    input_ok = False
    if session is not None:
        input_state = getattr(session, "input_channel_state", None)
        healthy = getattr(session, "is_input_channel_healthy", None)
        input_ok = healthy() if callable(healthy) else input_state == "open"
    input_detail = input_state or ("open" if input_ok else "closed")
    channel_label = "SmartGlass"
    result["inputDc"] = _step_status(input_ok, f"{channel_label} {input_detail}")

    return result
