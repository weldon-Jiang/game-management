"""
InputFocusManager — 并行任务间的物理输入隔离。

仅栈顶任务接收物理手柄/键盘钩子；经 DataChannel 的自动化虚拟输入不受影响。
"""

import threading
from typing import List, Optional

from ..core.logger import get_logger


class InputFocusManager:
    """维护焦点栈；栈顶 taskId 拥有物理输入路由。"""

    _instance: Optional["InputFocusManager"] = None

    def __init__(self):
        self.logger = get_logger("input_focus")
        self._stack: List[str] = []
        self._lock = threading.Lock()
        self._focused_task_id: Optional[str] = None

    @classmethod
    def get_instance(cls) -> "InputFocusManager":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def push(self, task_id: str) -> None:
        """任务启动时入栈，栈顶任务获得物理手柄/键盘路由。"""
        with self._lock:
            if task_id in self._stack:
                self._stack.remove(task_id)
            self._stack.append(task_id)
            self._focused_task_id = task_id
            self.logger.info("Input focus pushed: %s (stack=%s)", task_id, self._stack)

    def pop(self, task_id: str) -> None:
        """任务结束出栈，焦点回落到上一任务或 None。"""
        with self._lock:
            if task_id in self._stack:
                self._stack.remove(task_id)
            self._focused_task_id = self._stack[-1] if self._stack else None
            self.logger.info(
                "Input focus popped: %s (focused=%s)",
                task_id,
                self._focused_task_id,
            )

    def focus(self, task_id: str) -> bool:
        """task_control focus_window：将已有任务提升至栈顶（须已在栈内）。"""
        with self._lock:
            if task_id not in self._stack:
                self.logger.warning("focus(%s): task not in stack", task_id)
                return False
            self._stack.remove(task_id)
            self._stack.append(task_id)
            self._focused_task_id = task_id
            self.logger.info("Input focus set: %s", task_id)
            return True

    def is_focused(self, task_id: str) -> bool:
        with self._lock:
            return self._focused_task_id == task_id

    def get_focused_task_id(self) -> Optional[str]:
        with self._lock:
            return self._focused_task_id

    def should_accept_physical_input(self, task_id: str) -> bool:
        """物理输入钩子入口：仅栈顶 taskId 返回 True（DataChannel 自动化不受此限）。"""
        return self.is_focused(task_id)
