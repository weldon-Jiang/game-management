"""
使用Mock服务器的集成测试
=========================

测试Agent与Platform API的集成交互

作者：技术团队
版本：1.0
"""

import pytest
import asyncio
from unittest.mock import patch
from agent.automation.platform_api_client import PlatformApiClient
from agent.automation.tests.mock_server import MockPlatformServer, create_mock_server


@pytest.fixture
async def mock_server():
    """Mock服务器fixture"""
    server = await create_mock_server(port=8889)

    server.set_task("test_task_001", {
        "id": "test_task_001",
        "streamingAccountId": "sa_001"
    })

    server.set_game_accounts("sa_001", [
        {"id": "ga_001", "gamertag": "Player1", "completedCount": 0, "targetMatches": 3},
        {"id": "ga_002", "gamertag": "Player2", "completedCount": 0, "targetMatches": 3}
    ])

    yield server

    await server.stop()


@pytest.fixture
def api_client(mock_server):
    """API客户端fixture"""
    return PlatformApiClient(base_url="http://localhost:8889/api")


class TestWithMockServer:
    """使用Mock服务器的测试"""

    @pytest.mark.asyncio
    async def test_get_game_accounts_status_with_mock(self, api_client, mock_server):
        """测试获取游戏账号状态"""
        result = await api_client.get_game_accounts_status("test_task_001")

        assert result is not None
        assert "ga_001" in result
        assert "ga_002" in result
        assert result["ga_001"]["gamertag"] == "Player1"
        assert result["ga_001"]["completedCount"] == 0
        assert result["ga_001"]["targetMatches"] == 3

    @pytest.mark.asyncio
    async def test_report_match_complete_with_mock(self, api_client, mock_server):
        """测试上报比赛完成"""
        await api_client.report_match_complete(
            task_id="test_task_001",
            game_account_id="ga_001",
            completed_count=1
        )

        match_reports = mock_server.get_match_reports()
        assert len(match_reports) == 1
        assert match_reports[0]["gameAccountId"] == "ga_001"
        assert match_reports[0]["completedCount"] == 1

    @pytest.mark.asyncio
    async def test_multiple_match_reports_with_mock(self, api_client, mock_server):
        """测试多次上报比赛完成"""
        await api_client.report_match_complete("test_task_001", "ga_001", 1)
        await api_client.report_match_complete("test_task_001", "ga_001", 2)
        await api_client.report_match_complete("test_task_001", "ga_001", 3)

        match_reports = mock_server.get_match_reports()
        assert len(match_reports) == 3

        result = await api_client.get_game_accounts_status("test_task_001")
        assert result["ga_001"]["completedCount"] == 3

    @pytest.mark.asyncio
    async def test_report_task_progress_with_mock(self, api_client, mock_server):
        """测试上报任务进度"""
        await api_client.report_task_progress(
            task_id="test_task_001",
            step="STEP1",
            status="RUNNING",
            message="登录中"
        )

        await api_client.report_task_progress(
            task_id="test_task_001",
            step="STEP1",
            status="COMPLETED",
            message="登录完成"
        )

        progress_reports = mock_server.get_progress_reports()
        assert len(progress_reports) == 2
        assert progress_reports[0]["step"] == "STEP1"
        assert progress_reports[0]["status"] == "RUNNING"
        assert progress_reports[1]["status"] == "COMPLETED"

    @pytest.mark.asyncio
    async def test_all_accounts_completed_with_mock(self, api_client, mock_server):
        """测试所有账号完成"""
        await api_client.report_match_complete("test_task_001", "ga_001", 3)
        await api_client.report_match_complete("test_task_001", "ga_002", 3)

        result = await api_client.get_game_accounts_status("test_task_001")

        assert result["ga_001"]["completed"] is True
        assert result["ga_002"]["completed"] is True


class TestMockServerReset:
    """Mock服务器重置测试"""

    @pytest.mark.asyncio
    async def test_mock_server_reset(self, api_client, mock_server):
        """测试Mock服务器重置"""
        await api_client.report_task_progress(
            task_id="test_task_001",
            step="STEP1",
            status="RUNNING",
            message="测试"
        )

        assert len(mock_server.get_progress_reports()) == 1

        mock_server.reset()

        assert len(mock_server.get_progress_reports()) == 0
        assert len(mock_server.get_match_reports()) == 0
