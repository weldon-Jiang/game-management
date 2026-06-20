"""
WebSocket task_control 消息处理器。

契约：每条控制消息必须含 taskId；跨任务操作将被拒绝。
"""

from typing import Any, Callable, Dict, Optional

from ..core.logger import get_logger
from .input_focus import InputFocusManager
from .phase_fsm import PauseMode, SessionPhase
from .task_registry import TaskRuntimeRegistry


class TaskControlHandler:
    """将 task_control WS 动作路由到对应任务运行时。"""

    def __init__(
        self,
        registry: Optional[TaskRuntimeRegistry] = None,
        focus_manager: Optional[InputFocusManager] = None,
    ):
        self.logger = get_logger("task_control")
        self._registry = registry or TaskRuntimeRegistry.get_instance()
        self._focus = focus_manager or InputFocusManager.get_instance()
        self._scheduler: Optional[Any] = None

    def set_scheduler(self, scheduler: Any) -> None:
        self._scheduler = scheduler

    async def handle(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        将 task_control 命令分发给拥有 taskId 的运行时。

        控制消息限定在单任务运行时内，防止陈旧 WS 命令误操作其他并发任务。
        """
        task_id = data.get("taskId") or data.get("task_id")
        action = (data.get("action") or "").lower()

        if not task_id:
            self.logger.warning("task_control rejected: missing taskId")
            return {"success": False, "error": "taskId is required"}

        runtime = self._registry.get(task_id)
        if runtime is None:
            self.logger.warning("task_control rejected: unknown taskId=%s", task_id)
            return {"success": False, "error": f"Unknown taskId: {task_id}"}

        handlers: Dict[str, Callable] = {
            "pause": self._pause,
            "resume": self._resume,
            "cancel": self._cancel,
            "terminate": self._terminate,
            "show_window": self._show_window,
            "hide_window": self._hide_window,
            "focus_window": self._focus_window,
            "window_show": self._show_window,
            "window_hide": self._hide_window,
            "window_focus": self._focus_window,
            "skip_game_account": self._skip_game_account,
            "reconnect_stream": self._reconnect_stream,
            "start_game_automation": self._start_automation,
            "open_streaming_session": self._open_streaming,
        }

        handler = handlers.get(action)
        if not handler:
            return {"success": False, "error": f"Unknown action: {action}"}

        try:
            return await handler(runtime, data)
        except Exception as exc:
            self.logger.error("task_control %s failed: %s", action, exc, exc_info=True)
            return {"success": False, "error": str(exc)}

    async def _pause(self, runtime, data: Dict) -> Dict:
        """
        暂停自动化且不关闭串流资源。

        immediate 通过 InputGate 立即拦截输入；after_match 记录意图，
        待 Step4 完成当前比赛后再进入暂停阶段。
        """
        mode_str = (data.get("mode") or "immediate").lower()
        mode = (
            PauseMode.AFTER_MATCH
            if mode_str == "after_match"
            else PauseMode.IMMEDIATE
        )
        runtime.pause_mode = mode
        runtime.pause_after_match = mode == PauseMode.AFTER_MATCH
        runtime.phase_before_pause = runtime.phase_fsm.phase
        if mode == PauseMode.IMMEDIATE:
            from .pause_input_control import release_automation_input

            await release_automation_input(runtime.context, self.logger)
        runtime.context.pause()
        phase = runtime.set_phase(
            SessionPhase.PAUSED_AFTER_MATCH
            if mode == PauseMode.AFTER_MATCH
            else SessionPhase.PAUSED_IMMEDIATE,
            f"Paused ({mode.value})",
        )
        self._focus.focus(runtime.task_id)
        if self._scheduler:
            await self._scheduler.pause_task(runtime.task_id, mode=mode)
        if mode == PauseMode.IMMEDIATE:
            from ..task.task_timeline_events import (
                MSG_MANUAL_TAKEOVER_ON,
                emit_task_timeline_event,
            )

            await emit_task_timeline_event(
                runtime.context,
                MSG_MANUAL_TAKEOVER_ON,
                event_key="platform_pause_on",
            )
        return {"success": True, "phase": phase.value, "pauseMode": mode.value}

    async def _resume(self, runtime, data: Dict) -> Dict:
        if not runtime.phase_fsm.is_paused():
            return {"success": False, "error": "Task is not paused"}
        runtime.pause_mode = None
        runtime.pause_after_match = False
        from .pause_input_control import request_resume_reanchor, sync_scene_on_resume

        request_resume_reanchor(runtime.context)
        resume_scene = await sync_scene_on_resume(runtime.context, self.logger)
        runtime.context.resume()
        prev = runtime.phase_before_pause
        runtime.phase_before_pause = None
        # READY/AUTOMATION_FAILED 恢复后回到手动决策态；已启动的 Step4 才回到 automating。
        if prev == SessionPhase.READY or prev == SessionPhase.AUTOMATION_FAILED or not runtime.phase_fsm.automation_started:
            phase = runtime.set_phase(SessionPhase.READY, "Resumed")
        else:
            phase = runtime.set_phase(SessionPhase.AUTOMATING, "Resumed")
        if self._scheduler:
            await self._scheduler.resume_task(runtime.task_id)
        from ..task.task_timeline_events import (
            MSG_MANUAL_TAKEOVER_OFF,
            emit_task_timeline_event,
        )

        await emit_task_timeline_event(
            runtime.context,
            MSG_MANUAL_TAKEOVER_OFF,
            event_key="platform_pause_off",
        )
        result = {"success": True, "phase": phase.value}
        if resume_scene is not None:
            result["resumeSceneId"] = resume_scene
        return result

    async def _cancel(self, runtime, data: Dict) -> Dict:
        return await self._terminate(runtime, data)

    async def _terminate(self, runtime, data: Dict) -> Dict:
        """强制终止任务，由调度器执行单任务级清理。"""
        runtime.cancel_event.set()
        runtime.set_phase(SessionPhase.CLOSING, "Terminating")
        if self._scheduler and hasattr(self._scheduler, "force_terminate_task"):
            await self._scheduler.force_terminate_task(runtime.task_id)
        elif self._scheduler:
            await self._scheduler.stop_task(runtime.task_id)
        return {"success": True, "terminated": True}

    async def _show_window(self, runtime, data: Dict) -> Dict:
        if self._scheduler and hasattr(self._scheduler, "ensure_display_window"):
            ok = await self._scheduler.ensure_display_window(runtime.task_id)
            return {"success": ok, "windowVisible": ok}
        wm = runtime.modules.get("window_manager")
        if wm:
            ok = await wm.show_by_task(runtime.task_id)
            runtime.window_visible = ok
            return {"success": ok, "windowVisible": ok}
        return {"success": False, "windowVisible": False, "error": "No window manager"}

    async def _hide_window(self, runtime, data: Dict) -> Dict:
        runtime.window_visible = False
        if self._scheduler and hasattr(self._scheduler, "close_display_window"):
            ok = await self._scheduler.close_display_window(runtime.task_id)
            return {"success": ok, "windowVisible": False}
        wm = runtime.modules.get("window_manager")
        if wm:
            await wm.hide_by_task(runtime.task_id)
        return {"success": True, "windowVisible": False}

    async def _focus_window(self, runtime, data: Dict) -> Dict:
        self._focus.focus(runtime.task_id)
        wm = runtime.modules.get("window_manager")
        if wm:
            await wm.focus_by_task(runtime.task_id)
        return {"success": True}

    async def _skip_game_account(self, runtime, data: Dict) -> Dict:
        ga_id = data.get("gameAccountId") or data.get("game_account_id")
        if not ga_id:
            return {"success": False, "error": "gameAccountId required"}
        skipped = runtime.modules.setdefault("skipped_accounts", set())
        skipped.add(ga_id)
        task_obj = runtime.task_object
        if task_obj and hasattr(task_obj, "skip_game_account"):
            await task_obj.skip_game_account(ga_id)
        return {"success": True, "gameAccountId": ga_id}

    async def _reconnect_stream(self, runtime, data: Dict) -> Dict:
        """平台「重连串流」：全量重连 GSSV WebRTC（重新 play + 握手 + 等新鲜视频帧）。"""
        context = runtime.context
        context._reconnect_manual_override = True
        from ..xbox.stream_recovery import (
            invalidate_stream_video,
            reconnect_input_channel,
        )

        invalidate_stream_video(context, clear_sdl=True)
        task_logger = getattr(context, "task_logger", None)
        ok = await reconnect_input_channel(context, task_logger)
        return {"success": ok, "videoRestored": not bool(getattr(context, "_stream_video_stale", False))}

    async def _start_automation(self, runtime, data: Dict) -> Dict:
        """
        释放两阶段 READY 门闩并启动 Step4 自动化。

        所选 gameActionType 写入 task context，Step4 仍须在账号登录成功后应用。
        """
        if not runtime.phase_fsm.can_start_automation():
            return {
                "success": False,
                "error": f"Cannot start automation in phase {runtime.phase_fsm.phase.value}",
            }
        game_action_type = data.get("gameActionType") or data.get("game_action_type")
        if game_action_type:
            runtime.context.game_action_type = game_action_type
        automation_event = runtime.modules.get("automation_start_event")
        if automation_event:
            automation_event.set()
        if self._scheduler:
            await self._scheduler.start_automation(runtime.task_id, game_action_type)
        runtime.set_phase(SessionPhase.AUTOMATING, "Automation started")
        return {"success": True, "gameActionType": runtime.context.game_action_type}

    async def _open_streaming(self, runtime, data: Dict) -> Dict:
        return {"success": True, "phase": runtime.phase_fsm.phase.value}
