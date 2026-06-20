"""Step3 路由：统一走 xblive/xsrp 云端串流环境初始化。"""

from typing import Awaitable, Callable


def resolve_step3_streaming_init() -> Callable[..., Awaitable]:
    from ..automation.step3_xsrp import step3_execute_xsrp_init

    return step3_execute_xsrp_init
