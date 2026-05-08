"""
任务调度器单元测试
==================

测试任务调度器的任务启动、暂停、恢复、停止等功能

作者：技术团队
版本：1.0
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from agent.automation.automation_scheduler import AutomationScheduler
from agent.automation.task_context import AgentTaskContext, GameAccountInfo


class TestAutomationScheduler:
    """自动化任务调度器测试"""

    @pytest.fixture
    def scheduler(self):
        """创建测试调度器"""
        return AutomationScheduler(max_concurrent_tasks=5)

    def test_init(self, scheduler):
        """测试初始化"""
        assert scheduler._max_concurrent == 5
        assert scheduler._semaphore._value == 5
        assert len(scheduler._running_tasks) == 0
        assert len(scheduler._task_contexts) == 0

    @pytest.mark.asyncio
    async def test_start_task_success(self, scheduler):
        """测试成功启动任务"""
        with patch.object(scheduler, '_run_task', new_callable=AsyncMock):
            result = await scheduler.start_task(
                task_id="task_001",
                streaming_account_id="sa_001",
                streaming_account_email="test@example.com",
                streaming_account_password="password123",
                game_accounts=[
                    {"id": "ga_001", "gamertag": "Player1", "targetMatches": 3}
                ]
            )

            assert result is True
            assert "task_001" in scheduler._task_contexts

    @pytest.mark.asyncio
    async def test_start_task_duplicate(self, scheduler):
        """测试重复启动任务"""
        with patch.object(scheduler, '_run_task', new_callable=AsyncMock):
            await scheduler.start_task(
                task_id="task_001",
                streaming_account_id="sa_001",
                streaming_account_email="test@example.com",
                streaming_account_password="password123",
                game_accounts=[]
            )

            result = await scheduler.start_task(
                task_id="task_001",
                streaming_account_id="sa_001",
                streaming_account_email="test@example.com",
                streaming_account_password="password123",
                game_accounts=[]
            )

            assert result is False

    def test_get_task_status(self, scheduler):
        """测试获取任务状态"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )
        scheduler._task_contexts["task_001"] = context

        status = scheduler.get_task_status("task_001")
        assert status == "pending"

    def test_get_task_status_not_found(self, scheduler):
        """测试获取不存在的任务状态"""
        status = scheduler.get_task_status("non_existent")
        assert status is None

    def test_get_task_result_not_found(self, scheduler):
        """测试获取不存在的任务结果"""
        result = scheduler.get_task_result("non_existent")
        assert result is None

    def test_get_running_task_count_empty(self, scheduler):
        """测试获取运行中任务数量（空）"""
        assert scheduler.get_running_task_count() == 0

    def test_get_running_task_count_with_tasks(self, scheduler):
        """测试获取运行中任务数量"""
        scheduler._running_tasks["task_001"] = Mock()
        scheduler._running_tasks["task_002"] = Mock()
        assert scheduler.get_running_task_count() == 2

    def test_get_all_task_ids(self, scheduler):
        """测试获取所有任务ID"""
        scheduler._task_contexts["task_001"] = Mock()
        scheduler._task_contexts["task_002"] = Mock()

        task_ids = scheduler.get_all_task_ids()

        assert "task_001" in task_ids
        assert "task_002" in task_ids
        assert len(task_ids) == 2


class TestTaskContextCreation:
    """任务上下文创建测试"""

    @pytest.mark.asyncio
    async def test_create_task_context_from_params(self):
        """测试从参数创建任务上下文"""
        scheduler = AutomationScheduler()

        await scheduler.start_task(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123",
            game_accounts=[
                {
                    "id": "ga_001",
                    "gamertag": "Player1",
                    "email": "player1@example.com",
                    "password": "player123",
                    "isPrimary": True,
                    "targetMatches": 3
                },
                {
                    "id": "ga_002",
                    "gamertag": "Player2",
                    "email": "player2@example.com",
                    "password": "player456",
                    "isPrimary": False,
                    "targetMatches": 5
                }
            ],
            assigned_xbox={
                "id": "xbox_001",
                "name": "MyXbox",
                "ipAddress": "192.168.1.100",
                "liveId": "ABC123",
                "macAddress": "00:11:22:33:44:55"
            }
        )

        context = scheduler._task_contexts["task_001"]

        assert context.task_id == "task_001"
        assert context.streaming_account_id == "sa_001"
        assert context.streaming_account_email == "test@example.com"
        assert context.streaming_account_password == "password123"
        assert context.window_id == "window_task_001"

        assert len(context.game_accounts) == 2
        assert context.game_accounts[0].gamertag == "Player1"
        assert context.game_accounts[0].is_primary is True
        assert context.game_accounts[0].target_matches == 3
        assert context.game_accounts[1].gamertag == "Player2"
        assert context.game_accounts[1].target_matches == 5

        assert context.assigned_xbox is not None
        assert context.assigned_xbox.name == "MyXbox"
        assert context.assigned_xbox.ip_address == "192.168.1.100"

        assert "task_001" in scheduler._cancel_events
        assert scheduler._cancel_events["task_001"].is_set() is True
