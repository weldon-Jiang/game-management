"""
独立的测试版本 - 不依赖其他模块
用于快速验证测试框架
"""

import pytest
import sys
import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


# === 复制自 task_context.py 的类定义 ===
class TaskStepStatus(Enum):
    """任务步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskMainStatus(Enum):
    """任务主状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GameAccountInfo:
    """游戏账号信息"""
    id: str
    gamertag: str
    email: str = ""
    password: str = ""
    is_primary: bool = False
    target_matches: int = 3


@dataclass
class XboxInfo:
    """Xbox主机信息"""
    id: str = ""
    name: str = ""
    ip_address: str = ""
    live_id: str = ""
    mac_address: str = ""


@dataclass
class WindowInfo:
    """窗口信息"""
    window_id: str
    window_title: str
    handle: Any = None


@dataclass
class StepStatus:
    """步骤执行状态"""
    name: str
    status: TaskStepStatus = TaskStepStatus.PENDING
    message: str = ""
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    duration: Optional[float] = None
    result: Optional[Any] = None

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "message": self.message,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration
        }


class AgentTaskContext:
    """
    Agent任务上下文
    管理单个任务的完整状态和信息
    """
    def __init__(
        self,
        task_id: str,
        streaming_account_id: str,
        streaming_account_email: str,
        streaming_account_password: str,
        window_id: Optional[str] = None,
    ):
        self.task_id = task_id
        self.streaming_account_id = streaming_account_id
        self.streaming_account_email = streaming_account_email
        self.streaming_account_password = streaming_account_password
        self.window_id = window_id or f"window_{task_id}"

        self.task_status = TaskMainStatus.PENDING
        self.current_step = "PENDING"

        self.step1_status = StepStatus("step1")
        self.step2_status = StepStatus("step2")
        self.step3_status = StepStatus("step3")
        self.step4_status = StepStatus("step4")

        self.assigned_xbox: Optional[XboxInfo] = None
        self.current_xbox: Optional[XboxInfo] = None

        self.game_accounts: List[GameAccountInfo] = []
        self.matches_completed_today: Dict[str, int] = {}

        self.created_at = time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None

        import asyncio
        self.pause_event = asyncio.Event()
        self.pause_event.set()
        self.cancel_event = asyncio.Event()

    def is_paused(self) -> bool:
        return not self.pause_event.is_set()

    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def pause(self):
        self.pause_event.clear()
        if self.task_status == TaskMainStatus.RUNNING:
            self.task_status = TaskMainStatus.PAUSED

    def resume(self):
        self.pause_event.set()
        if self.task_status == TaskMainStatus.PAUSED:
            self.task_status = TaskMainStatus.RUNNING

    def cancel(self):
        self.cancel_event.set()
        if self.task_status in [TaskMainStatus.RUNNING, TaskMainStatus.PAUSED]:
            self.task_status = TaskMainStatus.CANCELLED

    def update_task_status(self, status: TaskMainStatus, message: str = ""):
        old_status = self.task_status
        self.task_status = status
        self.current_step = status.value
        if status == TaskMainStatus.RUNNING and not self.started_at:
            self.started_at = time.time()
        if status in [TaskMainStatus.COMPLETED, TaskMainStatus.FAILED, TaskMainStatus.CANCELLED]:
            self.completed_at = time.time()

    def update_step_status(self, step_name: str, status: TaskStepStatus, message: str = ""):
        step_map = {
            "step1": self.step1_status,
            "step2": self.step2_status,
            "step3": self.step3_status,
            "step4": self.step4_status
        }
        if step_name in step_map:
            step = step_map[step_name]
            old_status = step.status

            if old_status in [TaskStepStatus.PENDING, TaskStepStatus.FAILED] and status == TaskStepStatus.RUNNING:
                step.start_time = time.time()

            if old_status == TaskStepStatus.RUNNING and status in [TaskStepStatus.COMPLETED, TaskStepStatus.FAILED, TaskStepStatus.SKIPPED]:
                step.end_time = time.time()
                if step.start_time:
                    step.duration = step.end_time - step.start_time

            step.status = status
            step.message = message

    def get_step_status_dict(self) -> Dict[str, str]:
        return {
            "step1": self.step1_status.status.value if isinstance(self.step1_status.status, Enum) else str(self.step1_status.status),
            "step2": self.step2_status.status.value if isinstance(self.step2_status.status, Enum) else str(self.step2_status.status),
            "step3": self.step3_status.status.value if isinstance(self.step3_status.status, Enum) else str(self.step3_status.status),
            "step4": self.step4_status.status.value if isinstance(self.step4_status.status, Enum) else str(self.step4_status.status)
        }


# === 测试开始 ===

class TestGameAccountInfo:
    """游戏账号信息测试"""

    def test_create_game_account_info(self):
        """测试创建游戏账号信息"""
        ga = GameAccountInfo(
            id="ga_001",
            gamertag="TestPlayer",
            email="test@example.com",
            password="password123",
            is_primary=True,
            target_matches=3
        )

        assert ga.id == "ga_001"
        assert ga.gamertag == "TestPlayer"
        assert ga.email == "test@example.com"
        assert ga.password == "password123"
        assert ga.is_primary is True
        assert ga.target_matches == 3

    def test_default_target_matches(self):
        """测试默认目标比赛数"""
        ga = GameAccountInfo(id="ga_001", gamertag="TestPlayer")
        assert ga.target_matches == 3


class TestAgentTaskContext:
    """Agent任务上下文测试"""

    def test_create_task_context(self):
        """测试创建任务上下文"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        assert context.task_id == "task_001"
        assert context.streaming_account_id == "sa_001"
        assert context.streaming_account_email == "test@example.com"
        assert context.streaming_account_password == "password123"
        assert context.task_status == TaskMainStatus.PENDING
        assert context.current_step == "PENDING"

    def test_update_step_status(self):
        """测试更新步骤状态"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        context.update_step_status("step1", TaskStepStatus.RUNNING, "步骤1执行中")

        assert context.step1_status.status == TaskStepStatus.RUNNING
        assert context.step1_status.message == "步骤1执行中"
        assert context.step1_status.start_time is not None

    def test_get_step_status_dict(self):
        """测试获取步骤状态字典"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        status_dict = context.get_step_status_dict()

        assert "step1" in status_dict
        assert "step2" in status_dict
        assert "step3" in status_dict
        assert "step4" in status_dict
        assert status_dict["step1"] == "pending"

    def test_pause_and_resume(self):
        """测试暂停和恢复"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        assert context.is_paused() is False

        context.pause()
        assert context.is_paused() is True

        context.resume()
        assert context.is_paused() is False


if __name__ == "__main__":
    print("\n" + "="*60)
    print("  独立测试版本 - Agent 自动化模块")
    print("="*60)
    print("\n运行方式:")
    print("  pytest test_standalone.py -v")
    print("\n这个文件不依赖项目其他模块！")
    print("="*60 + "\n")
