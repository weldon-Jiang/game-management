"""
Session phase finite-state machine for StreamingAccountTask.

Phases align with platform streaming_session.phase and task_control contract.
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
    AUTOMATING = "automating"
    PAUSED_IMMEDIATE = "paused_immediate"
    PAUSED_AFTER_MATCH = "paused_after_match"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


class PauseMode(str, Enum):
    IMMEDIATE = "immediate"
    AFTER_MATCH = "after_match"


# Valid transitions: from_phase -> set of allowed target phases
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
    SessionPhase.AUTOMATING: frozenset({
        SessionPhase.PAUSED_IMMEDIATE,
        SessionPhase.PAUSED_AFTER_MATCH,
        SessionPhase.CLOSING,
        SessionPhase.CLOSED,
        SessionPhase.FAILED,
        SessionPhase.READY,
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
    """Per-task session phase state machine with transition validation."""

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
        return self._phase == SessionPhase.READY

    def can_restart_streaming(self) -> bool:
        """After automating/paused, restart streaming is forbidden."""
        return not self._automation_started

    @staticmethod
    def pause_phase_for_mode(mode: PauseMode) -> SessionPhase:
        if mode == PauseMode.AFTER_MATCH:
            return SessionPhase.PAUSED_AFTER_MATCH
        return SessionPhase.PAUSED_IMMEDIATE
