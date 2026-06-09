"""
任务工厂 - 可选扩展点

生产环境任务由 task_executor.handle_stream_control → AutomationScheduler
→ StreamingAccountTask 调度，不经过本工厂。
"""
from typing import Dict, Any, Optional, Callable

from .base_task import BaseAutomationTask
from .platform_api_client import PlatformApiClient


class TaskFactory:
    """根据任务类型创建 BaseAutomationTask 子类实例（可选）。"""

    _task_registry: Dict[str, Callable] = {}

    @classmethod
    def register_task(cls, task_type: str, task_class: Callable):
        cls._task_registry[task_type] = task_class

    @classmethod
    def create_task(
        cls,
        task_type: str,
        task_id: str,
        params: Dict[str, Any],
        platform_client: Optional[PlatformApiClient] = None,
    ) -> BaseAutomationTask:
        if task_type not in cls._task_registry:
            raise ValueError(
                f"未知的任务类型: {task_type}。"
                f"stream_control/xbox_automation 请使用 task_executor 内置路径。"
            )
        task_class = cls._task_registry[task_type]
        return task_class(task_id, params, platform_client)

    @classmethod
    def get_registered_types(cls) -> list:
        return list(cls._task_registry.keys())
