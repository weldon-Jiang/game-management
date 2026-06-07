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
        """
        Mark whether Step4 owns the virtual controller.

        Step1-3 only create stream/input channels and must keep this flag False;
        otherwise scene setup or READY state could accidentally send automation
        buttons while the user is manually operating the window.
        """
        self._automation_active = active

    @property
    def automation_active(self) -> bool:
        return self._automation_active

    def is_allowed(self) -> bool:
        """
        Return True only when Step4 is running and the task is not paused.

        The check is intentionally small and synchronous because it sits on the
        hot path before every virtual gamepad/DataChannel send.
        """
        if not self._automation_active:
            return False
        return not self._is_paused()
