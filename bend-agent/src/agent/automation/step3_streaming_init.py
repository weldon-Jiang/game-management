"""
步骤三：串流环境初始化
====================

功能说明：
- 初始化Xbox串流连接
- 建立画面捕获能力
- 初始化手柄控制（参考streaming项目）
- 为步骤四提供画面检测和手柄控制支持
- 支持高性能视频流显示（方案C优化）

核心定位：
- 这是步骤四的"准备工作"
- 将串流连接、画面捕获、手柄控制初始化好
- 步骤四直接使用这些能力进行游戏自动化

方法拆分：
- step3_streaming_init(): 执行串流环境初始化主流程
- _init_stream_window(): 初始化串流窗口
- _init_frame_capture(): 初始化画面捕获器（支持高性能模式）
- _init_gamepad_controller(): 初始化手柄控制器（新增）
- _init_keyboard_mapper(): 初始化键盘映射（新增）
- _detect_game_screen(): 检测游戏主界面
- _report_progress(): 上报进度到平台

作者：技术团队
版本：4.0

版本历史：
- 2.0: 集成手柄控制和键盘映射功能
- 3.0: 集成SDL2自绘窗口
- 4.0: 支持高性能视频流（方案C优化）
"""

import asyncio
import sys
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

        # frame_capture 是 Step4 场景识别和窗口显示的唯一画面来源，初始化失败必须终止准备流程。
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

        # 只建立 ControllerProtocol 通道，不在 Step3 发送自动化按键；Step4 才拥有自动化输入权。
        await _ensure_controller_protocol(context, logger, stream_logger)

        sdl_window = None
        if context.enable_window_display:
            context.update_step_status("step3", TaskStepStatus.RUNNING, "正在初始化SDL显示窗口...")
            stream_logger.info("正在初始化SDL显示窗口...")
            sdl_window = await _init_sdl_window(context, logger, stream_logger)
            if sdl_window:
                context.sdl_window = sdl_window
                if hasattr(sdl_window, "show"):
                    sdl_window.show()
                logger.info("SDL显示窗口初始化成功，已保存到上下文供步骤四使用")
                stream_logger.info("SDL显示窗口初始化成功")
            else:
                logger.warning("SDL显示窗口初始化失败，步骤四将不显示画面")
                stream_logger.warning("SDL显示窗口初始化失败")
        else:
            logger.info("窗口显示已禁用，跳过SDL窗口初始化")
            stream_logger.info("窗口显示已禁用")

        if check_cancel():
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        gamepad = await _init_gamepad_controller(context, logger, stream_logger)
        gamepad_available = gamepad is not None
        gamepad_name = getattr(gamepad, 'controller_name', None) if gamepad else None
        if gamepad:
            context._gamepad_controller = gamepad
            logger.info("手柄控制器初始化成功，已保存到上下文供步骤四使用")
            stream_logger.info("手柄控制器初始化成功")
        else:
            logger.warning("手柄控制器初始化失败，可能没有连接手柄")
            stream_logger.warning("手柄控制器初始化失败")

        keyboard_mapper = await _init_keyboard_mapper(context, logger, stream_logger)
        keyboard_available = keyboard_mapper is not None
        if keyboard_mapper:
            context._keyboard_mapper = keyboard_mapper
            _wire_sdl_close_handler(context)
            logger.info("键盘映射器初始化成功，已保存到上下文供步骤四使用")
            stream_logger.info("键盘映射器初始化成功")
        else:
            logger.warning("键盘映射器初始化失败")
            stream_logger.warning("键盘映射器初始化失败")

        if check_cancel():
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step3", TaskStepStatus.RUNNING, "正在检测游戏界面...")
        await report_progress(context.task_id, "STEP3", "RUNNING", "正在检测游戏界面...")

        stream_ready, ready_detail = await _validate_stream_readiness(
            context, logger, stream_logger
        )
        if context.sdl_window:
            # 就绪等待和手动接管期间仍需持续刷帧，否则 SDL 窗口会停在旧画面。
            await _start_sdl_display_pump(context, logger)
        if not stream_ready:
            error_msg = f"串流就绪检查未通过: {ready_detail}"
            logger.error(error_msg)
            stream_logger.error(error_msg)
            context.update_step_status("step3", TaskStepStatus.FAILED, error_msg)
            await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
            return Step3Result(
                success=False,
                error_code="STREAM_NOT_READY",
                message=error_msg,
            )

        game_ready = await _detect_game_screen(context, window, logger, stream_logger)
        if not game_ready:
            logger.warning("游戏界面检测未完成，但串流通道已就绪")

        success_msg = "串流环境初始化完成，画面捕获器和手柄控制器已准备就绪"
        logger.info(success_msg)
        stream_logger.info(success_msg)
        context.update_step_status("step3", TaskStepStatus.COMPLETED, success_msg)
        await report_progress(
            context.task_id, "STEP3", "COMPLETED", success_msg,
            {
                "gamepadAvailable": gamepad_available,
                "gamepadName": gamepad_name,
                "keyboardMapperAvailable": keyboard_available,
                "frameCaptureMode": getattr(context, '_video_capture_mode', 'unknown'),
                "sdlWindowEnabled": context.sdl_window is not None
            }
        )

        return Step3Result(success=True, message=success_msg)

    except asyncio.CancelledError:
        logger.info("步骤三被取消")
        stream_logger.info("步骤三被取消")
        context.update_step_status("step3", TaskStepStatus.SKIPPED, "任务被取消")
        return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

    except asyncio.TimeoutError as e:
        error_msg = f"步骤三执行超时: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step3", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
        return Step3Result(success=False, error_code="TIMEOUT", message=error_msg)

    except ConnectionError as e:
        error_msg = f"步骤三网络连接失败: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step3", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
        return Step3Result(success=False, error_code="CONNECTION_ERROR", message=error_msg)

    except ValueError as e:
        error_msg = f"步骤三参数错误: {str(e)}"
        logger.error(f"{error_msg}", exc_info=True)
        stream_logger.error(f"{error_msg}", exc_info=True)
        context.update_step_status("step3", TaskStepStatus.FAILED, error_msg, str(e))
        await report_progress(context.task_id, "STEP3", "FAILED", error_msg)
        return Step3Result(success=False, error_code="VALUE_ERROR", message=error_msg)

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

        if getattr(context, "_xhome_requires_webrtc", False):
            window = StreamWindow(window_title="Bend WebRTC")
            logger.info("xHome WebRTC 模式跳过本机 Xbox 窗口查找")
            stream_logger.info("xHome WebRTC 模式跳过本机 Xbox 窗口查找")
            return window

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

    except asyncio.TimeoutError as e:
        logger.error(f"串流窗口初始化超时: {e}")
        stream_logger.error(f"串流窗口初始化超时: {e}")
        return None
    except ConnectionError as e:
        logger.error(f"串流窗口初始化网络错误: {e}")
        stream_logger.error(f"串流窗口初始化网络错误: {e}")
        return None
    except ValueError as e:
        logger.error(f"串流窗口初始化参数错误: {e}")
        stream_logger.error(f"串流窗口初始化参数错误: {e}")
        return None
    except Exception as e:
        logger.error(f"串流窗口初始化失败: {e}")
        stream_logger.error(f"串流窗口初始化失败: {e}")
        return None


