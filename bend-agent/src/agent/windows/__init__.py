"""
Bend Agent Windows模块
======================

功能说明：
- Windows窗口管理
- 串流窗口操作
- SDL自绘窗口（优化二）
- 任务窗口管理

模块结构：
- stream_window: 串流窗口管理
- sdl_window: SDL自绘窗口（优化二）
- task_window_manager: 任务窗口管理器

作者：技术团队
版本：2.0
"""

from .stream_window import StreamWindow, WindowState
from .task_window_manager import TaskWindowManager

try:
    from .sdl_window import (
        SDLStreamWindow,
        SDLWindowState,
        SDLWindowConfig,
        sdl_stream_window,
        PYGAME_AVAILABLE
    )
    SDL_AVAILABLE = PYGAME_AVAILABLE
except ImportError:
    SDL_AVAILABLE = False

__all__ = [
    'StreamWindow',
    'WindowState',
    'TaskWindowManager',
    'SDLStreamWindow',
    'SDLWindowState',
    'SDLWindowConfig',
    'sdl_stream_window',
    'SDL_AVAILABLE'
]