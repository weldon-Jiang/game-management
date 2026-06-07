"""
InputFocusManager — physical input isolation across parallel tasks.

Only the stack-top task receives physical gamepad/keyboard hooks.
Automation virtual input via DataChannel is unaffected.
"""

import threading
from typing import List, Optional

from ..core.logger import get_logger


class InputFocusManager:
    """Maintains a focus stack; top taskId owns physical input routing."""

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
        with self._lock:
            if task_id in self._stack:
                self._stack.remove(task_id)
            self._stack.append(task_id)
            self._focused_task_id = task_id
            self.logger.info("Input focus pushed: %s (stack=%s)", task_id, self._stack)

    def pop(self, task_id: str) -> None:
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
        return self.is_focused(task_id)
