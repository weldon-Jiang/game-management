"""自动化步骤平台分流工具。"""

from ..task.task_context import AgentTaskContext


def account_platform(context: AgentTaskContext) -> str:
    """串流账号平台类型：xbox / playstation（由平台维护，用户自行选择）。"""
    return (getattr(context, "account_platform", None) or "xbox").strip().lower()
