"""Unit tests for agent.task.task_context dataclasses and enums."""

import asyncio

import pytest

from agent.task.task_context import (
    AgentTaskContext,
    AutomationResult,
    GameAccountInfo,
    PauseMode,
    Step1Result,
    Step4Result,
    StepStatus,
    TaskMainStatus,
    TaskStepStatus,
    XboxInfo,
)


class TestGameAccountInfo:
    def test_defaults(self):
        account = GameAccountInfo(id="ga-1", gamertag="tester")
        assert account.target_matches == 3
        assert account.today_match_count == 0
        assert account.is_primary is False


class TestXboxInfo:
    def test_lan_fields(self):
        xbox = XboxInfo(id="gssv-1", platform_host_id="host-1", ip_address="192.168.1.10")
        assert xbox.platform_host_id == "host-1"
        assert xbox.ip_address == "192.168.1.10"


class TestAgentTaskContext:
    def test_pause_event_initialized(self):
        context = AgentTaskContext(
            task_id="task-1",
            streaming_account_id="sa-1",
            streaming_account_email="a@example.com",
            streaming_account_password="secret",
        )
        assert context.pause_event is not None
        assert context.pause_event.is_set()

    def test_update_step_status_running_sets_start_time(self):
        context = AgentTaskContext(
            task_id="task-1",
            streaming_account_id="sa-1",
            streaming_account_email="a@example.com",
            streaming_account_password="secret",
        )
        context.update_step_status("step1", TaskStepStatus.RUNNING, message="starting")
        assert context.step1_status.status == TaskStepStatus.RUNNING
        assert context.step1_status.start_time is not None
        assert context.step1_status.message == "starting"

    def test_pause_and_resume(self):
        context = AgentTaskContext(
            task_id="task-1",
            streaming_account_id="sa-1",
            streaming_account_email="a@example.com",
            streaming_account_password="secret",
        )
        context.pause()
        assert context.is_paused()
        assert context.task_status == TaskMainStatus.PAUSED

        context.resume()
        assert not context.is_paused()
        assert context.task_status == TaskMainStatus.RUNNING

    @pytest.mark.asyncio
    async def test_wait_if_paused_unblocks_after_resume(self):
        context = AgentTaskContext(
            task_id="task-1",
            streaming_account_id="sa-1",
            streaming_account_email="a@example.com",
            streaming_account_password="secret",
        )
        context.pause()

        async def resume_later():
            await asyncio.sleep(0.05)
            context.resume()

        waiter = asyncio.create_task(context.wait_if_paused())
        resumer = asyncio.create_task(resume_later())
        await asyncio.wait_for(asyncio.gather(waiter, resumer), timeout=2)


class TestStepStatus:
    def test_to_dict(self):
        step = StepStatus(name="STEP1", status=TaskStepStatus.COMPLETED, message="ok")
        payload = step.to_dict()
        assert payload["name"] == "STEP1"
        assert payload["status"] == "completed"
        assert payload["message"] == "ok"


class TestAutomationResult:
    def test_failure_fields(self):
        result = AutomationResult(
            success=False,
            failed_step="STEP2",
            message="connection failed",
            error_code="XBOX_OFFLINE",
        )
        assert result.success is False
        assert result.failed_step == "STEP2"
        assert result.error_code == "XBOX_OFFLINE"


class TestStepResults:
    def test_step1_result(self):
        result = Step1Result(success=True, message="logged in")
        assert result.success is True

    def test_step4_result(self):
        result = Step4Result(success=True, total_matches=3)
        assert result.total_matches == 3


class TestTaskEnums:
    def test_pause_mode_values(self):
        assert PauseMode.IMMEDIATE.value == "immediate"
        assert PauseMode.AFTER_MATCH.value == "after_match"

    def test_main_status_values(self):
        assert TaskMainStatus.RUNNING.value == "running"
        assert TaskMainStatus.CANCELLED.value == "cancelled"
