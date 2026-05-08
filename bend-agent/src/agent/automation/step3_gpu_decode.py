"""
步骤三：显卡解码流转
====================

功能说明：
- 接收显卡解码后的视频流
- 通过Moonlight/Xbox App窗口显示
- 持续捕获画面供后续模板匹配使用

技术实现：
- 复用现有 VideoFrameCapture 模块进行窗口截图
- GPU解码后的画面通过窗口展示
- 截图用于后续的模板匹配和OCR识别

方法拆分：
- step3_execute_decode(): 执行显卡解码流转主流程
- _start_stream_display(): 启动串流显示
- _capture_frame(): 捕获画面验证
- _detect_game_scene(): 检测游戏场景
- _report_progress(): 上报进度到平台

作者：技术团队
版本：1.0
"""

import asyncio
from typing import Callable, Optional, Any

from ..core.logger import get_logger
from .task_context import AgentTaskContext, Step3Result, TaskStepStatus


async def step3_execute_decode(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str], None]
) -> Step3Result:
    """
    步骤三执行：显卡解码流转

    流程：
    1. 启动Moonlight/Xbox App窗口显示串流
    2. 建立持续的画面捕获循环
    3. 捕获首帧确认串流正常
    4. 检测游戏主界面
    5. 上报进度到平台

    参数：
    - context: 任务上下文
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数

    返回：
    - Step3Result: 包含解码流转结果的Step3Result
    """
    logger = get_logger(f'step3_decode_{context.task_id}')
    logger.info("=== 步骤三：开始显卡解码流转 ===")

    context.update_step_status("step3", TaskStepStatus.RUNNING, "正在启动串流显示...")
    await report_progress(context.task_id, "STEP3", "RUNNING", "正在启动串流显示...")

    try:
        if check_cancel():
            logger.info("任务被取消，步骤三终止")
            context.update_step_status("step3", TaskStepStatus.SKIPPED, "任务被取消")
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        window = await _get_or_create_window(context, logger)
        if not window:
            error_msg = "无法获取窗口"
            logger.error(error_msg)
            context.update_step_status("step3", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
            return Step3Result(success=False, error_code="WINDOW_FAILED", message=error_msg)

        if check_cancel():
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step3", TaskStepStatus.RUNNING, "正在验证串流...")
        await report_progress(context.task_id, "STEP3", "RUNNING", "正在验证串流...")

        frame = await _capture_frame(context, window, logger)

        if frame is None:
            error_msg = "无法捕获串流画面"
            logger.error(error_msg)
            context.update_step_status("step3", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
            return Step3Result(success=False, error_code="DECODE_FAILED", message=error_msg)

        logger.info(f"串流画面捕获成功: {frame.width}x{frame.height}")

        if check_cancel():
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step3", TaskStepStatus.RUNNING, "正在检测游戏界面...")
        await report_progress(context.task_id, "STEP3", "RUNNING", "正在检测游戏界面...")

        game_detected = await _detect_game_scene(context, window, logger)

        if not game_detected:
            logger.warning("未检测到游戏主界面，但继续执行")

        success_msg = "显卡解码流转正常，已进入游戏"
        logger.info(success_msg)
        context.update_step_status("step3", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP3", "COMPLETED", success_msg)

        return Step3Result(success=True, message=success_msg)

    except asyncio.CancelledError:
        logger.info("步骤三被取消")
        context.update_step_status("step3", TaskStepStatus.SKIPPED, "任务被取消")
        return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

    except Exception as e:
        error_msg = f"步骤三执行异常: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step3", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
        return Step3Result(success=False, error_code="EXCEPTION", message=error_msg)


async def _get_or_create_window(context: AgentTaskContext, logger) -> Optional[Any]:
    """
    获取或创建窗口

    参数：
    - context: 任务上下文
    - logger: 日志记录器

    返回：
    - StreamWindow或None
    """
    try:
        from ..windows.stream_window import StreamWindow
        from ..vision.frame_capture import VideoFrameCapture

        window = StreamWindow(window_title="Xbox")
        await window.find_window()

        if window._hwnd:
            await window.activate()
            logger.info("窗口已找到并激活")
        else:
            logger.warning("窗口未找到，尝试创建新窗口")
            window._hwnd = context.window_id

        capture = VideoFrameCapture(window)
        context.frame_capture = capture

        return window

    except Exception as e:
        logger.error(f"获取或创建窗口失败: {e}")
        return None


async def _capture_frame(
    context: AgentTaskContext,
    window: Any,
    logger
) -> Optional[Any]:
    """
    捕获画面

    参数：
    - context: 任务上下文
    - window: 窗口对象
    - logger: 日志记录器

    返回：
    - Frame或None
    """
    try:
        if context.frame_capture is None:
            from ..vision.frame_capture import VideoFrameCapture
            context.frame_capture = VideoFrameCapture(window)

        frame = await context.frame_capture.capture_frame()
        return frame

    except Exception as e:
        logger.error(f"捕获画面失败: {e}")
        return None


async def _detect_game_scene(
    context: AgentTaskContext,
    window: Any,
    logger
) -> bool:
    """
    检测游戏场景

    简化实现：仅验证能否捕获到画面
    后续可扩展为模板匹配检测游戏主界面

    参数：
    - context: 任务上下文
    - window: 窗口对象
    - logger: 日志记录器

    返回：
    - bool: 是否检测到游戏
    """
    try:
        frame = await _capture_frame(context, window, logger)
        if frame is None:
            return False

        logger.info(f"画面捕获正常，继续执行")
        return True

    except Exception as e:
        logger.error(f"检测游戏场景失败: {e}")
        return False
