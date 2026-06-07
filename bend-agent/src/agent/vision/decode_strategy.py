"""
GPU-first decode with CPU fallback when concurrent task limit exceeded.
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
    Resolve decode mode for a new task.

    - gpu: force GPU
    - cpu: force CPU
    - auto: GPU if under limit, else CPU
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
