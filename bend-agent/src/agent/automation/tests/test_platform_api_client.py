"""Unit tests for PlatformApiClient helpers and ProgressReporter wiring."""

import pytest

from agent.api.platform_api_client import (
    PlatformApiClient,
    ProgressReporter,
    _normalize_progress_fields,
)


class TestNormalizeProgressFields:
    def test_maps_camel_case_aliases(self):
        normalized = _normalize_progress_fields(
            {
                "gameAccountId": "ga-1",
                "todayCompleted": 2,
                "dailyLimit": 3,
                "errorCode": "E001",
                "errorDetails": "detail",
            }
        )
        assert normalized["game_account_id"] == "ga-1"
        assert normalized["today_completed"] == 2
        assert normalized["daily_limit"] == 3
        assert normalized["error_code"] == "E001"
        assert normalized["error_details"] == "detail"

    def test_keeps_existing_snake_case(self):
        normalized = _normalize_progress_fields(
            {"game_account_id": "ga-1", "gameAccountId": "ga-2"}
        )
        assert normalized["game_account_id"] == "ga-1"
        assert normalized["gameAccountId"] == "ga-2"


class TestPlatformApiClient:
    def test_init_with_explicit_credentials(self):
        client = PlatformApiClient(
            base_url="http://localhost:8060/api",
            agent_id="agent-1",
            agent_secret="secret",
        )
        assert client.base_url == "http://localhost:8060/api"
        assert client._agent_id == "agent-1"
        assert client._agent_secret == "secret"

    def test_set_credentials(self):
        client = PlatformApiClient(base_url="http://localhost:8060/api")
        client.set_credentials("agent-2", "secret-2")
        assert client._agent_id == "agent-2"
        assert client._agent_secret == "secret-2"


class TestProgressReporter:
    @pytest.mark.asyncio
    async def test_report_delegates_to_client(self, monkeypatch):
        calls = []

        async def fake_report_progress(task_id, step, status, message, **kwargs):
            calls.append((task_id, step, status, message, kwargs))
            return True

        client = PlatformApiClient(base_url="http://localhost:8060/api")
        monkeypatch.setattr(client, "report_progress", fake_report_progress)

        reporter = ProgressReporter(client)
        await reporter.report("task-1", "STEP1", "RUNNING", "starting", gameAccountId="ga-1")

        assert len(calls) == 1
        task_id, step, status, message, kwargs = calls[0]
        assert task_id == "task-1"
        assert step == "STEP1"
        assert status == "RUNNING"
        assert message == "starting"
        assert kwargs["gameAccountId"] == "ga-1"
