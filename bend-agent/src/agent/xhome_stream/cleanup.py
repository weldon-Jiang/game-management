"""Shared cleanup helpers for xHome media contexts."""

from typing import Any

from ..core.logger import get_logger


async def close_media_context(context: Any, logger=None) -> None:
    """Release display, capture, WebRTC, PlaySession, input, and host locks."""
    log = logger or get_logger("xhome_cleanup")
    if context is None:
        return

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

    cloud = getattr(context, "_cloud_stream_session", None) or getattr(
        context, "xbox_session", None
    )
    if cloud and hasattr(cloud, "disconnect"):
        try:
            await cloud.disconnect()
        except Exception as exc:
            log.debug("disconnect cloud session: %s", exc)
    context._cloud_stream_session = None
    context.xbox_session = None

    play_mgr = getattr(context, "_play_session_manager", None)
    if play_mgr and hasattr(play_mgr, "close"):
        try:
            await play_mgr.close()
        except Exception as exc:
            log.debug("close play session: %s", exc)
    context._play_session_manager = None

    try:
        from ..automation.step2_xbox_streaming import _release_xbox_host

        await _release_xbox_host(context)
    except Exception as exc:
        log.debug("release xbox host: %s", exc)
