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
            logger.info("键盘映射器初始化成功，已保存到上下文供步骤四使用")
            stream_logger.info("键盘映射器初始化成功")
        else:
            logger.warning("键盘映射器初始化失败")
            stream_logger.warning("键盘映射器初始化失败")

        if check_cancel():
            return Step3Result(success=False, error_code="CANCELLED", message="任务被取消")

        context.update_step_status("step3", TaskStepStatus.RUNNING, "正在检测游戏界面...")
        await report_progress(context.task_id, "STEP3", "RUNNING", "正在检测游戏界面...")

        game_ready = await _detect_game_screen(context, window, logger, stream_logger)
        if not game_ready:
            logger.warning("游戏界面检测未完成，但继续执行")

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
                "sdlWindowEnabled": hasattr(context, '_sdl_window') and context._sdl_window is not None
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

        sdl_window = await _init_sdl_window(context, logger, stream_logger)
        if sdl_window:
            context._sdl_window = sdl_window
            logger.info("SDL自绘窗口初始化成功，已保存到上下文供步骤四使用")
            stream_logger.info("SDL自绘窗口初始化成功")
        else:
            logger.warning("SDL窗口初始化失败，将使用窗口截图模式")

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

        config = SDLWindowConfig(
            width=1280,
            height=720,
            title="Bend Agent - Xbox Streaming",
            vsync=True,
            double_buffer=True
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
        direct_capture = getattr(context, '_direct_capture', None)

        capture = VideoFrameCapture(window)
        capture.set_video_controller(video_stream_controller)
        capture.set_direct_capture(direct_capture)
        capture.set_capture_mode(video_capture_mode)

        context.frame_capture = capture

        fps_info = ""
        if video_capture_mode == "rtp" and video_stream_controller:
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
            logger.info(f"画面捕获器初始化成功，分辨率: {frame.width}x{frame.height}{fps_info}")
            stream_logger.info(f"画面捕获器初始化成功，分辨率: {frame.width}x{frame.height}{fps_info}")
        else:
            logger.warning("画面捕获器初始化成功，但无法捕获首帧")
            stream_logger.warning("画面捕获器初始化成功，但无法捕获首帧")

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
        from ..input.controller_protocol import ControllerProtocol

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

        protocol = ControllerProtocol()

        if context.xbox_session:
            protocol.set_stream_controller(context.xbox_session)
            gamepad.set_input_callback(lambda sig: protocol.send_signal(
                ControllerProtocol.from_gamepad_signal(sig) if hasattr(ControllerProtocol, 'from_gamepad_signal') else sig
            ))
            logger.info("手柄控制器已绑定到Xbox流会话")
        else:
            logger.warning("Xbox流会话未初始化，手柄信号将无法发送")

        context._controller_protocol = protocol
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
