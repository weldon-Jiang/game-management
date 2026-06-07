"""
StreamingSession — orchestrates auth → discovery → xhome_stream ready chain.
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from ..auth.api import AuthService, StreamingCredentials
from ..core.logger import get_logger
from ..discovery.api import DiscoveryService
from ..discovery.models import ConsoleTarget
from ..runtime.phase_fsm import SessionPhase
from ..xhome_stream.api import MediaSession, XHomeStreamService


@dataclass
class SessionOpenResult:
    success: bool
    credentials: Optional[StreamingCredentials] = None
    console: Optional[ConsoleTarget] = None
    media: Optional[MediaSession] = None
    message: str = ""
    error_code: Optional[str] = None


class StreamingSession:
    """
    One streaming account + one console + one media session per task.
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.logger = get_logger(f"streaming_session_{task_id}")
        self._auth = AuthService()
        self._discovery = DiscoveryService()
        self._stream = XHomeStreamService()
        self.credentials: Optional[StreamingCredentials] = None
        self.console: Optional[ConsoleTarget] = None
        self.media: Optional[MediaSession] = None
        self._stream_context: Optional[Any] = None
        self._on_phase: Optional[Callable] = None

    def set_phase_callback(self, callback: Callable) -> None:
        self._on_phase = callback

    async def _emit_phase(self, phase: SessionPhase, message: str = "") -> None:
        if self._on_phase:
            result = self._on_phase(phase, message)
            if hasattr(result, "__await__"):
                await result

    async def open(
        self,
        email: str,
        password: str,
        streaming_account_id: str = "",
        auto_code: str = "",
        assigned_xbox: Optional[Dict[str, Any]] = None,
        auto_match_host: bool = True,
        window_manager: Any = None,
        decode_mode: str = "auto",
        check_cancel: Optional[Callable[[], bool]] = None,
        report_progress: Optional[Callable] = None,
        skip_auth: bool = False,
        existing_credentials: Optional[StreamingCredentials] = None,
        existing_console: Optional[ConsoleTarget] = None,
    ) -> SessionOpenResult:
        try:
            if check_cancel and check_cancel():
                return SessionOpenResult(success=False, error_code="CANCELLED", message="Cancelled")

            if skip_auth and existing_credentials:
                self.credentials = existing_credentials
            else:
                await self._emit_phase(SessionPhase.AUTHENTICATING, "Authenticating")
                self.credentials = await self._auth.authenticate(
                    email=email,
                    password=password,
                    auto_code=auto_code,
                    streaming_account_id=streaming_account_id,
                    check_cancel=check_cancel,
                    report_progress=report_progress,
                )

            if check_cancel and check_cancel():
                return SessionOpenResult(success=False, error_code="CANCELLED", message="Cancelled")

            if existing_console:
                self.console = existing_console
            else:
                await self._emit_phase(SessionPhase.DISCOVERING, "Discovering console")
                resolved = await self._discovery.resolve_console(
                    self.credentials,
                    self.task_id,
                    assigned_xbox=assigned_xbox,
                    auto_match_host=auto_match_host,
                    check_cancel=check_cancel,
                    report_progress=report_progress,
                )
                self.console = resolved.console
                self._stream_context = resolved.context

            if check_cancel and check_cancel():
                return SessionOpenResult(success=False, error_code="CANCELLED", message="Cancelled")

            await self._emit_phase(SessionPhase.STREAMING, "Opening stream")
            self.media = await self._stream.open_stream(
                self.credentials,
                self.console,
                self.task_id,
                window_manager=window_manager,
                decode_mode=decode_mode,
                check_cancel=check_cancel,
                report_progress=report_progress,
                source_context=self._stream_context,
            )

            await self._emit_phase(SessionPhase.INITIALIZING_DISPLAY, "Window + decode ready")
            input_mode = await self._detect_input_mode(self.media)
            await self._emit_phase(
                SessionPhase.INITIALIZING_INPUT,
                f"Input mode: {input_mode}",
            )

            await self._emit_phase(SessionPhase.READY, "SESSION_READY")
            return SessionOpenResult(
                success=True,
                credentials=self.credentials,
                console=self.console,
                media=self.media,
                message="SESSION_READY",
            )
        except Exception as exc:
            self.logger.error("Session open failed: %s", exc, exc_info=True)
            await self._emit_phase(SessionPhase.FAILED, str(exc))
            return SessionOpenResult(
                success=False,
                message=str(exc),
                error_code="SESSION_OPEN_FAILED",
            )

    async def reconnect(self) -> bool:
        if not self.media:
            return False
        await self._emit_phase(SessionPhase.STREAMING, "Reconnecting")
        ok = await self._stream.reconnect(self.media)
        if ok:
            await self._emit_phase(SessionPhase.READY, "Reconnected")
        return ok

    async def _detect_input_mode(self, media: MediaSession) -> str:
        """Physical gamepad if step3 already bound one; otherwise virtual via DataChannel."""
        ctx = media.context
        if getattr(ctx, "_gamepad_controller", None):
            return "physical"
        # step3/SDL already owns pygame — avoid re-init joystick (causes native crash on Windows).
        return "virtual"

    async def close(self, emit_phases: bool = True) -> None:
        """Tear down media; optionally emit CLOSING/CLOSED session phases."""
        if emit_phases:
            await self._emit_phase(SessionPhase.CLOSING, "Closing session")
        if self.media:
            await self._stream.close(self.media)
            self.media = None
        if emit_phases:
            await self._emit_phase(SessionPhase.CLOSED, "Session closed")
