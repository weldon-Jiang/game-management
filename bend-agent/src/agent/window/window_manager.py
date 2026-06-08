"""
StreamingWindowManager — 仅显示层窗口 API（show/hide/focus）。

不影响自动化链路（WebRTC → 解码 → 模板匹配 → step4）。
"""

from typing import Any, Dict, Optional

from ..core.logger import get_logger
from ..windows.task_window_manager import TaskWindowManager


class StreamingWindowManager:
    """
    任务级 SDL 显示窗口控制（show/hide/focus），不影响自动化截帧链路。

    由 task_control WS 触发；窗口生命周期与 TaskWindowManager 绑定。
    """

    def __init__(self, max_concurrent: int = 10):
        self.logger = get_logger("streaming_window_manager")
        self._inner = TaskWindowManager(max_concurrent_windows=max_concurrent)
        self._visibility: Dict[str, bool] = {}

    @property
    def inner(self) -> TaskWindowManager:
        return self._inner

    async def create_for_context(self, context: Any) -> Any:
        info = await self._inner.create_window_for_task(context)
        self._visibility[context.task_id] = True
        return info

    async def show_by_task(self, task_id: str) -> bool:
        """task_control window_show：恢复任务窗口可见性。"""
        wid = self._inner.get_window_id_by_task(task_id)
        if not wid:
            return False
        self._visibility[task_id] = True
        return await self._inner.show_window(wid)

    async def hide_by_task(self, task_id: str) -> bool:
        """task_control window_hide：隐藏窗口但不释放解码资源。"""
        wid = self._inner.get_window_id_by_task(task_id)
        if not wid:
            return False
        self._visibility[task_id] = False
        return await self._inner.hide_window(wid)

    async def focus_by_task(self, task_id: str) -> bool:
        wid = self._inner.get_window_id_by_task(task_id)
        if not wid:
            return False
        return await self._inner.focus_window(wid)

    def is_visible(self, task_id: str) -> bool:
        return self._visibility.get(task_id, True)

    async def destroy_by_task(self, task_id: str) -> None:
        """任务终止/取消时关闭窗口并释放 GPU 解码槽。"""
        await self._inner.close_window_by_task(task_id)
        self._visibility.pop(task_id, None)

    async def close_all(self) -> None:
        await self._inner.close_all_windows()
        self._visibility.clear()

    async def close_all_windows(self) -> None:
        """供调度器/遗留调用方的别名。"""
        await self.close_all()

    def get_window_id_by_task(self, task_id: str) -> Optional[str]:
        return self._inner.get_window_id_by_task(task_id)
