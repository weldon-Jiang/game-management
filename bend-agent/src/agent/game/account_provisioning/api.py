"""
AccountProvisioningModule — 每次 GameAction 前的被动门禁。

检测 → 添加（缺失时）→ 校验；用户不可直接启动本模块。
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
    """每任务实例；挂载于 StreamingAccountTaskRuntime.modules。"""

    STEP_TOTAL = 7

    def __init__(
        self,
        task_id: str,
        scene_detector: Any,
        input_sender: Any,
        report_progress: Optional[Callable] = None,
        platform_client: Any = None,
    ):
        self.task_id = task_id
        self.logger = get_logger(f"account_provisioning_{task_id}")
        self._detector = ProfileDetector(scene_detector)
        self._adder = AddAccountFlow(
            scene_detector,
            input_sender,
            platform_client,
        )
        self._report = report_progress
        self._phase = ProvisioningPhase.IDLE

    def refresh_dependencies(
        self,
        scene_detector: Any = None,
        input_sender: Any = None,
        platform_client: Any = None,
        frame_getter: Any = None,
        stream_session: Any = None,
    ) -> None:
        """step3/step4 初始化后延迟绑定检测器/输入。"""
        if scene_detector is not None:
            self._detector._scene = scene_detector
            self._adder._scene = scene_detector
        if input_sender is not None:
            self._adder._input = input_sender
        if platform_client is not None:
            self._adder._platform_client = platform_client
        if frame_getter is not None:
            self._adder._frame_getter = frame_getter
        if stream_session is not None:
            self._adder._stream_session = stream_session

    async def _emit(
        self,
        phase: ProvisioningPhase,
        message: str,
        game_account_id: str,
        step_index: int = 0,
        status: str = "RUNNING",
        *,
        account_status: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> None:
        self._phase = phase
        if not self._report:
            return
        extra: Dict[str, Any] = {
            "scope": "module",
            "module": "account_provisioning",
            "phase": phase.value,
            "game_account_id": game_account_id,
            "stepIndex": step_index,
            "stepTotal": self.STEP_TOTAL,
        }
        if account_status:
            extra["accountStatus"] = account_status
        if error_message:
            extra["errorMessage"] = error_message
        await self._report(
            self.task_id,
            "STEP4",
            status,
            message,
            **extra,
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
                "准备完成（账号已存在）",
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
        if added and game_account.gamertag:
            self.logger.info(
                "主机昵称已同步: %s -> gameAccount %s",
                game_account.gamertag,
                game_account.id,
            )
        if not added:
            await self._emit(
                ProvisioningPhase.FAILED,
                "添加账号失败",
                game_account.id,
                status="FAILED",
                account_status="failed",
                error_message="添加账号失败",
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
                account_status="failed",
                error_message="账号校验失败",
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
