"""
窗口管理包
========
合并原 window/ (管理抽象) + windows/ (具体实现)。

模块:
- window_manager: StreamingWindowManager
- task_window_manager: TaskWindowManager
- stream_window: StreamWindow, WindowState
- sdl_window: SDLStreamWindow, SDLWindowConfig, SDLWindowState
- display_pump: DisplayPump
"""

from .window_manager import StreamingWindowManager
from .task_window_manager import TaskWindowManager
from .stream_window import StreamWindow, WindowState
from .display_pump import DisplayPump

try:
    from .sdl_window import (
        SDLStreamWindow,
        SDLWindowState,
        SDLWindowConfig,
        sdl_stream_window,
        PYGAME_AVAILABLE,
    )
    SDL_AVAILABLE = PYGAME_AVAILABLE
except ImportError:
    SDL_AVAILABLE = False

__all__ = [
    "StreamingWindowManager",
    "TaskWindowManager",
    "StreamWindow",
    "WindowState",
    "DisplayPump",
    "SDLStreamWindow",
    "SDLWindowState",
    "SDLWindowConfig",
    "sdl_stream_window",
    "SDL_AVAILABLE",
]
