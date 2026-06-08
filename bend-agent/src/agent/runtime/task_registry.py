"""
TaskRuntimeRegistry — 按 taskId 查找运行时以实现并行任务隔离。

所有 WS task_control 须经本注册表解析；缺失或未知 taskId 将被拒绝。
"""

import asyncio
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from ..core.logger import get_logger
from ..task.task_context import AgentTaskContext, AutomationResult
from .phase_fsm import PauseMode, PhaseFSM, SessionPhase


@dataclass
class StreamingAccountTaskRuntime:
    """绑定一个串流账号与一个 taskId 的每任务运行时包。"""

    task_id: str
    context: AgentTaskContext
    phase_fsm: PhaseFSM = field(default_factory=PhaseFSM)
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    pause_mode: Optional[PauseMode] = None
    pause_after_match: bool = False
    phase_before_pause: Optional[SessionPhase] = None
    window_visible: bool = True
    session_id: Optional[str] = None
    modules: Dict[str, Any] = field(default_factory=dict)
    asyncio_task: Optional[asyncio.Task] = None
    task_object: Optional[Any] = None
    on_phase_change: Optional[Callable[[SessionPhase, str], Any]] = None

    def set_phase(
        self,
        phase: SessionPhase,
        message: str = "",
    ) -> SessionPhase:
        """
        应用经校验的阶段迁移并通知平台监听器。

        非法迁移记录日志并忽略，避免 stray WS 控制消息崩溃任务协程。
        """
        if not self.phase_fsm.can_transition(phase):
            get_logger("task_registry").warning(
                "Ignored invalid phase transition: %s -> %s (%s)",
                self.phase_fsm.phase.value,
                phase.value,
                message,
            )
            return self.phase_fsm.phase
        self.phase_fsm.transition(phase)
        if self.on_phase_change:
            result = self.on_phase_change(phase, message)
            if asyncio.iscoroutine(result):
                asyncio.create_task(result)
        return phase


class TaskRuntimeRegistry:
    """
    全局注册表：taskId -> StreamingAccountTaskRuntime。

    线程安全，供 WS 处理器与调度器协程查找。
    """

    _instance: Optional["TaskRuntimeRegistry"] = None

    def __init__(self):
        self.logger = get_logger("task_registry")
        self._runtimes: Dict[str, StreamingAccountTaskRuntime] = {}
        self._lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "TaskRuntimeRegistry":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(self, runtime: StreamingAccountTaskRuntime, replace: bool = False) -> None:
        """
        绑定 taskId 与运行时包。

        replace=True 用于平台复用长寿命 taskId，Agent 须在重跑 Step1-3 前
        丢弃陈旧运行时状态。
        """
        with self._lock:
            if runtime.task_id in self._runtimes:
                if not replace:
                    raise ValueError(f"Task {runtime.task_id} already registered")
                self._runtimes.pop(runtime.task_id, None)
            self._runtimes[runtime.task_id] = runtime
            self.logger.info("Registered task runtime: %s", runtime.task_id)

    def unregister(self, task_id: str) -> Optional[StreamingAccountTaskRuntime]:
        with self._lock:
            runtime = self._runtimes.pop(task_id, None)
            if runtime:
                self.logger.info("Unregistered task runtime: %s", task_id)
            return runtime

    def get(self, task_id: str) -> Optional[StreamingAccountTaskRuntime]:
        if not task_id:
            return None
        with self._lock:
            return self._runtimes.get(task_id)

    def require(self, task_id: str) -> StreamingAccountTaskRuntime:
        runtime = self.get(task_id)
        if runtime is None:
            raise KeyError(f"Unknown taskId: {task_id}")
        return runtime

    def list_active_task_ids(self) -> List[str]:
        with self._lock:
            return list(self._runtimes.keys())

    def count(self) -> int:
        with self._lock:
            return len(self._runtimes)

    def get_context(self, task_id: str) -> Optional[AgentTaskContext]:
        runtime = self.get(task_id)
        return runtime.context if runtime else None

    def set_result(self, task_id: str, result: AutomationResult) -> None:
        runtime = self.get(task_id)
        if runtime:
            runtime.modules["_result"] = result

    def get_result(self, task_id: str) -> Optional[AutomationResult]:
        runtime = self.get(task_id)
        if runtime:
            return runtime.modules.get("_result")
        return None
