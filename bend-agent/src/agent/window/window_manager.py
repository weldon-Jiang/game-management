"""
StreamingWindowManager — display-only window API (show/hide/focus).

Does not affect AutomationPath (WebRTC → decode → template match → step4).
"""

from typing import Any, Dict, Optional

from ..core.logger import get_logger
from ..windows.task_window_manager import TaskWindowManager


class StreamingWindowManager:
    """Task-scoped display window control; wraps TaskWindowManager."""

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
        wid = self._inner.get_window_id_by_task(task_id)
        if not wid:
            return False
        self._visibility[task_id] = True
        return await self._inner.show_window(wid)

    async def hide_by_task(self, task_id: str) -> bool:
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
        await self._inner.close_window_by_task(task_id)
        self._visibility.pop(task_id, None)

    async def close_all(self) -> None:
        await self._inner.close_all_windows()
        self._visibility.clear()

    async def close_all_windows(self) -> None:
        """Alias for scheduler/legacy callers."""
        await self.close_all()

    def get_window_id_by_task(self, task_id: str) -> Optional[str]:
        return self._inner.get_window_id_by_task(task_id)
