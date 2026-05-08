"""
集成测试：自动化任务完整流程
=============================

测试从任务创建到完成的完整流程

作者：技术团队
版本：1.0
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from agent.automation.task_context import (
    AgentTaskContext,
    GameAccountInfo,
    TaskMainStatus,
    TaskStepStatus
)
from agent.automation.automation_scheduler import AutomationScheduler


class TestAutomationFlow:
    """自动化任务流程集成测试"""

    @pytest.fixture
    def scheduler(self):
        """创建测试调度器"""
        return AutomationScheduler(max_concurrent_tasks=3)

    @pytest.fixture
    def task_context(self):
        """创建测试任务上下文"""
        context = AgentTaskContext(
            task_id="test_task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123",
            window_id="window_test_task_001"
        )
        context.game_accounts = [
            GameAccountInfo(
                id="ga_001",
                gamertag="TestPlayer1",
                target_matches=3
            ),
            GameAccountInfo(
                id="ga_002",
                gamertag="TestPlayer2",
                target_matches=3
            )
        ]
        return context

    def test_task_context_creation(self, task_context):
        """测试任务上下文创建"""
        assert task_context.task_id == "test_task_001"
        assert task_context.streaming_account_email == "test@example.com"
        assert len(task_context.game_accounts) == 2
        assert task_context.game_accounts[0].gamertag == "TestPlayer1"

    def test_task_status_transitions(self, task_context):
        """测试任务状态转换"""
        assert task_context.task_status == TaskMainStatus.PENDING

        task_context.update_task_status(TaskMainStatus.RUNNING)
        assert task_context.task_status == TaskMainStatus.RUNNING

        task_context.update_task_status(TaskMainStatus.PAUSED)
        assert task_context.task_status == TaskMainStatus.PAUSED

        task_context.update_task_status(TaskMainStatus.COMPLETED)
        assert task_context.task_status == TaskMainStatus.COMPLETED

    def test_step_status_transitions(self, task_context):
        """测试步骤状态转换"""
        assert task_context.step1_status.status == TaskStepStatus.PENDING

        task_context.update_step_status("step1", TaskStepStatus.RUNNING, "执行中")
        assert task_context.step1_status.status == TaskStepStatus.RUNNING
        assert task_context.step1_status.start_time is not None

        task_context.update_step_status("step1", TaskStepStatus.COMPLETED, "完成")
        assert task_context.step1_status.status == TaskStepStatus.COMPLETED
        assert task_context.step1_status.end_time is not None

    def test_pause_resume_mechanism(self, task_context):
        """测试暂停恢复机制"""
        task_context.update_task_status(TaskMainStatus.RUNNING)

        assert task_context.is_paused() is False

        task_context.pause()
        assert task_context.is_paused() is True
        assert task_context.task_status == TaskMainStatus.PAUSED

        task_context.resume()
        assert task_context.is_paused() is False
        assert task_context.task_status == TaskMainStatus.RUNNING

    def test_all_steps_status_dict(self, task_context):
        """测试所有步骤状态字典"""
        status_dict = task_context.get_step_status_dict()

        assert status_dict["step1"] == "pending"
        assert status_dict["step2"] == "pending"
        assert status_dict["step3"] == "pending"
        assert status_dict["step4"] == "pending"

        task_context.update_step_status("step1", TaskStepStatus.COMPLETED)
        task_context.update_step_status("step2", TaskStepStatus.RUNNING)
        task_context.update_step_status("step3", TaskStepStatus.PENDING)
        task_context.update_step_status("step4", TaskStepStatus.PENDING)

        status_dict = task_context.get_step_status_dict()

        assert status_dict["step1"] == "completed"
        assert status_dict["step2"] == "running"
        assert status_dict["step3"] == "pending"
        assert status_dict["step4"] == "pending"

    @pytest.mark.asyncio
    async def test_scheduler_start_task(self, scheduler):
        """测试调度器启动任务"""
        result = await scheduler.start_task(
            task_id="int_test_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123",
            game_accounts=[
                {"id": "ga_001", "gamertag": "Player1"}
            ]
        )

        assert result is True
        assert "int_test_001" in scheduler._task_contexts

    @pytest.mark.asyncio
    async def test_multiple_task_contexts_independent(self, scheduler):
        """测试多个任务上下文相互独立"""
        await scheduler.start_task(
            task_id="int_test_001",
            streaming_account_id="sa_001",
            streaming_account_email="test1@example.com",
            streaming_account_password="password123",
            game_accounts=[{"id": "ga_001", "gamertag": "Player1"}]
        )

        await scheduler.start_task(
            task_id="int_test_002",
            streaming_account_id="sa_002",
            streaming_account_email="test2@example.com",
            streaming_account_password="password456",
            game_accounts=[{"id": "ga_002", "gamertag": "Player2"}]
        )

        ctx1 = scheduler._task_contexts["int_test_001"]
        ctx2 = scheduler._task_contexts["int_test_002"]

        assert ctx1.streaming_account_email == "test1@example.com"
        assert ctx2.streaming_account_email == "test2@example.com"

        ctx1.pause()
        assert ctx1.is_paused() is True
        assert ctx2.is_paused() is False


class TestGameAccountProgressTracking:
    """游戏账号进度跟踪集成测试"""

    def test_matches_completed_tracking(self):
        """测试比赛完成数跟踪"""
        context = AgentTaskContext(
            task_id="test_task",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password"
        )

        context.matches_completed_today = {
            "ga_001": 0,
            "ga_002": 0
        }

        context.matches_completed_today["ga_001"] += 1
        assert context.matches_completed_today["ga_001"] == 1

        context.matches_completed_today["ga_001"] += 1
        assert context.matches_completed_today["ga_001"] == 2

        context.matches_completed_today["ga_002"] += 1
        assert context.matches_completed_today["ga_002"] == 1

    def test_check_all_accounts_completed(self):
        """测试检查所有账号是否完成"""
        context = AgentTaskContext(
            task_id="test_task",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password"
        )

        context.game_accounts = [
            GameAccountInfo(id="ga_001", gamertag="Player1", target_matches=3),
            GameAccountInfo(id="ga_002", gamertag="Player2", target_matches=3)
        ]

        context.matches_completed_today = {
            "ga_001": 3,
            "ga_002": 2
        }

        all_completed = all(
            context.matches_completed_today[ga.id] >= ga.target_matches
            for ga in context.game_accounts
        )
        assert all_completed is False

        context.matches_completed_today["ga_002"] = 3

        all_completed = all(
            context.matches_completed_today[ga.id] >= ga.target_matches
            for ga in context.game_accounts
        )
        assert all_completed is True
