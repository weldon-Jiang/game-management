"""
StreamingAccountTask — 单任务状态机（两阶段生命周期）。

阶段 1：认证 → 发现 → 串流 → READY（等待 start_automation）
阶段 2：开通门禁 → 逐账号 step4 → CLOSING（仅全部成功时）
"""

import asyncio
from typing import Any, Callable, Dict, List, Optional, Set

from ..core.task_logger import get_task_logger
from ..game.account_provisioning import AccountProvisioningModule
from ..runtime.input_focus import InputFocusManager
from ..runtime.input_gate import InputGate
from ..runtime.phase_fsm import PauseMode, SessionPhase
from ..runtime.task_registry import StreamingAccountTaskRuntime
from ..runtime.session import StreamingSession
from ..runtime.session_registry import SessionRegistry
from ..task.task_context import (
    AgentTaskContext,
    AutomationResult,
    TaskMainStatus,
    TaskStepStatus,
)
from ..vision.decode_strategy import release_decode_slot
from ..window.window_manager import StreamingWindowManager
from ..automation.step4 import step4_execute_gaming


class StreamingAccountTask:
    """单串流账号任务编排器，内置 phase FSM。"""

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
        self.task_logger = get_task_logger(runtime.task_id)
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
        执行两阶段串流任务生命周期。

        先打开并保持串流直至 READY，再等待平台下发 start_automation。
        Step4 失败时不关闭串流/窗口：任务进入 AUTOMATION_FAILED 等待重试，
        用户无需重跑 Step1-3。
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
            await self._apply_session_phase(phase, message)

        session.set_phase_callback(on_phase)

        try:
            self.context.update_task_status(TaskMainStatus.RUNNING)
            await self._apply_session_phase(SessionPhase.OPENING, "Starting streaming")

            open_result = await session.open(
                email=self.context.streaming_account_email,
                password=self.context.streaming_account_password,
                streaming_account_id=self.context.streaming_account_id,
                auto_code=self.context.streaming_account_auto_code,
                assigned_xbox=self._xbox_dict(),
                platform_xbox_hosts=self.context.platform_xbox_hosts,
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
                self.task_logger.warning(
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
                # READY 等待期间，仅取消路径会拆除串流。
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
                        await self._apply_session_phase(
                            SessionPhase.AUTOMATION_FAILED, retry_msg
                        )
                    else:
                        ready_msg = (
                            "等待选择自动化类型"
                            if display_ok
                            else "串流就绪，请显示窗口并选择自动化类型"
                        )
                        await self._apply_session_phase(SessionPhase.READY, ready_msg)
                    automation_event.clear()
                    # READY 为长寿命人工交接点；仅 start_automation 或取消可退出。
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

                await self._apply_session_phase(SessionPhase.AUTOMATING, "Automation running")

                await self._ensure_display_after_stream()

                # Step4 是唯一虚拟手柄来源；返回后立即关闭 automation_active。
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
                # 保留串流/窗口，使用户可在同一会话内重试 Step4。
                await self._apply_session_phase(SessionPhase.AUTOMATION_FAILED, fail_msg)
                self.task_logger.warning(
                    "Step4 failed (%s); stream kept alive for retry",
                    step4_result.error_code,
                )

        except asyncio.CancelledError:
            await self._cleanup_session(session, destroy_window=True)
            self.runtime.set_phase(SessionPhase.CLOSED, "Cancelled")
            return AutomationResult(success=False, error_code="CANCELLED", message="Cancelled")
        except Exception as exc:
            self.task_logger.error("StreamingAccountTask failed: %s", exc, exc_info=True)
            if not self.runtime.phase_fsm.is_terminal():
                await self._apply_session_phase(SessionPhase.FAILED, str(exc))
            await self._cleanup_session(session, destroy_window=True, emit_session_phases=False)
            return AutomationResult(success=False, error_code="EXCEPTION", message=str(exc))
        finally:
            # 最终兜底：任务不得遗留 input 焦点、解码槽或注册表项。
            input_gate.set_automation_active(False)
            focus.pop(task_id)
            release_decode_slot(self._decode_mode)
            SessionRegistry.get_instance().remove(task_id)

    async def _ensure_display_after_stream(self) -> bool:
        try:
            from ..automation.step3.display_helpers import step3_ensure_display

            ok = await step3_ensure_display(self.context)
            self.runtime.window_visible = ok
            return ok
        except Exception as exc:
            self.task_logger.warning("打开显示窗口失败: %s", exc)
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
        "_stream_lease_server_id",
        "_lan_direct",
        "_smartglass_certificate",
        "_smartglass_udp_connected",
        "_smartglass_enabled",
        "_lan_srtp_keys",
        "_lan_rtp_port",
        "_lan_endpoints",
        "_video_stream_controller",
        "_video_capture_mode",
        "_video_mode",
        "_rtp_available",
        "_direct_capture",
        "_input_channel_dirty",
        "_gpu_available",
        "_gpu_type",
        "_gpu_decoder",
        "_controller_protocol",
        "_keyboard_mapper",
        "_gamepad_controller",
        "_sdl_display_task",
        "_stream_runtime",
        "_step3_init_completed",
    )

    def _sync_media_context(self, media_ctx: AgentTaskContext) -> None:
        """复制 step2/3 串流产物，供 step4 重连 LAN 串流。"""
        for name in self._STREAM_CONTEXT_ATTRS:
            if hasattr(media_ctx, name):
                setattr(self.context, name, getattr(media_ctx, name))

    def _xbox_dict(self) -> Optional[Dict]:
        xb = self.context.assigned_xbox
        if not xb:
            return None
        return {
            "id": xb.platform_host_id or xb.id,
            "xboxId": xb.id,
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
        """关闭串流资源，并销毁或隐藏显示窗口。"""
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

    async def _apply_session_phase(self, phase: SessionPhase, message: str) -> None:
        """更新本地 FSM 并上报一条 session 事件（避免 set_phase + _report_session 双写时间线）。"""
        self.runtime.set_phase(phase, message)
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
        await self._apply_session_phase(phase, message)
