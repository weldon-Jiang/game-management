"""PlayStation LAN 串流管道诊断。"""

from typing import Any, Dict

from ..task.task_context import AgentTaskContext


def pipeline_diagnostic_from_context(context: AgentTaskContext) -> Dict[str, Any]:
    """PlayStation Step2 诊断（串流未开放阶段仅反映发现/匹配）。"""
    console = context.current_xbox
    return {
        "auth": "pending",
        "discovery": "ok" if console else "pending",
        "firstFrame": "pending",
        "inputDc": "pending",
        "streamMode": "lan",
        "platform": "playstation",
        "lanIp": getattr(console, "ip_address", None) if console else None,
        "chiakiConnect": "pending",
    }
