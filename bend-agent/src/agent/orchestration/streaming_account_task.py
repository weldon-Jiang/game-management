"""
StreamingAccountTask — single-task state machine (two-phase lifecycle).

Phase 1: auth → discovery → stream → READY (wait for start_automation)
Phase 2: provisioning gate → step4 per game account → CLOSING (only on full success)
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set

from ..core.logger import get_logger
from ..game.account_provisioning import AccountProvisioningModule
from ..runtime.input_focus import InputFocusManager
from ..runtime.input_gate import InputGate
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
        self._last_automation_fail_msg: Optional[str] = None
        if game_action_type:
            self.context.game_action_type = game_action_type

        runtime.task_object = self
        runtime.modules["window_manager"] = window_manager
        runtime.modules["skipped_accounts"] = self._skipped
        runtime.modules["automation_start_event"] = asyncio.Event()
        if not two_phase or game_action_type:
            runtime.modules["automation_start_event"].set()

    async def execute(self, check_cancel: Callable[[], bool]) -> AutomationResult:
        """
        Run the two-phase streaming task lifecycle.

        The method first opens and keeps a stream alive until READY, then waits
        for the platform to send start_automation. Step4 failures deliberately
        do not close the stream/window: the task moves to AUTOMATION_FAILED and
        waits for a retry so users can recover without rerunning Step1-3.
        """
        task_id = self.runtime.task_id
        focus = InputFocusManager.get_instance()
        focus.push(task_id)

        session = StreamingSession(task_id)
        self.runtime.modules["streaming_session"] = session
        SessionRegistry.get_instance().register(task_id, session)

        input_gate = InputGate(self.context.is_paused)
        self.runtime.modules["input_gate"] = input_gate

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
                await self._cleanup_session(session, destroy_window=True)
                return AutomationResult(
                    success=False,
                    failed_step="SESSION",
                    message=open_result.message,
                    error_code=open_result.error_code,
                )

            if open_result.media:
                self._decode_mode = open_result.media.decode_mode
                self._sync_media_context(open_result.media.context)

            display_ok = await self._ensure_display_after_stream()
            if not display_ok:
                self.logger.warning(
                    "串流成功但窗口未就绪，进入 READY 后可手动显示窗口"
                )

            provisioning = AccountProvisioningModule(
                task_id=task_id,
                scene_detector=getattr(self.context, "_streaming_scene_detector", None),
                input_sender=getattr(self.context, "_controller_protocol", None),
                report_progress=self._report_progress_extended,
                platform_client=self.platform_client,
            )
            self.runtime.modules["account_provisioning"] = provisioning

            automation_event: asyncio.Event = self.runtime.modules["automation_start_event"]
            total_matches = 0

            while True:
                # Cancellation is the only path that tears down the stream while waiting in READY.
                if check_cancel():
                    await self._cleanup_session(session, destroy_window=True)
                    self.runtime.set_phase(SessionPhase.CLOSED, "Cancelled")
                    return AutomationResult(
                        success=False, error_code="CANCELLED", message="Cancelled"
                    )

                if self.two_phase and not self.context.game_action_type:
                    if self.runtime.phase_fsm.phase == SessionPhase.AUTOMATION_FAILED:
                        retry_msg = (
                            self._last_automation_fail_msg
                            or "自动化失败，可重新选择模式后重试"
                        )
                        await self._report_session(
                            SessionPhase.AUTOMATION_FAILED, retry_msg
                        )
                    else:
                        ready_msg = (
                            "等待选择自动化类型"
                            if display_ok
                            else "串流就绪，请显示窗口并选择自动化类型"
                        )
                        self.runtime.set_phase(SessionPhase.READY, ready_msg)
                        await self._report_session(SessionPhase.READY, ready_msg)
                    automation_event.clear()
                    # READY is a long-lived manual handoff point; it only exits on start_automation or cancellation.
                    while not automation_event.is_set():
                        if check_cancel():
                            await self._cleanup_session(session, destroy_window=True)
                            return AutomationResult(
                                success=False,
                                error_code="CANCELLED",
                                message="Cancelled",
                            )
                        await self.context.wait_if_paused()
                        await asyncio.sleep(0.5)

                self.runtime.set_phase(SessionPhase.AUTOMATING, "Automation running")
                await self._report_session(SessionPhase.AUTOMATING, "Automation running")

                await self._ensure_display_after_stream()

                # Step4 is the only owner of virtual controller input; disable it immediately after Step4 returns.
                input_gate.set_automation_active(True)
                step4_result = await step4_execute_gaming(
                    self.context,
                    check_cancel,
                    self._report_progress,
                    platform_client=self.platform_client,
                    provisioning_module=provisioning,
                    skipped_accounts=self._skipped,
                    pause_after_match=lambda: self.runtime.pause_after_match,
                    set_session_phase=self._set_session_phase,
                    keep_session_alive=True,
                    input_gate=input_gate,
                )
                input_gate.set_automation_active(False)

                if step4_result.success:
                    total_matches = step4_result.total_matches or total_matches
                    self.runtime.set_phase(SessionPhase.CLOSING, "All accounts done")
                    await self._cleanup_session(session, destroy_window=True)
                    self.runtime.set_phase(SessionPhase.CLOSED, "Completed")
                    return AutomationResult(
                        success=True,
                        message=step4_result.message,
                        total_matches=total_matches,
                    )

                if check_cancel():
                    await self._cleanup_session(session, destroy_window=True)
                    return AutomationResult(
                        success=False,
                        error_code="CANCELLED",
                        message="Cancelled",
                    )

                self.context.game_action_type = None
                automation_event.clear()
                fail_msg = step4_result.message or "自动化失败"
                self._last_automation_fail_msg = fail_msg
                # Keep stream/window resources alive so the user can retry Step4 from the same READY-like session.
                self.runtime.set_phase(SessionPhase.AUTOMATION_FAILED, fail_msg)
                await self._report_session(SessionPhase.AUTOMATION_FAILED, fail_msg)
                self.logger.warning(
                    "Step4 failed (%s); stream kept alive for retry",
                    step4_result.error_code,
                )

        except asyncio.CancelledError:
            await self._cleanup_session(session, destroy_window=True)
            self.runtime.set_phase(SessionPhase.CLOSED, "Cancelled")
            return AutomationResult(success=False, error_code="CANCELLED", message="Cancelled")
        except Exception as exc:
            self.logger.error("StreamingAccountTask failed: %s", exc, exc_info=True)
            if not self.runtime.phase_fsm.is_terminal():
                self.runtime.set_phase(SessionPhase.FAILED, str(exc))
                await self._report_session(SessionPhase.FAILED, str(exc))
            await self._cleanup_session(session, destroy_window=True, emit_session_phases=False)
            return AutomationResult(success=False, error_code="EXCEPTION", message=str(exc))
        finally:
            # Final safety net: no task should leave input focus, decode slots, or registry entries behind.
            input_gate.set_automation_active(False)
            focus.pop(task_id)
            release_decode_slot(self._decode_mode)
            SessionRegistry.get_instance().remove(task_id)

    async def _ensure_display_after_stream(self) -> bool:
        try:
            from ..automation.step3_streaming_init import step3_ensure_display

            ok = await step3_ensure_display(self.context)
            self.runtime.window_visible = ok
            return ok
        except Exception as exc:
            self.logger.warning("打开显示窗口失败: %s", exc)
            self.runtime.window_visible = False
            return False

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
        "_xhome_requires_webrtc",
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

    async def _cleanup_session(
        self,
        session: StreamingSession,
        destroy_window: bool,
        emit_session_phases: bool = True,
    ) -> None:
        """Close stream resources and either destroy or hide the display window."""
        await session.close(emit_phases=emit_session_phases)
        if destroy_window:
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
