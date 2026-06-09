"""
Chiaki 注册与会话握手（占位）。

后续实现：
- PS4/PS5 Remote Play 注册（9295）
- Takion 会话建立
- PIN / regist key 与平台 credential 对接

当前 Step2 在匹配成功后返回 PS_STREAM_NOT_SUPPORTED，不调用本模块。
"""

from dataclasses import dataclass
from typing import Optional

from ..task.task_context import AgentTaskContext


@dataclass
class ChiakiConnectResult:
    """Chiaki 连接结果（占位）。"""

    success: bool
    message: str = ""
    error_code: str = "PS_STREAM_NOT_IMPLEMENTED"


async def connect_playstation_lan(
    context: AgentTaskContext,
    *,
    device_id: str,
    ip_address: str,
    port: int = 9295,
) -> ChiakiConnectResult:
    """
    建立 PlayStation LAN 串流会话（未实现）。

    参数:
        context: 任务上下文
        device_id: Chiaki host-id
        ip_address: 主机 LAN IP
        port: host-request-port，默认 9295
    """
    _ = (context, device_id, ip_address, port)
    return ChiakiConnectResult(
        success=False,
        message="PlayStation 串流握手尚未实现",
        error_code="PS_STREAM_NOT_IMPLEMENTED",
    )


async def disconnect_playstation_session(context: AgentTaskContext) -> None:
    """释放 PS 串流会话资源（占位）。"""
    session = getattr(context, "ps_session", None)
    if session is not None:
        context.ps_session = None  # type: ignore[attr-defined]
