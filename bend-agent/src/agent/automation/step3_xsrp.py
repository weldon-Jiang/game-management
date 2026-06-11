"""
步骤三（xblive/xsrp 栈）：串流环境初始化。

对齐 streaming/xsrp.py 中 OpenStreaming 之后的 CaptureStreaming + WriteControllerData 通道：
- WebRTC direct 帧源 + SDL 显示 + InputPump + 空闲保活
"""

from __future__ import annotations

import asyncio
from typing import Any, Callable, Dict, Optional

from ..core.account_logger import get_stream_logger
from ..core.task_logger import get_task_logger
from ..task.task_context import AgentTaskContext, Step3Result, TaskStepStatus
from ..xbox.xsrp_frame_capture import XsrpFrameCapture
from ..xbox.xsrp_pipeline_diagnostic import pipeline_diagnostic_from_context
from ..xbox.xsrp_stream_keepalive import start_xsrp_idle_keepalive

# 复用旧 Step3 的窗口/输入/S DL 泵实现，避免重复维护
from .step3_display_helpers import (
    _ensure_controller_protocol,
    _format_window_title,
    _init_gamepad_controller,
    _init_keyboard_mapper,
    _init_sdl_window,
    _init_stream_window,
    _load_window_settings,
    _start_input_pump_if_ready,
    _start_sdl_display_pump,
    _wire_sdl_close_handler,
)


def _build_step3_pipeline_diagnostic(context: AgentTaskContext) -> Dict[str, Any]:
    diag = pipeline_diagnostic_from_context(context, step3_merged=True)
    if getattr(context, "_input_channel_dirty", False):
        diag["inputDc"] = "fail"
    return diag


