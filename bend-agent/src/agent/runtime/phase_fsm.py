"""
StreamingAccountTask 的会话阶段有限状态机。

阶段与平台 streaming_session.phase 及 task_control 契约对齐。
"""

from enum import Enum
from typing import Dict, FrozenSet, Optional, Set


class SessionPhase(str, Enum):
    OPENING = "opening"
    AUTHENTICATING = "authenticating"
    DISCOVERING = "discovering"
    STREAMING = "streaming"
    INITIALIZING_DISPLAY = "initializing_display"
    INITIALIZING_INPUT = "initializing_input"
    READY = "ready"
    AUTOMATION_FAILED = "automation_failed"
    AUTOMATING = "automating"
    PAUSED_IMMEDIATE = "paused_immediate"
    PAUSED_AFTER_MATCH = "paused_after_match"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class PauseMode(str, Enum):
    IMMEDIATE = "immediate"
    AFTER_MATCH = "after_match"


# 合法迁移：from_phase -> 允许的目标 phase 集合
# AUTOMATION_FAILED 允许回到 AUTOMATING/READY，支撑 Step4 失败保留串流后的重试语义。
_TRANSITIONS: Dict[SessionPhase, FrozenSet[SessionPhase]] = {
    SessionPhase.OPENING: frozenset({
        SessionPhase.AUTHENTICATING,
        SessionPhase.FAILED,
        SessionPhase.CLOSED,
    }),
    SessionPhase.AUTHENTICATING: frozenset({
        SessionPhase.DISCOVERING,
        SessionPhase.FAILED,
        SessionPhase.CLOSED,
    }),
    SessionPhase.DISCOVERING: frozenset({
        SessionPhase.STREAMING,
        SessionPhase.FAILED,
        SessionPhase.CLOSED,
    }),
    SessionPhase.STREAMING: frozenset({
        SessionPhase.INITIALIZING_DISPLAY,
        SessionPhase.READY,
        SessionPhase.FAILED,
        SessionPhase.CLOSED,
    }),
    SessionPhase.INITIALIZING_DISPLAY: frozenset({
        SessionPhase.INITIALIZING_INPUT,
        SessionPhase.READY,
        SessionPhase.FAILED,
        SessionPhase.CLOSED,
    }),
    SessionPhase.INITIALIZING_INPUT: frozenset({
        SessionPhase.READY,
        SessionPhase.FAILED,
        SessionPhase.CLOSED,
    }),
    SessionPhase.READY: frozenset({
        SessionPhase.AUTOMATING,
        SessionPhase.PAUSED_IMMEDIATE,
        SessionPhase.CLOSING,
        SessionPhase.CLOSED,
        SessionPhase.FAILED,
    }),
    SessionPhase.AUTOMATION_FAILED: frozenset({
        SessionPhase.AUTOMATING,
        SessionPhase.READY,
        SessionPhase.CLOSING,
        SessionPhase.CLOSED,
        SessionPhase.FAILED,
    }),
    SessionPhase.AUTOMATING: frozenset({
        SessionPhase.PAUSED_IMMEDIATE,
        SessionPhase.PAUSED_AFTER_MATCH,
        SessionPhase.CLOSING,
        SessionPhase.CLOSED,
        SessionPhase.FAILED,
        SessionPhase.READY,
        SessionPhase.AUTOMATION_FAILED,
    }),
    SessionPhase.PAUSED_IMMEDIATE: frozenset({
        SessionPhase.AUTOMATING,
        SessionPhase.READY,
        SessionPhase.CLOSING,
        SessionPhase.CLOSED,
        SessionPhase.FAILED,
    }),
    SessionPhase.PAUSED_AFTER_MATCH: frozenset({
        SessionPhase.AUTOMATING,
        SessionPhase.PAUSED_IMMEDIATE,
        SessionPhase.CLOSING,
        SessionPhase.CLOSED,
        SessionPhase.FAILED,
    }),
    SessionPhase.CLOSING: frozenset({
        SessionPhase.CLOSED,
        SessionPhase.FAILED,
    }),
    SessionPhase.CLOSED: frozenset(),
    SessionPhase.FAILED: frozenset({
        SessionPhase.CLOSED,
    }),
}

_TERMINAL: Set[SessionPhase] = {SessionPhase.CLOSED, SessionPhase.FAILED}


class PhaseFSM:
    """带迁移校验的每任务会话阶段状态机。"""

    def __init__(self, initial: SessionPhase = SessionPhase.OPENING):
        self._phase = initial
        self._automation_started = False

    @property
    def phase(self) -> SessionPhase:
        return self._phase

    @property
    def automation_started(self) -> bool:
        return self._automation_started

    def can_transition(self, target: SessionPhase) -> bool:
        if target == self._phase:
            return True
        allowed = _TRANSITIONS.get(self._phase, frozenset())
        return target in allowed

    def transition(self, target: SessionPhase) -> SessionPhase:
        if not self.can_transition(target):
            raise ValueError(
                f"Invalid phase transition: {self._phase.value} -> {target.value}"
            )
        self._phase = target
        if target == SessionPhase.AUTOMATING:
            self._automation_started = True
        return self._phase

    def is_terminal(self) -> bool:
        return self._phase in _TERMINAL

    def is_paused(self) -> bool:
        return self._phase in (
            SessionPhase.PAUSED_IMMEDIATE,
            SessionPhase.PAUSED_AFTER_MATCH,
        )

    def can_start_automation(self) -> bool:
        """仅 READY 与 AUTOMATION_FAILED 可接收 start_game_automation。"""
        return self._phase in (
            SessionPhase.READY,
            SessionPhase.AUTOMATION_FAILED,
        )

    def can_restart_streaming(self) -> bool:
        """
        自动化/暂停后禁止重启串流。

        同一 taskId 的 Step1-3 重跑须在 automation_started 置位前完成，
        否则平台会拆掉进行中的 Step4 会话。
        """
        return not self._automation_started

    @staticmethod
    def pause_phase_for_mode(mode: PauseMode) -> SessionPhase:
        if mode == PauseMode.AFTER_MATCH:
            return SessionPhase.PAUSED_AFTER_MATCH
        return SessionPhase.PAUSED_IMMEDIATE
