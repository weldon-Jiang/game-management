"""
步骤三：串流环境初始化
=====================

功能说明：
- 初始化Xbox串流连接
- 建立画面捕获能力
- 为步骤四提供画面检测支持

核心定位：
- 这是步骤四的"准备工作"
- 将串流连接和画面捕获能力初始化好
- 步骤四直接使用这些能力进行游戏自动化

方法拆分：
- step3_streaming_init(): 执行串流环境初始化主流程
- _init_stream_window(): 初始化串流窗口
- _init_frame_capture(): 初始化画面捕获器
- _detect_game_screen(): 检测游戏主界面
- _report_progress(): 上报进度到平台

作者：技术团队
版本：1.0
"""

import asyncio
from typing import Callable, Optional, Any

from ..core.logger import get_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext, Step3Result, TaskStepStatus


async def step3_streaming_init(
    context: AgentTaskContext,
    check_cancel: Callable[[], bool],
    report_progress: Callable[[str, str, str], None]
) -> Step3Result:
    """
    步骤三执行：串流环境初始化

    核心职责：
    - 为步骤四准备串流环境
    - 初始化画面捕获能力供步骤四使用
    - 检测游戏主界面

    流程：
    1. 初始化串流窗口
    2. 初始化画面捕获器
    3. 检测游戏主界面
    4. 返回画面捕获器到上下文供步骤四使用

    参数：
    - context: 任务上下文（包含步骤二建立的Xbox连接）
    - check_cancel: 取消检查函数
    - report_progress: 进度上报函数

    返回：
    - Step3Result: 包含初始化结果的Step3Result
    """
    logger = get_logger(f'step3_init_{context.task_id}')
    stream_logger = get_stream_logger(context.streaming_account_email)
    logger.info("=== 步骤三：开始串流环境初始化 ===")
    stream_logger.info("=== 开始串流环境初始化 ===")

    context.update_step_status("step3", TaskStepStatus.RUNNING, "正在初始化串流环境...")
    await report_progress(context.task_id, "STEP3", "RUNNING", "正在初始化串流环境...")

    try:
        if check_cancel():
            logger.info("任务被取消，步骤三终止")
            context.update_step_status("step3", TaskStepStatus.SKIPPED, "任务被取消")
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step3", TaskStepStatus.RUNNING, "正在初始化串流窗口...")
        await report_progress(context.task_id, "STEP3", "RUNNING", "正在初始化串流窗口...")
        stream_logger.info("正在初始化串流窗口...")

        window = await _init_stream_window(context, logger, stream_logger)
        if not window:
            error_msg = "串流窗口初始化失败"
            logger.error(error_msg)
            stream_logger.error(error_msg)
            context.update_step_status("step3", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
            return Step3Result(success=False, error_code="WINDOW_INIT_FAILED", message=error_msg)

        if check_cancel():
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step3", TaskStepStatus.RUNNING, "正在初始化画面捕获器...")
        await report_progress(context.task_id, "STEP3", "RUNNING", "正在初始化画面捕获器...")
        stream_logger.info("正在初始化画面捕获器...")

        capture = await _init_frame_capture(context, window, logger, stream_logger)
        if not capture:
            error_msg = "画面捕获器初始化失败"
            logger.error(error_msg)
            stream_logger.error(error_msg)
            context.update_step_status("step3", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
            return Step3Result(success=False, error_code="CAPTURE_INIT_FAILED", message=error_msg)

        context.frame_capture = capture
        logger.info("画面捕获器初始化成功，已保存到上下文供步骤四使用")

        if check_cancel():
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step3", TaskStepStatus.RUNNING, "正在检测游戏界面...")
        await report_progress(context.task_id, "STEP3", "RUNNING", "正在检测游戏界面...")

        game_ready = await _detect_game_screen(context, window, logger, stream_logger)
        if not game_ready:
            logger.warning("游戏界面检测未完成，但继续执行")

        success_msg = "串流环境初始化完成，画面捕获器已准备就绪"
        logger.info(success_msg)
        stream_logger.info(success_msg)
        context.update_step_status("step3", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(context.task_id, "STEP3", "COMPLETED", success_msg)

        return Step3Result(success=True, message=success_msg)

    except asyncio.CancelledError:
        logger.info("步骤三被取消")
        stream_logger.info("步骤三被取消")
        context.update_step_status("step3", TaskStepStatus.SKIPPED, "任务被取消")
        return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

    except Exception as e:
        error_msg = f"步骤三执行异常: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step3", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
        return Step3Result(success=False, error_code="EXCEPTION", message=error_msg)


async def _init_stream_window(
    context: AgentTaskContext,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    初始化串流窗口

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - StreamWindow或None
    """
    try:
        from ..windows.stream_window import StreamWindow

        window = StreamWindow(window_title="Xbox")

        if context.window_id:
            window._hwnd = context.window_id
            logger.info(f"使用已有窗口句柄: {context.window_id}")
        else:
            await window.find_window()
            if not window._hwnd:
                logger.warning("未找到Xbox窗口，将使用默认窗口")
                window._hwnd = context.window_id

        await window.activate()
        logger.info("串流窗口初始化成功")
        stream_logger.info("串流窗口初始化成功")

        return window

    except Exception as e:
        logger.error(f"初始化串流窗口失败: {e}")
        stream_logger.error(f"初始化串流窗口失败: {e}")
        return None


async def _init_frame_capture(
    context: AgentTaskContext,
    window: Any,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    初始化画面捕获器

    参数：
    - context: 任务上下文
    - window: 串流窗口
    - logger: 主日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - VideoFrameCapture或None
    """
    try:
        from ..vision.frame_capture import VideoFrameCapture

        capture = VideoFrameCapture(window)
        context.frame_capture = capture

        frame = await capture.capture_frame()
        if frame:
            logger.info(f"画面捕获器初始化成功，分辨率: {frame.width}x{frame.height}")
            stream_logger.info(f"画面捕获器初始化成功，分辨率: {frame.width}x{frame.height}")
        else:
            logger.warning("画面捕获器初始化成功，但无法捕获首帧")
            stream_logger.warning("画面捕获器初始化成功，但无法捕获首帧")

        return capture

    except Exception as e:
        logger.error(f"初始化画面捕获器失败: {e}")
        stream_logger.error(f"初始化画面捕获器失败: {e}")
        return None


async def _detect_game_screen(
    context: AgentTaskContext,
    window: Any,
    logger,
    stream_logger
) -> bool:
    """
    检测游戏主界面

    参数：
    - context: 任务上下文
    - window: 串流窗口
    - logger: 主日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - bool: 是否检测到游戏界面
    """
    try:
        if context.frame_capture is None:
            logger.warning("画面捕获器未初始化，跳过游戏界面检测")
            return False

        frame = await context.frame_capture.capture_frame()
        if frame is None:
            logger.warning("无法捕获游戏画面")
            stream_logger.warning("无法捕获游戏画面")
            return False

        logger.info(f"游戏画面捕获成功: {frame.width}x{frame.height}")
        stream_logger.info(f"游戏画面捕获成功: {frame.width}x{frame.height}")
        return True

    except Exception as e:
        logger.error(f"检测游戏界面失败: {e}")
        stream_logger.error(f"检测游戏界面失败: {e}")
        return False
