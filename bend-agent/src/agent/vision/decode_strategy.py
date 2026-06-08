"""
GPU 优先解码；并发超限时回退 CPU。
"""

import threading
from typing import Optional

from ..core.config import config
from ..core.logger import get_logger

_logger = get_logger("decode_strategy")
_active_gpu_decodes = 0
_lock = threading.Lock()


def get_max_gpu_decodes() -> int:
    return int(config.get("task.max_concurrent_gpu", config.get("task.max_concurrent", 3)))


def resolve_decode_mode(requested: str = "auto") -> str:
    """
    为新任务选择解码模式。

    - gpu: 强制 GPU
    - cpu: 强制 CPU
    - auto: 未超 GPU 并发上限时用 GPU，否则 CPU
    """
    global _active_gpu_decodes
    requested = (requested or "auto").lower()
    if requested == "cpu":
        return "cpu"
    if requested == "gpu":
        _acquire_gpu()
        return "gpu"

    max_gpu = get_max_gpu_decodes()
    with _lock:
        if _active_gpu_decodes < max_gpu:
            _active_gpu_decodes += 1
            _logger.info(
                "Decode mode: gpu (%s/%s active)",
                _active_gpu_decodes,
                max_gpu,
            )
            return "gpu"
    _logger.info("Decode mode: cpu (GPU slots full %s/%s)", _active_gpu_decodes, max_gpu)
    return "cpu"


def _acquire_gpu() -> None:
    global _active_gpu_decodes
    with _lock:
        _active_gpu_decodes += 1


def release_decode_slot(mode: str) -> None:
    global _active_gpu_decodes
    if (mode or "").lower() != "gpu":
        return
    with _lock:
        _active_gpu_decodes = max(0, _active_gpu_decodes - 1)
