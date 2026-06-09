"""PlayStation 主机信息 → task_context 映射（复用 XboxInfo 字段承载 console 目标）。"""

from ..task.task_context import XboxInfo
from .models import PlayStationConsole


def ps_console_to_task_context(
    console: PlayStationConsole,
    platform_host_id: str = "",
) -> XboxInfo:
    """将 PS 发现结果写入 context.current_xbox / assigned_xbox。"""
    return XboxInfo(
        id=console.device_id,
        platform_host_id=platform_host_id,
        name=console.name,
        ip_address=console.ip_address,
        live_id=console.device_id,
        power_state=console.power_state,
        console_type=console.console_type,
    )
