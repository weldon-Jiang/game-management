"""
Step3 显示/输入 helper — SDL 窗口、InputPump、窗口生命周期。

生产 Step3 主流程：step3_xsrp.py（xsrp 栈）/ step3_router（平台分流）。
"""

import asyncio
from typing import Any, Callable, Dict, Optional

from ..core.task_logger import get_task_logger
from ..core.account_logger import get_stream_logger
from ..task.task_context import AgentTaskContext


def _load_window_settings() -> Dict[str, Any]:
    """读取 agent.yaml window.* 与 close_terminates_task 映射。"""
    from ..core.config import config as app_config

    close_terminates = bool(app_config.get("window.close_terminates_task", True))
    title_tpl = str(app_config.get("window.title_template", "{email}"))
    return {
        "width": int(app_config.get("window.default_width", 1280)),
        "height": int(app_config.get("window.default_height", 720)),
        "display_fps_max": float(app_config.get("window.display_fps_max", 30)),
        "fit_aspect": bool(app_config.get("window.fit_aspect", True)),
        "hide_on_close": not close_terminates,
        "close_terminates_task": close_terminates,
        "close_confirm_title": str(
            app_config.get("window.close_confirm_title", "结束串流")
        ),
        "close_confirm_message": str(
            app_config.get(
                "window.close_confirm_message",
                "关闭窗口将结束串流任务和自动化，是否继续？",
            )
        ),
        "title_template": title_tpl,
    }


def _format_window_title(context: AgentTaskContext, template: str) -> str:
    email = context.streaming_account_email or "Xbox"
    try:
        return template.format(email=email, task_id=context.task_id[:8])
    except Exception:
        return email


async def _init_stream_window(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
) -> Optional[Any]:
    """占位 StreamWindow（云端串流不依赖 Xbox App 窗口）。"""
    try:
        from ..windows.stream_window import StreamWindow

        window = StreamWindow(window_title="Bend Stream")
        task_logger.info("云端串流跳过本机 Xbox App 窗口查找")
        stream_logger.info("云端串流跳过本机 Xbox App 窗口查找")
        return window
    except Exception as e:
        task_logger.error(f"串流窗口初始化失败: {e}")
        stream_logger.error(f"串流窗口初始化失败: {e}")
        return None


async def _start_sdl_display_pump(context: AgentTaskContext, task_logger) -> None:
    """保持 SDL 窗口响应：从 StreamRuntime latest_frame 显示，不重复 capture。"""
    existing = getattr(context, "_sdl_display_task", None)
    if existing and not existing.done():
        return

    win_settings = _load_window_settings()
    display_interval = 1.0 / max(1.0, win_settings["display_fps_max"])
    sdl = context.sdl_window
    if sdl is not None and hasattr(sdl, "set_display_fps_max"):
        sdl.set_display_fps_max(win_settings["display_fps_max"])

    async def _pump():
        from ..runtime.stream_runtime import get_or_create_stream_runtime

        runtime = get_or_create_stream_runtime(context)
        task_logger.info(
            "SDL 显示泵已启动（max %sfps，消费 StreamRuntime latest_frame）",
            win_settings["display_fps_max"],
        )
        first_frame_logged = False
        while context.sdl_window and context.sdl_window.is_running:
            try:
                if hasattr(context.sdl_window, "process_events"):
                    context.sdl_window.process_events()

                frame_data = None
                latest = runtime.get_latest_frame()
                if latest is not None:
                    frame_data = getattr(latest, "data", latest)
                    if not first_frame_logged:
                        task_logger.info(
                            "SDL 显示泵首帧: %sx%s",
                            getattr(latest, "width", "?"),
                            getattr(latest, "height", "?"),
                        )
                        first_frame_logged = True
                elif context.frame_capture is not None and not runtime.is_capture_running:
                    frame = await context.frame_capture.capture_frame()
                    if frame is not None:
                        frame_data = getattr(frame, "data", frame)

                if frame_data is not None:
                    if hasattr(frame_data, "copy"):
                        frame_data = frame_data.copy()
                    if hasattr(context.sdl_window, "present_frame"):
                        context.sdl_window.present_frame(frame_data)
                        context.sdl_window.render_display()
                    else:
                        context.sdl_window.update_frame(frame_data)

                await asyncio.sleep(display_interval)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                task_logger.debug("SDL display pump: %s", exc)
                await asyncio.sleep(display_interval)
        task_logger.info("SDL 显示泵已停止")

    context._sdl_display_task = asyncio.create_task(_pump())


async def _start_input_pump_if_ready(context: AgentTaskContext, task_logger) -> None:
    """串流与 input 通道就绪后启动 InputPump（125Hz 焦点 / 8Hz 背景）。"""
    protocol = getattr(context, "_controller_protocol", None)
    if protocol is None or getattr(context, "xbox_session", None) is None:
        return
    from ..input.pump_scheduler import start_input_pump

    await start_input_pump(context, context.task_id, protocol)
    task_logger.info("InputPump 已绑定 task=%s", context.task_id)


