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
        from ..automation.step3_streaming_init import _stop_sdl_display_pump

        await _stop_sdl_display_pump(context)
    except Exception as exc:
        log.debug("stop sdl display pump: %s", exc)

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

    try:
        from ..automation.step2_xbox_streaming import _release_xbox_host

        await _release_xbox_host(context)
    except Exception as exc:
        log.debug("release xbox host: %s", exc)
