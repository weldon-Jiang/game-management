"""xHome 媒体上下文共用的清理辅助函数。"""

from typing import Any

from ..core.logger import get_logger


async def close_media_context(context: Any, logger=None) -> None:
    """释放显示、截帧、SmartGlass 会话、input 与主机锁。"""
    log = logger or get_logger("xhome_cleanup")
    if context is None:
        return

    try:
        from ..input.pump_scheduler import stop_input_pump

        await stop_input_pump(context)
    except Exception as exc:
        log.debug("stop input pump: %s", exc)

    try:
        from ..automation.step3.display_helpers import _stop_sdl_display_pump

        await _stop_sdl_display_pump(context)
    except Exception as exc:
        log.debug("stop sdl display pump: %s", exc)

    try:
        from ..runtime.stream_runtime import get_or_create_stream_runtime

        runtime = getattr(context, "_stream_runtime", None)
        if runtime is not None:
            await runtime.stop_long_lived()
            context._stream_runtime = None
    except Exception as exc:
        log.debug("stop stream runtime: %s", exc)

    sdl = getattr(context, "sdl_window", None)
    if sdl:
        try:
            if hasattr(sdl, "destroy"):
                await sdl.destroy()
            elif hasattr(sdl, "close"):
                sdl.close()
        except Exception as exc:
            log.debug("destroy sdl window: %s", exc)
        context.sdl_window = None

    keyboard = getattr(context, "_keyboard_mapper", None)
    if keyboard and hasattr(keyboard, "stop"):
        try:
            await keyboard.stop()
        except Exception as exc:
            log.debug("stop keyboard mapper: %s", exc)
        context._keyboard_mapper = None

    gamepad = getattr(context, "_gamepad_controller", None)
    if gamepad:
        try:
            if hasattr(gamepad, "stop"):
                await gamepad.stop()
            elif hasattr(gamepad, "close"):
                result = gamepad.close()
                if hasattr(result, "__await__"):
                    await result
        except Exception as exc:
            log.debug("stop gamepad controller: %s", exc)
        context._gamepad_controller = None

    capture = getattr(context, "frame_capture", None)
    if capture and hasattr(capture, "close"):
        try:
            await capture.close()
        except Exception as exc:
            log.debug("close frame capture: %s", exc)
    context.frame_capture = None

    session = getattr(context, "xbox_session", None)
    if session and hasattr(session, "disconnect"):
        try:
            await session.disconnect()
        except Exception as exc:
            log.debug("disconnect xbox session: %s", exc)
    context.xbox_session = None

    stack = getattr(context, "_streaming_stack", "")
    if stack == "xsrp":
        try:
            from ..xbox.xsrp_cleanup import cleanup_xsrp_stream_context

            await cleanup_xsrp_stream_context(context, log)
        except Exception as exc:
            log.debug("xsrp stream cleanup: %s", exc)

    try:
        from ..xbox.console_lease import release_xbox_host

        await release_xbox_host(context)
    except Exception as exc:
        log.debug("release xbox host: %s", exc)