async def _stop_sdl_display_pump(context: AgentTaskContext) -> None:
    """停止 READY 阶段 SDL 显示泵。"""
    task = getattr(context, "_sdl_display_task", None)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    context._sdl_display_task = None


def _wire_sdl_close_handler(context: AgentTaskContext) -> None:
    """将标题栏关闭绑定到 window_close_callback（终止任务或仅隐藏显示）。"""
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
            # KeyboardMapper 轮询 pygame 事件比 SDL 显示泵更频繁，须同步关窗回调，
            # 否则 QUIT 被 keyboard 循环吞掉且 handler 为 None，标题栏 X 无效。
            keyboard_mapper.set_window_close_handler(close_cb)
        elif hasattr(sdl, "hide"):
            keyboard_mapper.set_window_close_handler(sdl.hide)
        else:
            keyboard_mapper.set_window_close_handler(None)


async def step3_close_display(context: AgentTaskContext) -> None:
    """销毁 SDL 窗口并停止显示泵；自动化/串流不受影响。"""
    task_logger = get_task_logger(context.task_id)
    from ..input.pump_scheduler import stop_input_pump

    await stop_input_pump(context)
    await _stop_sdl_display_pump(context)
    sdl = getattr(context, "sdl_window", None)
    if sdl:
        try:
            if hasattr(sdl, "destroy"):
                await sdl.destroy()
            elif hasattr(sdl, "close"):
                sdl.close()
        except Exception as exc:
            task_logger.debug("close display window: %s", exc)
        context.sdl_window = None


def _sdl_window_is_active(sdl: Any) -> bool:
    if sdl is None:
        return False
    if getattr(sdl, "is_running", False):
        return True
    return bool(getattr(sdl, "_running", False))


async def step3_ensure_display(context: AgentTaskContext) -> bool:
    """确保 SDL 窗口可见；已有窗口则仅恢复显示泵。"""
    task_logger = get_task_logger(context.task_id)
    stream_logger = get_stream_logger(context.streaming_account_email)

    if not context.enable_window_display:
        task_logger.info("窗口显示已禁用，跳过")
        return False

    if not context.frame_capture:
        task_logger.warning("无法显示窗口：frame_capture 未就绪")
        return False

    sdl = context.sdl_window
    if _sdl_window_is_active(sdl):
        task_logger.info("任务窗口已存在，跳过创建，仅恢复显示")
        if hasattr(sdl, "show"):
            sdl.show()
        _wire_sdl_close_handler(context)
        await _start_sdl_display_pump(context, task_logger)
        return True

    if sdl is not None:
        context.sdl_window = None

    return await step3_reopen_display(context, task_logger=task_logger, stream_logger=stream_logger)


async def step3_reopen_display(
    context: AgentTaskContext,
    task_logger=None,
    stream_logger=None,
) -> bool:
    """基于现有 frame_capture 上下文重新打开 SDL 窗口。"""
    task_logger = task_logger or get_task_logger(context.task_id)
    stream_logger = stream_logger or get_stream_logger(context.streaming_account_email)

    if not context.enable_window_display:
        task_logger.info("窗口显示已禁用，跳过重新打开")
        return False

    if not context.frame_capture:
        task_logger.warning("无法重新打开窗口：frame_capture 未就绪")
        return False

    if _sdl_window_is_active(context.sdl_window):
        if hasattr(context.sdl_window, "show"):
            context.sdl_window.show()
        _wire_sdl_close_handler(context)
        await _start_sdl_display_pump(context, task_logger)
        return True

    sdl_window = await _init_sdl_window(context, task_logger, stream_logger)
    if not sdl_window:
        return False

    context.sdl_window = sdl_window
    if hasattr(sdl_window, "show"):
        sdl_window.show()
    _wire_sdl_close_handler(context)
    await _start_sdl_display_pump(context, task_logger)
    return True


async def _init_sdl_window(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
) -> Optional[Any]:
    """初始化 SDL 自绘窗口。"""
    try:
        from ..windows.sdl_window import SDLStreamWindow, SDLWindowConfig, PYGAME_AVAILABLE

        if not PYGAME_AVAILABLE:
            task_logger.warning("pygame不可用，SDL窗口功能不可用")
            return None

        gpu_type = getattr(context, "_gpu_type", "cpu")
        gpu_available = getattr(context, "_gpu_available", False)
        win_settings = _load_window_settings()

        task_logger.info(f"初始化SDL窗口，GPU类型: {gpu_type}")

        title = _format_window_title(context, win_settings["title_template"])

        config = SDLWindowConfig(
            width=win_settings["width"],
            height=win_settings["height"],
            title=title,
            vsync=True,
            double_buffer=True,
            resizable=False,
            hide_on_close=win_settings["hide_on_close"],
            fit_aspect=win_settings["fit_aspect"],
        )

        sdl_window = SDLStreamWindow(config)
        sdl_window.set_display_fps_max(win_settings["display_fps_max"])
        success = await sdl_window.initialize(config)

        if not success:
            task_logger.error("SDL窗口初始化失败")
            return None

        task_logger.info(f"SDL自绘窗口初始化成功: {config.width}x{config.height}")
        task_logger.info(f"GPU加速: {'启用' if gpu_available else '禁用'}")

        return sdl_window

    except Exception as e:
        task_logger.warning(f"SDL窗口初始化异常: {e}，将使用窗口截图模式")
        stream_logger.warning(f"SDL窗口初始化失败: {e}")
        return None


