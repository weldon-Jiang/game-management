"""Agent 进程关闭标志，供后台重连/时间线上报等跳过 shutdown 期间工作。"""

_shutting_down = False


def mark_agent_shutting_down() -> None:
    global _shutting_down
    _shutting_down = True


def is_agent_shutting_down() -> bool:
    return _shutting_down
