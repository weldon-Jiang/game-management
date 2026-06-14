"""
StreamingSession — 编排 auth → discovery → xhome_stream 就绪链。
"""

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from ..auth.api import AuthService, StreamingCredentials
from ..core.task_logger import get_task_logger
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
    每个任务对应一个串流账号、一台主机与一个媒体会话。
    """

    def __init__(self, task_id: str):
        self.task_id = task_id
        self.task_logger = get_task_logger(task_id)
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
        platform_xbox_hosts: Optional[List[Dict[str, Any]]] = None,
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
                await self._close_partial_media()
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
                    task_id=self.task_id,
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
                    platform_xbox_hosts=platform_xbox_hosts,
                    auto_match_host=auto_match_host,
                    check_cancel=check_cancel,
                    report_progress=report_progress,
                )
                self.console = resolved.console
                self._stream_context = resolved.context

            if check_cancel and check_cancel():
                await self._close_partial_media()
                return SessionOpenResult(success=False, error_code="CANCELLED", message="Cancelled")

            from ..automation.step3_xsrp import is_xsrp_stream_media_ready

            stream_already_ready = (
                self._stream_context is not None
                and is_xsrp_stream_media_ready(self._stream_context)
            )
            if stream_already_ready:
                # xsrp 在 Step2 链内已完成 Step3，但仍须上报 STREAMING，
                # 否则 FSM 停留在 discovering，后续 ready 迁移会被拒绝。
                self.task_logger.info(
                    "Step2+3 已在 discovery 完成，跳过 open_stream 重复初始化"
                )
                await self._emit_phase(SessionPhase.STREAMING, "Stream connected")
            else:
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
            self.task_logger.error("Session open failed: %s", exc, exc_info=True)
            await self._close_partial_media()
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
        """step3 已绑定物理手柄则用物理输入，否则经 DataChannel 虚拟输入。"""
        ctx = media.context
        if getattr(ctx, "_gamepad_controller", None):
            return "physical"
        # step3/SDL 已占用 pygame — 避免重复初始化 joystick（Windows 上可能原生崩溃）。
        return "virtual"

    async def close(self, emit_phases: bool = True) -> None:
        """拆除媒体资源；可选上报 CLOSING/CLOSED 会话阶段。"""
        if emit_phases:
            await self._emit_phase(SessionPhase.CLOSING, "Closing session")
        if self.media:
            await self._stream.close(self.media)
            self.media = None
            self._stream_context = None
        elif self._stream_context:
            await self._stream.close_context(self._stream_context)
            self._stream_context = None
        if emit_phases:
            await self._emit_phase(SessionPhase.CLOSED, "Session closed")

    async def _close_partial_media(self) -> None:
        """Step2 之后、READY 之前失败时的尽力清理。"""
        try:
            if self.media:
                await self._stream.close(self.media)
                self.media = None
            elif self._stream_context:
                await self._stream.close_context(self._stream_context)
                self._stream_context = None
        except Exception as cleanup_exc:
            self.task_logger.warning("Partial session cleanup failed: %s", cleanup_exc)