async def _ensure_controller_protocol(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
) -> None:
    """绑定 ControllerProtocol 到 WebRTC 串流会话（context.xbox_session）。"""
    if getattr(context, "_controller_protocol", None):
        return

    from ..input.controller_protocol import ControllerProtocol

    protocol = ControllerProtocol()
    if context.xbox_session:
        protocol.set_stream_controller(context.xbox_session)
        task_logger.info("控制器协议已绑定串流会话")
        stream_logger.info("控制器协议已绑定串流会话")
    else:
        task_logger.warning("串流会话未初始化，控制器协议暂无法发送信号")

    context._controller_protocol = protocol


async def _init_gamepad_controller(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
) -> Optional[Any]:
    """初始化物理手柄（InputPump 负责 DC 发送）。"""
    try:
        from ..input.xbox_gamepad import XboxGamepadController

        task_logger.info("正在初始化手柄控制器...")
        stream_logger.info("正在初始化手柄控制器...")

        gamepad = XboxGamepadController(controller_id=0)
        initialized = await gamepad.initialize()

        if not initialized:
            task_logger.warning("手柄控制器初始化失败，可能没有连接手柄")
            stream_logger.warning("手柄控制器初始化失败")
            return None

        task_logger.info(f"手柄已连接: {gamepad.controller_name}")
        stream_logger.info(f"手柄已连接: {gamepad.controller_name}")

        if context._controller_protocol is None:
            await _ensure_controller_protocol(context, task_logger, stream_logger)

        task_logger.info("手柄控制器初始化成功（InputPump 负责 DC 发送）")
        stream_logger.info("手柄控制器初始化成功")

        return gamepad

    except Exception as e:
        task_logger.error(f"初始化手柄控制器失败: {e}")
        stream_logger.error(f"初始化手柄控制器失败: {e}")
        return None


async def _init_keyboard_mapper(
    context: AgentTaskContext,
    task_logger,
    stream_logger,
) -> Optional[Any]:
    """初始化键盘映射器（overlay 经 InputPump 发送）。"""
    try:
        from ..input.keyboard_mapper import KeyboardMapper
        from ..input.controller_protocol import ControllerSignal, XboxButtonFlag
        from ..input.keyboard_mapper import KeyAction

        task_logger.info("正在初始化键盘映射器...")
        stream_logger.info("正在初始化键盘映射器...")

        keyboard = KeyboardMapper()
        await keyboard.start()

        if hasattr(context, "_controller_protocol") and context._controller_protocol:
            context._keyboard_overlay_signal = ControllerSignal.zero()

            action_map = {
                KeyAction.TAP_A: XboxButtonFlag.A,
                KeyAction.TAP_B: XboxButtonFlag.B,
                KeyAction.TAP_X: XboxButtonFlag.X,
                KeyAction.TAP_Y: XboxButtonFlag.Y,
                KeyAction.TAP_START: XboxButtonFlag.START,
                KeyAction.TAP_SELECT: XboxButtonFlag.SELECT,
                KeyAction.TAP_L1: XboxButtonFlag.L1,
                KeyAction.TAP_R1: XboxButtonFlag.R1,
                KeyAction.MOVE_UP: XboxButtonFlag.DPAD_UP,
                KeyAction.MOVE_DOWN: XboxButtonFlag.DPAD_DOWN,
                KeyAction.MOVE_LEFT: XboxButtonFlag.DPAD_LEFT,
                KeyAction.MOVE_RIGHT: XboxButtonFlag.DPAD_RIGHT,
            }

            def handle_key_action(action: KeyAction, is_pressed: bool):
                try:
                    flag = action_map.get(action)
                    if flag is None:
                        return
                    overlay = context._keyboard_overlay_signal
                    overlay.set_button(flag, is_pressed)
                except Exception as e:
                    task_logger.error(f"处理键盘动作失败: {e}")

            keyboard.register_action_callback(handle_key_action)
            task_logger.info("键盘映射器已绑定到 InputPump overlay")
        else:
            task_logger.warning("控制器协议未初始化，键盘映射将无法工作")

        task_logger.info("键盘映射器初始化成功")
        stream_logger.info("键盘映射器初始化成功")

        return keyboard

    except Exception as e:
        task_logger.error(f"初始化键盘映射器失败: {e}")
        stream_logger.error(f"初始化键盘映射器失败: {e}")
        return None
