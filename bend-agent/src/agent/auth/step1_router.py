"""Step1 认证路由：生产仅 xblive（MSAL 已移出热路径，见 scripts/debug）。"""

from typing import Awaitable, Callable

from ..core.logger import get_logger


def resolve_step1_execute_login() -> Callable[..., Awaitable]:
    from ..core.config import get_config

    logger = get_logger("step1_router")
    provider = (getattr(get_config().auth, "PROVIDER", "xblive") or "xblive").lower()
    if provider == "msal":
        logger.warning(
            "auth.provider=msal 已废弃，生产热路径固定 xblive；"
            "MSAL 调试请用 scripts/debug/*"
        )
    from ..automation.step1_xblive_login import step1_execute_login

    return step1_execute_login
