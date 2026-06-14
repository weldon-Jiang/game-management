"""Lightweight scheduler-related tests (no AutomationScheduler import — avoids heavy deps on CI)."""

from agent.task.task_context import AgentTaskContext, AutomationResult, TaskMainStatus


class TestAutomationSchedulerState:
    def test_task_context_status_lookup(self):
        contexts = {}
        context = AgentTaskContext(
            task_id="task-1",
            streaming_account_id="sa-1",
            streaming_account_email="a@example.com",
            streaming_account_password="secret",
        )
        context.update_task_status(TaskMainStatus.RUNNING)
        contexts["task-1"] = context

        assert contexts.get("task-1").task_status.value == "running"

    def test_task_results_map(self):
        results = {}
        results["task-1"] = AutomationResult(success=True, message="done")
        assert results["task-1"].success is True


class TestTaskContextCreation:
    def test_context_defaults_for_streaming_session(self):
        context = AgentTaskContext(
            task_id="task-1",
            streaming_account_id="sa-1",
            streaming_account_email="a@example.com",
            streaming_account_password="secret",
        )
        assert context.session_phase == "opening"
        assert context.game_action_type == ""
        assert context.auto_match_host is True
