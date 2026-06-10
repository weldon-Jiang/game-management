"""Step1 认证路由：xblive（默认）或 legacy MSAL。"""

from typing import Awaitable, Callable


def resolve_step1_execute_login() -> Callable[..., Awaitable]:
    from ..core.config import get_config

    provider = (getattr(get_config().auth, "PROVIDER", "xblive") or "xblive").lower()
    if provider == "msal":
        from ..automation.step1_stream_account_login import step1_execute_login

        return step1_execute_login
    from ..automation.step1_xblive_login import step1_execute_login

    return step1_execute_login