async def step3_execute_xsrp_init(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable,
) -> Step3Result:
    """xsrp Step3：WebRTC 帧捕获 + 显示 + 输入通道就绪。"""
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)
    task_logger.info("=== 步骤三（xsrp）：开始串流环境初始化 ===")
    stream_logger.info("=== 步骤三（xsrp）：开始串流环境初始化 ===")

    context.update_step_status("step3", TaskStepStatus.RUNNING, "xsrp 正在初始化串流环境...")
    await report_progress(
        context.task_id, "STEP3", "RUNNING", "xsrp 正在初始化串流环境...",
        streamingStack="xsrp",
    )

    try:
        if check_cancel():
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        direct_capture = getattr(context, "_direct_capture", None)
        if direct_capture is None and getattr(context, "_cloud_frame_controller", None):
            direct_capture = context._cloud_frame_controller
            context._direct_capture = direct_capture

        if not context.xbox_session or direct_capture is None:
            msg = "xsrp Step3 缺少 Step2 WebRTC 会话或帧源"
            task_logger.error(msg)
            context.update_step_status("step3", TaskStepStatus.FAILED, msg)
            await report_progress(context.task_id, "STEP3", "FAILED", msg, streamingStack="xsrp")
            return Step3Result(success=False, error_code="NO_XSRP_SESSION", message=msg)

        window = await _init_stream_window(context, task_logger, stream_logger)
        if not window:
            msg = "xsrp 串流窗口初始化失败"
            context.update_step_status("step3", TaskStepStatus.FAILED, msg)
            await report_progress(context.task_id, "STEP3", "FAILED", msg, streamingStack="xsrp")
            return Step3Result(success=False, error_code="WINDOW_INIT_FAILED", message=msg)

        capture = XsrpFrameCapture(direct_capture)
        context.frame_capture = capture
        context._video_capture_mode = "direct"
        context._streaming_stack = "xsrp"

        frame = await capture.capture_frame()
        if frame is None:
            msg = "xsrp 首帧捕获失败"
            task_logger.error(msg)
            context.update_step_status("step3", TaskStepStatus.FAILED, msg)
            await report_progress(context.task_id, "STEP3", "FAILED", msg, streamingStack="xsrp")
            return Step3Result(success=False, error_code="CAPTURE_INIT_FAILED", message=msg)

        task_logger.info("xsrp 首帧: %sx%s", frame.width, frame.height)
        stream_logger.info(f"xsrp 首帧: {frame.width}x{frame.height}")

        from ..runtime.stream_runtime import get_or_create_stream_runtime

        stream_runtime = get_or_create_stream_runtime(context)
        stream_runtime.seed_latest_frame(frame)
        await stream_runtime.start_long_lived(task_logger)

        await _ensure_controller_protocol(context, task_logger, stream_logger)
        _bind_xsrp_input_close_handler(context, task_logger)

        if context.enable_window_display:
            sdl_window = await _init_sdl_window(context, task_logger, stream_logger)
            if sdl_window:
                context.sdl_window = sdl_window
                if hasattr(sdl_window, "show"):
                    sdl_window.show()
                await _start_sdl_display_pump(context, task_logger)

        await _init_gamepad_controller(context, task_logger, stream_logger)
        await _init_keyboard_mapper(context, task_logger, stream_logger)
        _wire_sdl_close_handler(context)

        stream_ready, ready_detail = await _validate_xsrp_stream_readiness(
            context, task_logger, stream_logger,
        )
        if not stream_ready:
            msg = f"xsrp 串流就绪检查未通过: {ready_detail}"
            context.update_step_status("step3", TaskStepStatus.FAILED, msg)
            await report_progress(context.task_id, "STEP3", "FAILED", msg, streamingStack="xsrp")
            return Step3Result(success=False, error_code="STREAM_NOT_READY", message=msg)

        await start_xsrp_idle_keepalive(context, task_logger)
        await _start_input_pump_if_ready(context, task_logger)

        success_msg = "xsrp 串流环境初始化完成"
        context.update_step_status("step3", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(
            context.task_id,
            "STEP3",
            "COMPLETED",
            success_msg,
            {
                "streamingStack": "xsrp",
                "frameCaptureMode": "direct",
                "sdlWindowEnabled": context.sdl_window is not None,
                "pipelineDiagnostic": _build_step3_pipeline_diagnostic(context),
            },
        )
        context._step3_init_completed = True
        return Step3Result(success=True, message=success_msg)

    except asyncio.CancelledError:
        context.update_step_status("step3", TaskStepStatus.SKIPPED, "任务被取消")
        return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")
    except Exception as exc:
        msg = f"xsrp 步骤三异常: {exc}"
        task_logger.error(msg, exc_info=True)
        context.update_step_status("step3", TaskStepStatus.FAILED, msg, str(exc))
        await report_progress(context.task_id, "STEP3", "FAILED", msg, streamingStack="xsrp")
        return Step3Result(success=False, error_code="EXCEPTION", message=msg)


def is_xsrp_stream_media_ready(context: AgentTaskContext) -> bool:
    """Step2 链末尾已跑完 Step3 时为 True，open_stream 可跳过重复初始化。"""
    return bool(
        getattr(context, "_step3_init_completed", False)
        and getattr(context, "frame_capture", None) is not None
        and getattr(context, "xbox_session", None) is not None
    )


def _bind_xsrp_input_close_handler(context: AgentTaskContext, task_logger) -> None:
    """WebRTC input 通道关闭时标记 dirty，供 Step4/重连感知。"""
    webrtc = getattr(context, "_cloud_webrtc", None)
    if webrtc is None or not hasattr(webrtc, "on_input_channel_close"):
        return

    def _on_close():
        context._input_channel_dirty = True
        task_logger.warning("xsrp input 通道 closed，已标记待恢复")

    webrtc.on_input_channel_close(_on_close)


async def _validate_xsrp_stream_readiness(context, task_logger, stream_logger) -> tuple:
    """验证 WebRTC 帧与 DataChannel 输入（无 LAN 重连）。"""
    from ..runtime.stream_runtime import capture_task_frame

    async def _check_frames() -> tuple:
        if context.frame_capture is None:
            return False, "画面捕获器未初始化"
        sizes = []
        for _ in range(3):
            frame = await capture_task_frame(context, timeout=1.0)
            if frame is None:
                return False, "连续截帧失败"
            sizes.append((frame.width, frame.height))
            await asyncio.sleep(0.5)
        if len(set(sizes)) > 1:
            return False, f"帧分辨率不稳定: {sizes}"
        return True, f"WebRTC 帧稳定 {sizes[0][0]}x{sizes[0][1]}"

    async def _check_input() -> tuple:
        session = getattr(context, "xbox_session", None)
        if session is None:
            return False, "无 xsrp 会话"
        if not getattr(session, "is_connected", False):
            return False, "WebRTC 未连接"
        ok1 = await session.send_keepalive()
        ok2 = await session.send_keepalive()
        if not (ok1 and ok2):
            return False, "DataChannel keepalive 失败"
        state = getattr(session, "input_channel_state", None) or "open"
        return True, f"xsrp input ready ({state})"

    frames_ok, frames_msg = await _check_frames()
    input_ok, input_msg = await _check_input()
    if frames_ok and input_ok:
        task_logger.info("xsrp STEP3 就绪: %s; %s", frames_msg, input_msg)
        return True, f"{frames_msg}; {input_msg}"

    if not input_ok:
        context._input_channel_dirty = True
    return False, f"{frames_msg}; {input_msg}"
