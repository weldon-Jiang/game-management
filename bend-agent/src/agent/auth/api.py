"""
AuthService — 串流基础设施的分级令牌链。

封装现有 MSAL 认证；session/discovery/stream 仅消费 StreamingCredentials。
"""

from dataclasses import dataclass, field
from typing import Any, Callable, List, Optional

from ..core.logger import get_logger


@dataclass
class StreamingCredentials:
    streaming_account_id: str
    email: str
    password: str
    auto_code: str = ""
    microsoft_tokens: Optional[Any] = None
    xbox_tokens: Optional[Any] = None
    gs_token: str = ""
    gssv_base_uri: str = ""
    gssv_xsts_token: str = ""
    web_xsts_token: str = ""
    user_hash: str = ""
    gs_token_expires_at: float = 0.0
    prefetched_consoles: List[Any] = field(default_factory=list)


class AuthService:
    """认证串流账号并产出令牌包。"""

    def __init__(self):
        self.logger = get_logger("auth_service")
        self._cache: dict = {}

    def get_cached_credentials(self, email: str) -> Optional[StreamingCredentials]:
        return self._cache.get(email.lower())

    async def refresh_if_needed(self, email: str) -> Optional[StreamingCredentials]:
        """凭证仍有效则返回缓存；否则重新认证。"""
        cached = self.get_cached_credentials(email)
        if cached and cached.gs_token:
            return cached
        if cached:
            return await self.authenticate(
                email=cached.email,
                password=cached.password,
                auto_code=cached.auto_code,
                streaming_account_id=cached.streaming_account_id,
            )
        return None

    async def authenticate(
        self,
        email: str,
        password: str,
        auto_code: str = "",
        streaming_account_id: str = "",
        task_id: str = "",
        check_cancel: Optional[Callable[[], bool]] = None,
        report_progress: Optional[Callable] = None,
    ) -> StreamingCredentials:
        from ..auth.step1_router import resolve_step1_execute_login
        from ..task.task_context import AgentTaskContext, TaskStepStatus

        step1_execute_login = resolve_step1_execute_login()

        effective_task_id = task_id or f"auth_{streaming_account_id or email}"
        context = AgentTaskContext(
            task_id=effective_task_id,
            streaming_account_id=streaming_account_id,
            streaming_account_email=email,
            streaming_account_password=password,
            streaming_account_auto_code=auto_code,
        )

        async def _report(*args, **kwargs):
            if report_progress:
                result = report_progress(*args, **kwargs)
                if hasattr(result, "__await__"):
                    await result

        result = await step1_execute_login(
            context,
            check_cancel or (lambda: False),
            _report,
        )
        if not result.success:
            raise RuntimeError(result.message or "Authentication failed")

        creds = StreamingCredentials(
            streaming_account_id=streaming_account_id,
            email=email,
            password=password,
            auto_code=auto_code,
            microsoft_tokens=result.microsoft_tokens,
            xbox_tokens=result.xbox_tokens,
        )
        xbox_tokens = result.xbox_tokens
        if xbox_tokens:
            creds.gs_token = getattr(xbox_tokens, "access_token", "") or getattr(
                xbox_tokens, "gs_token", ""
            )
            creds.gssv_base_uri = getattr(xbox_tokens, "gssv_base_uri", "") or getattr(
                xbox_tokens, "base_uri", ""
            )
            creds.gssv_xsts_token = getattr(xbox_tokens, "xsts_token", "")
            creds.web_xsts_token = getattr(xbox_tokens, "web_xsts_token", "")
            creds.user_hash = getattr(xbox_tokens, "user_hash", "")
            sid = getattr(xbox_tokens, "server_id", "")
            pp = getattr(xbox_tokens, "play_path", "")
            if sid and pp:
                creds.prefetched_consoles = [{"serverId": sid, "playPath": pp}]
        self._cache[email.lower()] = creds
        return creds
