"""
SDL 显示泵 — 对齐 streaming WorkerCapture @ frame_fps（默认 30）。

解码帧 (game_mat) 经 SDLStreamWindow.present_frame 刷新；与识别链路解耦。
"""

import asyncio
from typing import Any, Optional

from ..core.config import config as app_config
from ..core.logger import get_logger


class DisplayPump:
    """按 display_fps_max 节流刷新 SDL 窗口；隐藏窗口时仍更新 game_mat。"""

    def __init__(self, context: Any, task_logger=None, fps: Optional[float] = None):
        self._context = context
        self._task_logger = task_logger or get_logger("display_pump")
        max_fps = fps or float(app_config.get("window.display_fps_max", 30))
        self._interval = 1.0 / max(1.0, max_fps)
        self._task: Optional[asyncio.Task] = None
        self._first_frame_logged = False

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._run())
        self._task_logger.info("DisplayPump 已启动 (interval=%.3fs)", self._interval)

    async def stop(self) -> None:
        if not self._task:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        self._task_logger.info("DisplayPump 已停止")

    async def _run(self) -> None:
        while True:
            sdl = getattr(self._context, "sdl_window", None)
            if not sdl or not getattr(sdl, "is_running", False):
                break
            try:
                if hasattr(sdl, "process_events"):
                    sdl.process_events()

                frame_data = None
                capture = getattr(self._context, "frame_capture", None)
                if capture is not None:
                    frame = await capture.capture_frame()
                    if frame is not None:
                        frame_data = getattr(frame, "data", frame)
                        if not self._first_frame_logged:
                            w = getattr(frame, "width", "?")
                            h = getattr(frame, "height", "?")
                            self._task_logger.info("DisplayPump 首帧: %sx%s", w, h)
                            self._first_frame_logged = True

                if frame_data is not None:
                    if hasattr(frame_data, "copy"):
                        frame_data = frame_data.copy()
                    if hasattr(sdl, "present_frame"):
                        sdl.present_frame(frame_data)
                        if hasattr(sdl, "render_display"):
                            sdl.render_display()
                    elif hasattr(sdl, "update_frame"):
                        sdl.update_frame(frame_data)

                await asyncio.sleep(self._interval)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._task_logger.debug("DisplayPump: %s", exc)
                await asyncio.sleep(self._interval)


async def start_display_pump(context: Any, task_logger=None) -> DisplayPump:
    """启动并挂到 context._display_pump。"""
    existing = getattr(context, "_display_pump", None)
    if existing and existing.running:
        return existing
    pump = DisplayPump(context, task_logger=task_logger)
    context._display_pump = pump
    await pump.start()
    return pump


async def stop_display_pump(context: Any) -> None:
    pump = getattr(context, "_display_pump", None)
    if pump:
        await pump.stop()
    context._display_pump = None