async def _start_sdl_display_pump(context: AgentTaskContext, logger) -> None:
    """保持 SDL 窗口响应：在 step3/就绪等待期间刷新 WebRTC 帧。"""
    existing = getattr(context, "_sdl_display_task", None)
    if existing and not existing.done():
        return

    async def _pump():
        logger.info("SDL 显示泵已启动（就绪阶段也会刷帧）")
        first_frame_logged = False
        while context.sdl_window and context.sdl_window.is_running:
            try:
                # 该循环只负责显示，不做场景决策；Step4 启动后会接管独立的捕获/检测循环。
                if hasattr(context.sdl_window, "process_events"):
                    context.sdl_window.process_events()

                frame_data = None
                capture = context.frame_capture
                if capture is not None:
                    frame = await capture.capture_frame()
                    if frame is not None:
                        frame_data = getattr(frame, "data", frame)
                        if not first_frame_logged:
                            logger.info(
                                "SDL 显示泵首帧: %sx%s",
                                getattr(frame, "width", "?"),
                                getattr(frame, "height", "?"),
                            )
                            first_frame_logged = True
                if frame_data is not None:
                    if hasattr(frame_data, "copy"):
                        frame_data = frame_data.copy()
                    context.sdl_window.update_frame(frame_data)
                await asyncio.sleep(0.033)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.debug("SDL display pump: %s", exc)
                await asyncio.sleep(0.1)
        logger.info("SDL 显示泵已停止")

    context._sdl_display_task = asyncio.create_task(_pump())


