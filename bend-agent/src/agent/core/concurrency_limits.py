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
