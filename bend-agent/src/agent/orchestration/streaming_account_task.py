"""
StreamingAccountTask — single-task state machine (two-phase lifecycle).

Phase 1: auth → discovery → stream → READY (wait for start_automation)
Phase 2: provisioning gate → step4 per game account → CLOSING
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set

from ..core.logger import get_logger
from ..game.account_provisioning import AccountProvisioningModule
from ..runtime.input_focus import InputFocusManager
from ..runtime.phase_fsm import PauseMode, SessionPhase
from ..runtime.task_registry import StreamingAccountTaskRuntime
from ..session.api import StreamingSession
from ..session.registry import SessionRegistry
from ..task.task_context import (
    AgentTaskContext,
    AutomationResult,
    TaskMainStatus,
    TaskStepStatus,
)
from ..vision.decode_strategy import release_decode_slot
from ..window.window_manager import StreamingWindowManager
from ..automation.step4_game_automation import step4_execute_gaming


class StreamingAccountTask:
    """Per streaming-account task orchestrator with phase FSM."""

    def __init__(
        self,
        runtime: StreamingAccountTaskRuntime,
        window_manager: StreamingWindowManager,
        platform_client: Any,
        two_phase: bool = True,
        game_action_type: Optional[str] = None,
    ):
        self.runtime = runtime
        self.context = runtime.context
        self.window_manager = window_manager
        self.platform_client = platform_client
        self.two_phase = two_phase
        self.logger = get_logger(f"sat_{runtime.task_id}")
        self._skipped: Set[str] = set()
        self._decode_mode = "auto"
        if game_action_type:
            self.context.game_action_type = game_action_type

        runtime.task_object = self
        runtime.modules["window_manager"] = window_manager
        runtime.modules["skipped_accounts"] = self._skipped
        runtime.modules["automation_start_event"] = asyncio.Event()
        if not two_phase or game_action_type:
            runtime.modules["automation_start_event"].set()

    async def execute(self, check_cancel: Callable[[], bool]) -> AutomationResult:
        task_id = self.runtime.task_id
        focus = InputFocusManager.get_instance()
        focus.push(task_id)

        session = StreamingSession(task_id)
        self.runtime.modules["streaming_session"] = session
        SessionRegistry.get_instance().register(task_id, session)

        async def on_phase(phase: SessionPhase, message: str):
            self.runtime.set_phase(phase, message)
            await self._report_session(phase, message)

        session.set_phase_callback(on_phase)

        try:
            self.context.update_task_status(TaskMainStatus.RUNNING)
            self.runtime.set_phase(SessionPhase.OPENING, "Starting streaming")

            open_result = await session.open(
                email=self.context.streaming_account_email,
                password=self.context.streaming_account_password,
                streaming_account_id=self.context.streaming_account_id,
                auto_code=self.context.streaming_account_auto_code,
                assigned_xbox=self._xbox_dict(),
                auto_match_host=self.context.auto_match_host,
                window_manager=self.window_manager,
                check_cancel=check_cancel,
                report_progress=self._report_progress,
            )
            if not open_result.success:
                return AutomationResult(
                    success=False,
                    failed_step="SESSION",
                    message=open_result.message,
                    error_code=open_result.error_code,
                )

            if open_result.media:
                self._decode_mode = open_result.media.decode_mode
                self._sync_media_context(open_result.media.context)

            provisioning = AccountProvisioningModule(
                task_id=task_id,
                scene_detector=getattr(self.context, "_streaming_scene_detector", None),
                input_sender=getattr(self.context, "_controller_protocol", None),
                report_progress=self._report_progress_extended,
            )
            self.runtime.modules["account_provisioning"] = provisioning

            if self.two_phase and not self.context.game_action_type:
                await self._report_session(SessionPhase.READY, "等待选择自动化类型")
                automation_event: asyncio.Event = self.runtime.modules["automation_start_event"]
                while not automation_event.is_set():
                    if check_cancel():
                        return AutomationResult(success=False, error_code="CANCELLED", message="Cancelled")
                    await self.context.wait_if_paused()
                    await asyncio.sleep(0.5)

            self.runtime.set_phase(SessionPhase.AUTOMATING, "Automation running")
            try:
                from ..automation.step3_streaming_init import _stop_sdl_display_pump
                await _stop_sdl_display_pump(self.context)
            except Exception:
                pass
            step4_result = await step4_execute_gaming(
                self.context,
                check_cancel,
                self._report_progress,
                platform_client=self.platform_client,
                provisioning_module=provisioning,
                skipped_accounts=self._skipped,
                pause_after_match=lambda: self.runtime.pause_after_match,
                set_session_phase=self._set_session_phase,
            )

            if step4_result.success:
                self.runtime.set_phase(SessionPhase.CLOSING, "All accounts done")
                await self._cleanup_session(session, destroy_window=True)
                self.runtime.set_phase(SessionPhase.CLOSED, "Completed")
                return AutomationResult(
                    success=True,
                    message=step4_result.message,
                    total_matches=step4_result.total_matches,
                )

            await self._cleanup_session(session, destroy_window=True)
            self.runtime.set_phase(SessionPhase.FAILED, step4_result.message)
            return AutomationResult(
                success=False,
                failed_step="STEP4",
                message=step4_result.message,
                error_code=step4_result.error_code,
            )

        except asyncio.CancelledError:
            await self._cleanup_session(session, destroy_window=True)
            self.runtime.set_phase(SessionPhase.CLOSED, "Cancelled")
            return AutomationResult(success=False, error_code="CANCELLED", message="Cancelled")
        except Exception as exc:
            self.logger.error("StreamingAccountTask failed: %s", exc, exc_info=True)
            await self._cleanup_session(session, destroy_window=True)
            self.runtime.set_phase(SessionPhase.FAILED, str(exc))
            return AutomationResult(success=False, error_code="EXCEPTION", message=str(exc))
        finally:
            focus.pop(task_id)
            release_decode_slot(self._decode_mode)
            SessionRegistry.get_instance().remove(task_id)

    async def skip_game_account(self, game_account_id: str) -> None:
        self._skipped.add(game_account_id)

    _STREAM_CONTEXT_ATTRS = (
        "microsoft_tokens",
        "xbox_tokens",
        "xbox_session",
        "current_xbox",
        "frame_capture",
        "sdl_window",
        "assigned_xbox",
        "_play_session_manager",
        "_play_session_enabled",
        "_play_session_session_id",
        "_play_session_session_path",
        "_sdp_enabled",
        "_media_channel_enabled",
        "_cloud_stream_session",
        "_webrtc_handler",
        "_webrtc_frame_controller",
        "_video_capture_mode",
        "_video_mode",
        "_rtp_available",
        "_gpu_available",
        "_gpu_type",
        "_gpu_decoder",
        "_controller_protocol",
        "_keyboard_mapper",
        "_gamepad_controller",
        "_sdl_display_task",
    )

    def _sync_media_context(self, media_ctx: AgentTaskContext) -> None:
        """Copy step2/3 stream artifacts so step4 can reconnect WebRTC."""
        for name in self._STREAM_CONTEXT_ATTRS:
            if hasattr(media_ctx, name):
                setattr(self.context, name, getattr(media_ctx, name))

    def _xbox_dict(self) -> Optional[Dict]:
        xb = self.context.assigned_xbox
        if not xb:
            return None
        return {
            "id": xb.id,
            "name": xb.name,
            "ipAddress": xb.ip_address,
            "liveId": xb.live_id,
            "macAddress": xb.mac_address,
        }

    async def _cleanup_session(self, session: StreamingSession, destroy_window: bool) -> None:
        try:
            from ..automation.step3_streaming_init import _stop_sdl_display_pump
            await _stop_sdl_display_pump(self.context)
        except Exception:
            pass
        await session.close()
        if destroy_window:
            sdl = self.context.sdl_window
            if sdl:
                try:
                    if hasattr(sdl, "destroy"):
                        await sdl.destroy()
                    elif hasattr(sdl, "close"):
                        sdl.close()
                except Exception:
                    pass
                self.context.sdl_window = None
            await self.window_manager.destroy_by_task(self.runtime.task_id)
        elif self.context.sdl_window and hasattr(self.context.sdl_window, "hide"):
            try:
                self.context.sdl_window.hide()
            except Exception:
                pass

    async def _report_progress(
        self,
        task_id: str,
        step: str,
        status: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        if extra_data:
            kwargs.update(extra_data)
        if self.platform_client:
            await self.platform_client.report_progress(
                task_id, step, status, message, **kwargs
            )

    async def _report_progress_extended(
        self,
        task_id: str,
        step: str,
        status: str,
        message: str,
        extra_data: Optional[Dict[str, Any]] = None,
        **kwargs,
    ):
        await self._report_progress(task_id, step, status, message, extra_data, **kwargs)

    async def _report_session(self, phase: SessionPhase, message: str) -> None:
        await self._report_progress(
            self.runtime.task_id,
            "SESSION",
            "RUNNING",
            message,
            scope="session",
            phase=phase.value,
            windowState="visible" if self.runtime.window_visible else "hidden",
            pauseMode=self.runtime.pause_mode.value if self.runtime.pause_mode else None,
        )

    async def _set_session_phase(self, phase: SessionPhase, message: str) -> None:
        from ..runtime.phase_fsm import PauseMode

        self.runtime.set_phase(phase, message)
        if phase.value.startswith("paused"):
            self.runtime.pause_mode = PauseMode.IMMEDIATE
            self.runtime.pause_after_match = False
            self.context.pause_mode = PauseMode.IMMEDIATE.value
            self.context.pause()
        elif phase == SessionPhase.AUTOMATING:
            self.runtime.pause_mode = None
            self.runtime.pause_after_match = False
            self.context.pause_mode = None
            self.context.resume()
        await self._report_session(phase, message)
