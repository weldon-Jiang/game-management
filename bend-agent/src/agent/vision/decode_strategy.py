"""
GPU 优先解码；可选并发上限，超出时 auto 模式回退 CPU。

task.max_concurrent_gpu 语义：
- 0 或未配置：不限制 GPU 路数（压测默认）
- >0：最多 N 路 GPU，满额后 auto 降级 CPU
"""

import threading

from ..core.config import config
from ..core.logger import get_logger

_logger = get_logger("decode_strategy")
_active_gpu_decodes = 0
_lock = threading.Lock()


def get_max_gpu_decodes() -> int:
    """返回 GPU 解码槽上限；0 表示不限制。"""
    raw = config.get("task.max_concurrent_gpu", 0)
    if raw is None:
        return 0
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 0


def resolve_decode_mode(requested: str = "auto") -> str:
    """
    为新任务选择解码模式。

    - gpu: 强制 GPU
    - cpu: 强制 CPU
    - auto: 未超 GPU 并发上限时用 GPU，否则 CPU（上限为 0 时不降级）
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
        if max_gpu <= 0 or _active_gpu_decodes < max_gpu:
            _active_gpu_decodes += 1
            if max_gpu <= 0:
                _logger.info(
                    "Decode mode: gpu (%s active, unlimited)",
                    _active_gpu_decodes,
                )
            else:
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
