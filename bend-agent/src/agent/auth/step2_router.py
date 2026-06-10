"""Step2 路由：统一走 xblive/xsrp 云端 GSSV 串流。"""

from typing import Awaitable, Callable


def resolve_step2_execute_streaming() -> Callable[..., Awaitable]:
    from ..automation.step2_xsrp import step2_execute_xsrp_streaming

    return step2_execute_xsrp_streaming
