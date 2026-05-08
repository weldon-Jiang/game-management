"""
任务窗口管理器
==============

功能说明：
- 为每个串流账号任务创建独立窗口
- 维护 task_id -> window_id -> window_info 的映射
- 管理窗口生命周期

核心原则：一个任务对应一个窗口，任务完成或失败时窗口必须关闭

作者：技术团队
版本：1.0
"""

import asyncio
import time
from typing import Dict, Optional, List
from dataclasses import dataclass

from ..core.logger import get_logger
from .task_context import AgentTaskContext, WindowInfo


class TaskWindowManager:
    """
    任务窗口管理器

    职责：
    - 为每个串流账号任务创建独立窗口
    - 维护 task_id -> window_id -> window_info 的映射
    - 管理窗口生命周期

    重要原则：
    - 一个任务对应一个窗口
    - 任务完成或失败时，窗口必须关闭
    - 窗口之间相互隔离，独立执行
    """

    def __init__(self, max_concurrent_windows: int = 10):
        """
        初始化窗口管理器

        参数：
        - max_concurrent_windows: 最大并发窗口数
        """
        self.logger = get_logger('task_window_manager')
        self._windows: Dict[str, WindowInfo] = {}
        self._task_to_window: Dict[str, str] = {}
        self._max_concurrent = max_concurrent_windows
        self._semaphore = asyncio.Semaphore(max_concurrent_windows)

    async def create_window_for_task(self, context: AgentTaskContext) -> WindowInfo:
        """
        为任务创建独立窗口

        一个串流账号 = 一个任务 = 一个窗口

        参数：
        - context: 任务上下文

        返回：
        - WindowInfo: 创建的窗口信息
        """
        await self._semaphore.acquire()

        window_id = f"window_{context.task_id}"
        window_info = WindowInfo(
            window_id=window_id,
            streaming_account_id=context.streaming_account_id,
            task_id=context.task_id,
            state="creating",
            created_time=time.time()
        )

        try:
            window_info.window_handle = await self._create_physical_window(window_info)
            window_info.state = "created"

            self._windows[window_id] = window_info
            self._task_to_window[context.task_id] = window_id

            self.logger.info(f"为任务 {context.task_id} 创建窗口 {window_id}")
            return window_info

        except Exception as e:
            self.logger.error(f"创建窗口失败: {e}")
            window_info.state = "failed"
            self._semaphore.release()
            raise

    async def close_window(self, window_id: str):
        """
        关闭指定窗口

        参数：
        - window_id: 窗口ID
        """
        if window_id not in self._windows:
            self.logger.warning(f"窗口不存在: {window_id}")
            return

        window = self._windows[window_id]
        window.state = "closing"

        try:
            await self._close_physical_window(window)
            window.state = "closed"

            task_id = window.task_id
            self._task_to_window.pop(task_id, None)
            self._windows.pop(window_id)

            self._semaphore.release()
            self.logger.info(f"窗口 {window_id} 已关闭")

        except Exception as e:
            self.logger.error(f"关闭窗口失败: {e}")
            window.state = "error"

    async def close_window_by_task(self, task_id: str):
        """
        根据任务ID关闭窗口

        参数：
        - task_id: 任务ID
        """
        window_id = self._task_to_window.get(task_id)
        if window_id:
            await self.close_window(window_id)
        else:
            self.logger.warning(f"任务 {task_id} 没有关联的窗口")

    def get_window_by_task(self, task_id: str) -> Optional[WindowInfo]:
        """
        根据任务ID获取窗口信息

        参数：
        - task_id: 任务ID

        返回：
        - WindowInfo或None
        """
        window_id = self._task_to_window.get(task_id)
        return self._windows.get(window_id) if window_id else None

    def get_all_windows(self) -> List[WindowInfo]:
        """
        获取所有窗口信息

        返回：
        - List[WindowInfo]: 窗口列表
        """
        return list(self._windows.values())

    def get_window_count(self) -> int:
        """获取当前窗口数量"""
        return len(self._windows)

    async def _create_physical_window(self, window_info: WindowInfo) -> int:
        """
        创建物理窗口

        参数：
        - window_info: 窗口信息

        返回：
        - int: 窗口句柄
        """
        try:
            import win32gui
            import win32con
            import win32ui
            from PIL import Image

            window_title = f"BendAgent_{window_info.task_id}"

            wc = win32gui.WNDCLASS()
            wc.lpszClassName = f"BendAgent_Window_{window_info.task_id}"
            wc.lpfnWndProc = win32gui.DefWindowProc

            class_atom = win32gui.RegisterClass(wc)

            hwnd = win32gui.CreateWindow(
                class_atom,
                window_title,
                win32con.WS_OVERLAPPEDWINDOW,
                win32con.CW_USEDEFAULT,
                win32con.CW_USEDEFAULT,
                1280,
                720,
                None,
                None,
                None,
                None
            )

            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
            win32gui.UpdateWindow(hwnd)

            self.logger.info(f"物理窗口已创建: {hwnd}")
            return int(hwnd)

        except ImportError:
            self.logger.warning("win32 API不可用，创建模拟窗口句柄")
            return hash(window_info.window_id) % 1000000
        except Exception as e:
            self.logger.error(f"创建物理窗口失败: {e}")
            raise

    async def _close_physical_window(self, window_info: WindowInfo):
        """
        关闭物理窗口

        参数：
        - window_info: 窗口信息
        """
        if window_info.window_handle is None:
            return

        try:
            import win32gui

            hwnd = window_info.window_handle
            if win32gui.IsWindow(hwnd):
                win32gui.DestroyWindow(hwnd)
                self.logger.info(f"物理窗口已销毁: {hwnd}")

        except ImportError:
            self.logger.warning("win32 API不可用")
        except Exception as e:
            self.logger.error(f"关闭物理窗口失败: {e}")

    async def activate_window(self, task_id: str) -> bool:
        """
        激活指定任务的窗口

        参数：
        - task_id: 任务ID

        返回：
        - bool: 是否成功
        """
        window = self.get_window_by_task(task_id)
        if not window or window.window_handle is None:
            return False

        try:
            import win32gui

            hwnd = window.window_handle
            if win32gui.IsWindow(hwnd):
                win32gui.SetForegroundWindow(hwnd)
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                return True

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"激活窗口失败: {e}")

        return False

    async def close_all_windows(self):
        """关闭所有窗口"""
        window_ids = list(self._windows.keys())
        for window_id in window_ids:
            await self.close_window(window_id)
        self.logger.info("所有窗口已关闭")