async def _stop_sdl_display_pump(context: AgentTaskContext) -> None:
    """Step4 启动自有显示循环前停止 READY 阶段显示泵。"""
    task = getattr(context, "_sdl_display_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    context._sdl_display_task = None


def _wire_sdl_close_handler(context: AgentTaskContext) -> None:
    """将标题栏关闭绑定到 window_close_callback（仅显示层）。"""
    sdl = context.sdl_window
    if not sdl:
        return
    close_cb = getattr(context, "window_close_callback", None)
    if close_cb and hasattr(sdl, "set_close_callback"):
        sdl.set_close_callback(close_cb)
    elif hasattr(sdl, "set_close_callback"):
        sdl.set_close_callback(None)
    keyboard_mapper = getattr(context, "_keyboard_mapper", None)
    if keyboard_mapper and hasattr(keyboard_mapper, "set_window_close_handler"):
        if close_cb:
            keyboard_mapper.set_window_close_handler(None)
        elif hasattr(sdl, "hide"):
            keyboard_mapper.set_window_close_handler(sdl.hide)


async def step3_close_display(context: AgentTaskContext) -> None:
    """销毁 SDL 窗口并停止显示泵；自动化/串流不受影响。"""
    logger = get_logger(f"step3_display_{context.task_id}")
    await _stop_sdl_display_pump(context)
    sdl = getattr(context, "sdl_window", None)
    if sdl:
        try:
            if hasattr(sdl, "destroy"):
                await sdl.destroy()
            elif hasattr(sdl, "close"):
                sdl.close()
        except Exception as exc:
            logger.debug("close display window: %s", exc)
        context.sdl_window = None


def _sdl_window_is_active(sdl: Any) -> bool:
    """SDL 窗口存在且仍在运行（未被用户关闭）时为 True。"""
    if sdl is None:
        return False
    if getattr(sdl, "is_running", False):
        return True
    return bool(getattr(sdl, "_running", False))


async def step3_ensure_display(context: AgentTaskContext) -> bool:
    """
    确保任务的 SDL 窗口可见。

    - 已有活动窗口 → 显示并刷新显示泵（跳过重建）
    - 用户已关闭/销毁 → 基于现有串流上下文重建
    """
    logger = get_logger(f"step3_display_{context.task_id}")
    stream_logger = get_stream_logger(context.streaming_account_email)

    if not context.enable_window_display:
        logger.info("窗口显示已禁用，跳过")
        return False

    if not context.frame_capture and not getattr(context, "_webrtc_frame_controller", None):
        logger.warning("无法显示窗口：frame_capture / WebRTC 未就绪")
        return False

    sdl = context.sdl_window
    if _sdl_window_is_active(sdl):
        logger.info("任务窗口已存在，跳过创建，仅恢复显示")
        if hasattr(sdl, "show"):
            sdl.show()
        _wire_sdl_close_handler(context)
        await _start_sdl_display_pump(context, logger)
        return True

    if sdl is not None:
        context.sdl_window = None

    return await step3_reopen_display(context, logger=logger, stream_logger=stream_logger)


async def step3_reopen_display(
    context: AgentTaskContext,
    logger=None,
    stream_logger=None,
) -> bool:
    """
    基于现有 WebRTC/frame_capture 上下文重新打开 SDL 窗口。

    跳过认证、发现与串流协商。
    """
    logger = logger or get_logger(f"step3_display_{context.task_id}")
    stream_logger = stream_logger or get_stream_logger(context.streaming_account_email)

    if not context.enable_window_display:
        logger.info("窗口显示已禁用，跳过重新打开")
        return False

    if not context.frame_capture and not getattr(context, "_webrtc_frame_controller", None):
        logger.warning("无法重新打开窗口：frame_capture / WebRTC 未就绪")
        return False

    if _sdl_window_is_active(context.sdl_window):
        if hasattr(context.sdl_window, "show"):
            context.sdl_window.show()
        _wire_sdl_close_handler(context)
        await _start_sdl_display_pump(context, logger)
        return True

    sdl_window = await _init_sdl_window(context, logger, stream_logger)
    if not sdl_window:
        return False

    context.sdl_window = sdl_window
    if hasattr(sdl_window, "show"):
        sdl_window.show()
    _wire_sdl_close_handler(context)
    await _start_sdl_display_pump(context, logger)
    return True


async def _init_sdl_window(
    context: AgentTaskContext,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    初始化SDL自绘窗口（优化二）

    功能说明：
    - 创建SDL窗口用于自绘渲染
    - 将GPU解码器集成到SDL窗口
    - 提供高效的帧捕获能力

    参数：
    - context: 任务上下文
    - logger: 日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - SDLStreamWindow或None
    """
    try:
        from ..windows.sdl_window import SDLStreamWindow, SDLWindowConfig, PYGAME_AVAILABLE

        if not PYGAME_AVAILABLE:
            logger.warning("pygame不可用，SDL窗口功能不可用")
            return None

        gpu_type = getattr(context, '_gpu_type', 'cpu')
        gpu_available = getattr(context, '_gpu_available', False)

        logger.info(f"初始化SDL窗口，GPU类型: {gpu_type}")

        from ..core.config import config as app_config
        from ..gssv.network_util import fit_display_size

        account = context.streaming_account_email or "Xbox"
        max_w = int(app_config.get("window.default_width", 1280))
        max_h = int(app_config.get("window.default_height", 720))
        screen_w, screen_h = 1920, 1080
        if sys.platform == "win32":
            try:
                import ctypes
                user32 = ctypes.windll.user32
                screen_w = int(user32.GetSystemMetrics(0))
                screen_h = int(user32.GetSystemMetrics(1))
            except Exception:
                pass

        video_w = int(getattr(context, "stream_width", 0) or max_w)
        video_h = int(getattr(context, "stream_height", 0) or max_h)
        win_w, win_h = fit_display_size(
            screen_w, screen_h, video_w, video_h, max_w=max_w, max_h=max_h
        )

        config = SDLWindowConfig(
            width=win_w,
            height=win_h,
            title=f"Bend Agent - {account} - {context.task_id[:8]}",
            vsync=True,
            double_buffer=True,
            resizable=False,
            hide_on_close=False,
            fit_aspect=True,
        )

        sdl_window = SDLStreamWindow(config)
        success = await sdl_window.initialize(config)

        if not success:
            logger.error("SDL窗口初始化失败")
            return None

        logger.info(f"SDL自绘窗口初始化成功: {config.width}x{config.height}")
        logger.info(f"GPU加速: {'启用' if gpu_available else '禁用'}")

        return sdl_window

    except asyncio.TimeoutError as e:
        logger.warning(f"SDL窗口初始化超时: {e}，将使用窗口截图模式")
        stream_logger.warning(f"SDL窗口初始化超时: {e}")
        return None
    except ConnectionError as e:
        logger.warning(f"SDL窗口初始化网络错误: {e}，将使用窗口截图模式")
        stream_logger.warning(f"SDL窗口初始化失败: {e}")
        return None
    except ValueError as e:
        logger.warning(f"SDL窗口初始化参数错误: {e}，将使用窗口截图模式")
        stream_logger.warning(f"SDL窗口初始化失败: {e}")
        return None
    except Exception as e:
        logger.warning(f"SDL窗口初始化异常: {e}，将使用窗口截图模式")
        stream_logger.warning(f"SDL窗口初始化失败: {e}")
        return None


async def _init_frame_capture(
    context: AgentTaskContext,
    window: Any,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    初始化画面捕获器（支持高性能模式）

    功能说明：
    - 优先使用视频流控制器（RTP模式）
    - 回退到窗口截图模式
    - 提供统一的帧接口

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

        video_capture_mode = getattr(context, '_video_capture_mode', 'fallback')
        video_stream_controller = getattr(context, '_video_stream_controller', None)
        webrtc_frame_controller = getattr(context, '_webrtc_frame_controller', None)
        direct_capture = getattr(context, '_direct_capture', None)
        requires_webrtc = bool(getattr(context, "_xhome_requires_webrtc", False))

        if requires_webrtc:
            if not webrtc_frame_controller:
                logger.error("xHome WebRTC 模式缺少 WebRTC 帧控制器，拒绝降级到窗口截图")
                stream_logger.error("xHome WebRTC 模式缺少 WebRTC 帧控制器")
                return None
            video_capture_mode = "webrtc"
        elif video_capture_mode in ('fallback', 'window') and webrtc_frame_controller:
            video_capture_mode = 'webrtc'

        capture = VideoFrameCapture(window)
        capture.set_video_controller(video_stream_controller)
        capture.set_webrtc_controller(webrtc_frame_controller)
        capture.set_direct_capture(direct_capture)
        capture.set_capture_mode(video_capture_mode)

        context.frame_capture = capture

        fps_info = ""
        if video_capture_mode == "webrtc" and webrtc_frame_controller:
            fps_info = " (WebRTC模式)"
            logger.info(f"画面捕获器已配置为 WebRTC 模式{fps_info}")
            stream_logger.info(f"画面捕获器已配置为 WebRTC 模式{fps_info}")
        elif video_capture_mode == "rtp" and video_stream_controller:
            fps_info = f" (RTP模式)"
            logger.info(f"画面捕获器已配置为RTP模式，支持高帧率显示{fps_info}")
            stream_logger.info(f"画面捕获器已配置为RTP模式{fps_info}")
        elif video_capture_mode == "direct" and direct_capture:
            fps_info = f" (直接捕获模式)"
            logger.info(f"画面捕获器已配置为直接捕获模式{fps_info}")
            stream_logger.info(f"画面捕获器已配置为直接捕获模式{fps_info}")
        else:
            logger.info("画面捕获器已配置为窗口截图模式")
            stream_logger.info("画面捕获器已配置为窗口截图模式")

        frame = await capture.capture_frame()
        if frame:
            prefix = "WebRTC 首帧" if video_capture_mode == "webrtc" else "画面首帧"
            logger.info(f"{prefix}捕获成功，分辨率: {frame.width}x{frame.height}{fps_info}")
            stream_logger.info(f"{prefix}捕获成功，分辨率: {frame.width}x{frame.height}{fps_info}")
        else:
            logger.warning("画面捕获器初始化成功，但无法捕获首帧")
            stream_logger.warning("画面捕获器初始化成功，但无法捕获首帧")
            if requires_webrtc:
                logger.error("WebRTC 首帧 FAILED: xHome 模式拒绝使用窗口截图兜底")
                stream_logger.error("WebRTC 首帧 FAILED: xHome 模式拒绝使用窗口截图兜底")
                return None

        return capture

    except asyncio.TimeoutError as e:
        logger.error(f"初始化画面捕获器超时: {e}")
        stream_logger.error(f"初始化画面捕获器超时: {e}")
        return None
    except ConnectionError as e:
        logger.error(f"初始化画面捕获器网络错误: {e}")
        stream_logger.error(f"初始化画面捕获器网络错误: {e}")
        return None
    except ValueError as e:
        logger.error(f"初始化画面捕获器参数错误: {e}")
        stream_logger.error(f"初始化画面捕获器参数错误: {e}")
        return None
    except Exception as e:
        logger.error(f"初始化画面捕获器失败: {e}")
        stream_logger.error(f"初始化画面捕获器失败: {e}")
        return None


async def _validate_stream_readiness(
    context: AgentTaskContext,
    logger,
    stream_logger,
) -> tuple:
    """
    验证画面捕获与 input 通道就绪，失败时尝试一次重连。
    """
    from ..xbox.stream_keepalive import (
        ensure_input_channel,
        is_input_channel_open,
        send_keepalive,
    )

    async def _check_frames() -> tuple:
        if context.frame_capture is None:
            return False, "画面捕获器未初始化"
        sizes = []
        for _ in range(3):
            frame = await context.frame_capture.capture_frame()
            if frame is None:
                return False, "连续截帧失败"
            sizes.append((frame.width, frame.height))
            await asyncio.sleep(1.0)
        if len(set(sizes)) > 1:
            return False, f"帧分辨率不稳定: {sizes}"
        prefix = "WebRTC 首帧" if getattr(context, "_video_capture_mode", "") == "webrtc" else "首帧"
        return True, f"{prefix}稳定 {sizes[0][0]}x{sizes[0][1]}"

    async def _check_input() -> tuple:
        session = getattr(context, "xbox_session", None)
        if session is None:
            return True, "无 WebRTC 会话，跳过 input 检查"
        if not await ensure_input_channel(session, timeout=10.0):
            return False, "input DataChannel 未 open"
        ok1 = await send_keepalive(session)
        ok2 = await send_keepalive(session)
        if not (ok1 and ok2):
            return False, "input DataChannel keepalive 发送失败"
        state = getattr(session, "input_channel_state", None) or "open"
        return True, f"input DataChannel ready ({state})"

    frames_ok, frames_msg = await _check_frames()
    input_ok, input_msg = await _check_input()
    if frames_ok and input_ok:
        logger.info("STEP3 串流就绪: %s; %s", frames_msg, input_msg)
        stream_logger.info("STEP3 串流就绪: %s; %s", frames_msg, input_msg)
        return True, f"{frames_msg}; {input_msg}"

    logger.warning(
        "STEP3 串流就绪检查 FAILED (%s; %s)，尝试重连 input DataChannel",
        frames_msg,
        input_msg,
    )
    from ..xbox.stream_recovery import reconnect_input_channel, rebind_stream_bindings

    if await reconnect_input_channel(context, logger):
        rebind_stream_bindings(context)
        frames_ok, frames_msg = await _check_frames()
        input_ok, input_msg = await _check_input()
        if frames_ok and input_ok:
            logger.info("STEP3 重连后串流就绪: %s; %s", frames_msg, input_msg)
            return True, f"{frames_msg}; {input_msg}"

    session = getattr(context, "xbox_session", None)
    if session is not None and not is_input_channel_open(session):
        context._input_channel_dirty = True
    return False, f"{frames_msg}; {input_msg}"


def _bind_input_channel_close_handler(context: AgentTaskContext, logger) -> None:
    """注册回调，供 step4 感知 input 通道断开。"""
    session = getattr(context, "_cloud_stream_session", None) or getattr(
        context, "xbox_session", None
    )
    if session is None or not hasattr(session, "on_input_channel_close"):
        return

    def _on_close():
        context._input_channel_dirty = True
        logger.warning("input DataChannel closed，已标记待恢复")

    session.on_input_channel_close(_on_close)
    if hasattr(session, "bind_input_channel_handlers"):
        session.bind_input_channel_handlers()
    logger.info("input DataChannel close 回调已注册")


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

    except asyncio.TimeoutError as e:
        logger.error(f"检测游戏界面超时: {e}")
        stream_logger.error(f"检测游戏界面超时: {e}")
        return False
    except ConnectionError as e:
        logger.error(f"检测游戏界面网络错误: {e}")
        stream_logger.error(f"检测游戏界面网络错误: {e}")
        return False
    except ValueError as e:
        logger.error(f"检测游戏界面参数错误: {e}")
        stream_logger.error(f"检测游戏界面参数错误: {e}")
        return False
    except Exception as e:
        logger.error(f"检测游戏界面失败: {e}")
        stream_logger.error(f"检测游戏界面失败: {e}")
        return False


async def _ensure_controller_protocol(
    context: AgentTaskContext,
    logger,
    stream_logger,
) -> None:
    """即使没有物理手柄也绑定 ControllerProtocol 到云端会话。"""
    if getattr(context, "_controller_protocol", None):
        return

    from ..input.controller_protocol import ControllerProtocol

    protocol = ControllerProtocol()
    if context.xbox_session:
        protocol.set_stream_controller(context.xbox_session)
        channel = "WebRTC DataChannel" if getattr(context, "_cloud_stream_session", None) else "SmartGlass"
        logger.info(f"控制器协议已绑定 Xbox 流会话 ({channel})")
        stream_logger.info(f"控制器协议已绑定 Xbox 流会话 ({channel})")
    else:
        logger.warning("Xbox 流会话未初始化，控制器协议暂无法发送信号")

    context._controller_protocol = protocol
    _bind_input_channel_close_handler(context, logger)


async def _init_gamepad_controller(
    context: AgentTaskContext,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    初始化手柄控制器（参考streaming项目SDL2 GameController）

    功能说明：
    - 使用pygame初始化Xbox手柄
    - 配置手柄输入参数
    - 设置与Xbox流控制器的集成

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - XboxGamepadController或None
    """
    try:
        from ..input.xbox_gamepad import XboxGamepadController
        from ..input.controller_protocol import ControllerProtocol, ControllerSignal

        logger.info("正在初始化手柄控制器...")
        stream_logger.info("正在初始化手柄控制器...")

        gamepad = XboxGamepadController(controller_id=0)
        initialized = await gamepad.initialize()

        if not initialized:
            logger.warning("手柄控制器初始化失败，可能没有连接手柄")
            stream_logger.warning("手柄控制器初始化失败")
            return None

        logger.info(f"手柄已连接: {gamepad.controller_name}")
        stream_logger.info(f"手柄已连接: {gamepad.controller_name}")

        protocol = context._controller_protocol
        if protocol is None:
            await _ensure_controller_protocol(context, logger, stream_logger)
            protocol = context._controller_protocol

        if protocol and context.xbox_session:
            gamepad.set_input_callback(
                lambda sig: protocol.send_signal(ControllerSignal.from_gamepad_signal(sig))
            )
        logger.info("手柄控制器初始化成功")
        stream_logger.info("手柄控制器初始化成功")

        return gamepad

    except asyncio.TimeoutError as e:
        logger.error(f"初始化手柄控制器超时: {e}")
        stream_logger.error(f"初始化手柄控制器超时: {e}")
        return None
    except ConnectionError as e:
        logger.error(f"初始化手柄控制器网络错误: {e}")
        stream_logger.error(f"初始化手柄控制器网络错误: {e}")
        return None
    except ValueError as e:
        logger.error(f"初始化手柄控制器参数错误: {e}")
        stream_logger.error(f"初始化手柄控制器参数错误: {e}")
        return None
    except Exception as e:
        logger.error(f"初始化手柄控制器失败: {e}")
        stream_logger.error(f"初始化手柄控制器失败: {e}")
        return None


async def _init_keyboard_mapper(
    context: AgentTaskContext,
    logger,
    stream_logger
) -> Optional[Any]:
    """
    初始化键盘映射器（参考streaming项目keybinding.csv）

    功能说明：
    - 将键盘按键映射为Xbox手柄动作
    - 支持WASD移动、鼠标视角等
    - 配置映射回调到Xbox控制器

    参数：
    - context: 任务上下文
    - logger: 主日志记录器
    - stream_logger: 流媒体账号日志记录器

    返回：
    - KeyboardMapper或None
    """
    try:
        from ..input.keyboard_mapper import KeyboardMapper
        from ..input.controller_protocol import ControllerProtocol, ControllerSignal
        from ..input.keyboard_mapper import KeyAction

        logger.info("正在初始化键盘映射器...")
        stream_logger.info("正在初始化键盘映射器...")

        keyboard = KeyboardMapper()
        await keyboard.start()

        if hasattr(context, '_controller_protocol') and context._controller_protocol:
            protocol = context._controller_protocol

            def handle_key_action(action: KeyAction, is_pressed: bool):
                try:
                    signal = ControllerSignal()

                    action_map = {
                        KeyAction.TAP_A: (signal.BUTTON_A, 0.1),
                        KeyAction.TAP_B: (signal.BUTTON_B, 0.1),
                        KeyAction.TAP_X: (signal.BUTTON_X, 0.1),
                        KeyAction.TAP_Y: (signal.BUTTON_Y, 0.1),
                        KeyAction.TAP_START: (signal.BUTTON_START, 0.1),
                        KeyAction.TAP_SELECT: (signal.BUTTON_SELECT, 0.1),
                        KeyAction.MOVE_UP: (signal.DPAD_UP, 0),
                        KeyAction.MOVE_DOWN: (signal.DPAD_DOWN, 0),
                        KeyAction.MOVE_LEFT: (signal.DPAD_LEFT, 0),
                        KeyAction.MOVE_RIGHT: (signal.DPAD_RIGHT, 0),
                    }

                    if action in action_map:
                        button_flag, duration = action_map[action]
                        if is_pressed or duration > 0:
                            signal.set_button(button_flag, is_pressed)

                except Exception as e:
                    logger.error(f"处理键盘动作失败: {e}")

            keyboard.register_action_callback(handle_key_action)
            logger.info("键盘映射器已绑定到控制器协议")
        else:
            logger.warning("控制器协议未初始化，键盘映射将无法工作")

        logger.info("键盘映射器初始化成功")
        stream_logger.info("键盘映射器初始化成功")

        return keyboard

    except asyncio.TimeoutError as e:
        logger.error(f"初始化键盘映射器超时: {e}")
        stream_logger.error(f"初始化键盘映射器超时: {e}")
        return None
    except ConnectionError as e:
        logger.error(f"初始化键盘映射器网络错误: {e}")
        stream_logger.error(f"初始化键盘映射器网络错误: {e}")
        return None
    except ValueError as e:
        logger.error(f"初始化键盘映射器参数错误: {e}")
        stream_logger.error(f"初始化键盘映射器参数错误: {e}")
        return None
    except Exception as e:
        logger.error(f"初始化键盘映射器失败: {e}")
        stream_logger.error(f"初始化键盘映射器失败: {e}")
        return None
