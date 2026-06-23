"""
任务级并发上限解析。

压测阶段约定：配置值 <= 0 表示不限制，内部映射为大槽位供 Semaphore 使用。
实测稳定后可在 agent.yaml 写入具体正整数。
"""

PRESSURE_TEST_UNLIMITED_SLOTS = 65535


def resolve_concurrency_limit(raw, default: int = 0) -> int:
    """解析 task.max_concurrent 等；0/未配置/非法 → 不限制。"""
    if raw is None:
        value = default
    else:
        try:
            value = int(raw)
        except (TypeError, ValueError):
            value = default
    if value <= 0:
        return PRESSURE_TEST_UNLIMITED_SLOTS
    return value


def get_task_min_concurrent() -> int:
    from ..core.config import config

    raw = config.get("task.min_concurrent", 20)
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 20


def get_task_capacity_cap() -> int:
    """0 = 不封顶（仅硬件测算约束）。"""
    from ..core.config import config

    raw = config.get("task.capacity_cap", 50)
    try:
        return max(0, int(raw))
    except (TypeError, ValueError):
        return 50


def resolve_declared_capacity_from_config() -> int:
    """按 agent.yaml 与当前硬件计算注册/上报用 declared_capacity。"""
    from ..vision.decode_strategy import get_max_gpu_decodes
    from .streaming_capacity import CapacityInputs, resolve_declared_capacity
    from .system_resource_detector import SystemResourceDetector

    total_mem_mb, _ = SystemResourceDetector.get_memory_info()
    inputs = CapacityInputs(
        cpu_count=SystemResourceDetector.get_cpu_count(),
        total_memory_mb=total_mem_mb,
        max_gpu_slots=get_max_gpu_decodes(),
    )
    return resolve_declared_capacity(
        inputs,
        min_concurrent=get_task_min_concurrent(),
        capacity_cap=get_task_capacity_cap(),
    )
