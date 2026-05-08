"""
平台API客户端单元测试
====================

测试Platform API客户端的数据获取和上报功能

作者：技术团队
版本：1.0
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from agent.automation.platform_api_client import PlatformApiClient, ProgressReporter


class TestPlatformApiClient:
    """Platform API客户端测试"""

    @pytest.fixture
    def client(self):
        """创建测试客户端"""
        return PlatformApiClient(base_url="http://localhost:8080/api")

    def test_init(self, client):
        """测试初始化"""
        assert client.base_url == "http://localhost:8080/api"
        assert client._retry_count == 3
        assert client._retry_delay == 1.0

    @pytest.mark.asyncio
    async def test_get_game_accounts_status_success(self, client):
        """测试获取游戏账号状态成功"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "code": 200,
            "data": [
                {
                    "id": "ga_001",
                    "gamertag": "Player1",
                    "completedCount": 2,
                    "targetMatches": 3,
                    "completed": False
                },
                {
                    "id": "ga_002",
                    "gamertag": "Player2",
                    "completedCount": 3,
                    "targetMatches": 3,
                    "completed": True
                }
            ]
        })

        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await client.get_game_accounts_status("task_001")

            assert "ga_001" in result
            assert "ga_002" in result
            assert result["ga_001"]["gamertag"] == "Player1"
            assert result["ga_001"]["completedCount"] == 2

    @pytest.mark.asyncio
    async def test_get_game_accounts_status_empty(self, client):
        """测试获取游戏账号状态为空"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "code": 200,
            "data": []
        })

        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await client.get_game_accounts_status("task_001")

            assert result == {}

    @pytest.mark.asyncio
    async def test_report_match_complete_success(self, client):
        """测试上报比赛完成成功"""
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={
            "code": 200,
            "data": {
                "allAccounts": [
                    {"id": "ga_001", "completedCount": 3, "completed": True}
                ],
                "allCompleted": True
            }
        })

        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await client.report_match_complete(
                task_id="task_001",
                game_account_id="ga_001",
                completed_count=3
            )

            assert result is not None
            assert result["allCompleted"] is True

    @pytest.mark.asyncio
    async def test_report_match_complete_failure(self, client):
        """测试上报比赛完成失败"""
        mock_response = Mock()
        mock_response.status = 500

        with patch.object(client, '_get_session') as mock_session:
            mock_session.return_value.__aenter__.return_value.post = AsyncMock(return_value=mock_response)

            result = await client.report_match_complete(
                task_id="task_001",
                game_account_id="ga_001",
                completed_count=3
            )

            assert result is None

    @pytest.mark.asyncio
    async def test_report_task_progress_success(self, client):
        """测试上报任务进度成功"""
        with patch('agent.automation.platform_api_client.websocket_client') as mock_ws:
            mock_ws._running = True
            mock_ws.send = AsyncMock()

            await client.report_task_progress(
                task_id="task_001",
                step="STEP1",
                status="RUNNING",
                message="登录中"
            )

            mock_ws.send.assert_called_once()
            call_args = mock_ws.send.call_args[0]
            assert call_args[0] == "task_progress"
            assert call_args[1]["taskId"] == "task_001"
            assert call_args[1]["step"] == "STEP1"

    @pytest.mark.asyncio
    async def test_report_task_error_success(self, client):
        """测试上报任务错误成功"""
        with patch('agent.automation.platform_api_client.websocket_client') as mock_ws:
            mock_ws._running = True
            mock_ws.send = AsyncMock()

            await client.report_task_error(
                task_id="task_001",
                step="STEP2",
                error_code="XBOX_CONNECT_FAILED",
                error_message="Xbox连接失败"
            )

            mock_ws.send.assert_called_once()
            call_args = mock_ws.send.call_args[0]
            assert call_args[0] == "task_error"
            assert call_args[1]["errorCode"] == "XBOX_CONNECT_FAILED"


class TestProgressReporter:
    """进度上报器测试"""

    @pytest.fixture
    def mock_client(self):
        """创建模拟客户端"""
        return Mock(spec=PlatformApiClient)

    def test_init(self, mock_client):
        """测试初始化"""
        reporter = ProgressReporter(mock_client)
        assert reporter.platform_client == mock_client

    @pytest.mark.asyncio
    async def test_report(self, mock_client):
        """测试上报"""
        reporter = ProgressReporter(mock_client)
        mock_client.report_task_progress = AsyncMock()

        await reporter.report(
            task_id="task_001",
            step="STEP1",
            status="RUNNING",
            message="测试消息"
        )

        mock_client.report_task_progress.assert_called_once_with(
            "task_001", "STEP1", "RUNNING", "测试消息"
        )

    @pytest.mark.asyncio
    async def test_report_error(self, mock_client):
        """测试上报错误"""
        reporter = ProgressReporter(mock_client)
        mock_client.report_task_error = AsyncMock()

        await reporter.report_error(
            task_id="task_001",
            step="STEP2",
            error_code="FAILED",
            error_message="测试错误"
        )

        mock_client.report_task_error.assert_called_once_with(
            "task_001", "STEP2", "FAILED", "测试错误", None
        )
