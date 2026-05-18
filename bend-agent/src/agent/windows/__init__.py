"""
Bend Agent Windows模块
======================

功能说明：
- Windows窗口管理
- 串流窗口操作
- 任务窗口管理

模块结构：
- stream_window: 串流窗口管理
- task_window_manager: 任务窗口管理器

作者：技术团队
版本：1.0
"""

from .stream_window import StreamWindow, WindowState
from .task_window_manager import TaskWindowManager

__all__ = ['StreamWindow', 'WindowState', 'TaskWindowManager']