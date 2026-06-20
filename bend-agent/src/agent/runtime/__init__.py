"""Agent 运行时：任务注册表、阶段 FSM、输入焦点、串流运行时。"""

from .stream_runtime import StreamRuntime, get_or_create_stream_runtime

__all__ = [
    "StreamRuntime",
    "get_or_create_stream_runtime",
    "capture_task_frame",
]
