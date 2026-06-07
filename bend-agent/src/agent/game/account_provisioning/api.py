"""
AccountProvisioningModule — passive gate before each GameAction.

Detect → Add (if missing) → Verify. User cannot start this module directly.
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, Optional

from ...core.logger import get_logger
from ...task.task_context import GameAccountInfo
from .detector import ProfileDetector
from .add_account_flow import AddAccountFlow


class ProvisioningPhase(str, Enum):
    IDLE = "idle"
    DETECTING = "detecting"
    ADDING = "adding"
    VERIFYING = "verifying"
    READY = "ready"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class ProvisioningResult:
    success: bool
    phase: ProvisioningPhase
    message: str = ""
    step_index: int = 0
    step_total: int = 0


class AccountProvisioningModule:
    """Per-task instance; mounted on StreamingAccountTaskRuntime.modules."""

    STEP_TOTAL = 7

    def __init__(
        self,
        task_id: str,
        scene_detector: Any,
        input_sender: Any,
        report_progress: Optional[Callable] = None,
    ):
        self.task_id = task_id
        self.logger = get_logger(f"account_provisioning_{task_id}")
        self._detector = ProfileDetector(scene_detector)
        self._adder = AddAccountFlow(scene_detector, input_sender)
        self._report = report_progress
        self._phase = ProvisioningPhase.IDLE

    def refresh_dependencies(
        self,
        scene_detector: Any = None,
        input_sender: Any = None,
    ) -> None:
        """Late-bind detector/input after step3/step4 init."""
        if scene_detector is not None:
            self._detector._scene = scene_detector
            self._adder._scene = scene_detector
        if input_sender is not None:
            self._adder._input = input_sender

    async def _emit(
        self,
        phase: ProvisioningPhase,
        message: str,
        game_account_id: str,
        step_index: int = 0,
        status: str = "RUNNING",
    ) -> None:
        self._phase = phase
        if not self._report:
            return
        await self._report(
            self.task_id,
            "STEP4",
            status,
            message,
            scope="module",
            module="account_provisioning",
            phase=phase.value,
            game_account_id=game_account_id,
            stepIndex=step_index,
            stepTotal=self.STEP_TOTAL,
        )

    async def ensure(
        self,
        game_account: GameAccountInfo,
        check_cancel: Callable[[], bool],
        skipped: bool = False,
    ) -> ProvisioningResult:
        if skipped:
            await self._emit(
                ProvisioningPhase.SKIPPED,
                "Account skipped",
                game_account.id,
                status="SKIPPED",
            )
            return ProvisioningResult(
                success=False,
                phase=ProvisioningPhase.SKIPPED,
                message="skipped",
            )

        if check_cancel():
            return ProvisioningResult(success=False, phase=ProvisioningPhase.FAILED, message="cancelled")

        await self._emit(
            ProvisioningPhase.DETECTING,
            "检测账号是否存在",
            game_account.id,
            step_index=1,
        )
        exists = await self._detector.profile_exists(game_account)
        if exists:
            await self._emit(
                ProvisioningPhase.READY,
                "账号已存在",
                game_account.id,
                step_index=self.STEP_TOTAL,
                status="COMPLETED",
            )
            return ProvisioningResult(
                success=True,
                phase=ProvisioningPhase.READY,
                message="already_exists",
                step_index=self.STEP_TOTAL,
                step_total=self.STEP_TOTAL,
            )

        await self._emit(
            ProvisioningPhase.ADDING,
            "添加账号中",
            game_account.id,
            step_index=2,
        )
        added = await self._adder.run(
            game_account,
            check_cancel=check_cancel,
            on_step=lambda idx, msg: asyncio.create_task(
                self._emit(
                    ProvisioningPhase.ADDING,
                    msg,
                    game_account.id,
                    step_index=idx,
                )
            ),
        )
        if not added:
            await self._emit(
                ProvisioningPhase.FAILED,
                "添加账号失败",
                game_account.id,
                status="FAILED",
            )
            return ProvisioningResult(
                success=False,
                phase=ProvisioningPhase.FAILED,
                message="add_failed",
            )

        await self._emit(
            ProvisioningPhase.VERIFYING,
            "校验账号",
            game_account.id,
            step_index=6,
        )
        verified = await self._detector.profile_exists(game_account)
        if not verified:
            await self._emit(
                ProvisioningPhase.FAILED,
                "校验失败",
                game_account.id,
                status="FAILED",
            )
            return ProvisioningResult(
                success=False,
                phase=ProvisioningPhase.FAILED,
                message="verify_failed",
            )

        await self._emit(
            ProvisioningPhase.READY,
            "账号就绪",
            game_account.id,
            step_index=self.STEP_TOTAL,
            status="COMPLETED",
        )
        return ProvisioningResult(
            success=True,
            phase=ProvisioningPhase.READY,
            message="ready",
            step_index=self.STEP_TOTAL,
            step_total=self.STEP_TOTAL,
        )
