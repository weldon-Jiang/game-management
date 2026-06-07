"""Gate virtual controller input during pause or outside step4 automation."""

from typing import Callable, Optional


class InputGate:
    """
    Blocks gamepad/DataChannel input when automation is inactive or task is paused.

    Step4 sets automation_active=True while running; pause clears input without
    tearing down the stream session.
    """

    def __init__(self, is_paused: Callable[[], bool]):
        self._is_paused = is_paused
        self._automation_active = False

    def set_automation_active(self, active: bool) -> None:
        self._automation_active = active

    @property
    def automation_active(self) -> bool:
        return self._automation_active

    def is_allowed(self) -> bool:
        if not self._automation_active:
            return False
        return not self._is_paused()
