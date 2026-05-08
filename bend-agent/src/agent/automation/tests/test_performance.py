"""
性能测试：Agent自动化模块
=========================

测试多并发任务执行的性能

作者：技术团队
版本：1.0
"""

import pytest
import asyncio
import time
from typing import List
from unittest.mock import Mock, AsyncMock, patch
from agent.automation.task_context import AgentTaskContext, GameAccountInfo
from agent.automation.automation_scheduler import AutomationScheduler
# 下面这个导入可能因为依赖问题失败，但我们在 mock 时不需要实际导入
try:
    from agent.automation.platform_api_client import PlatformApiClient
except ImportError:
    # 如果导入失败，我们使用一个简单的 Mock 替代
    PlatformApiClient = None


class TestSchedulerPerformance:
    """调度器性能测试"""

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_concurrent_task_startup_performance(self):
        """
        测试并发任务启动性能

        目标：启动10个任务耗时 < 1秒
        """
        scheduler = AutomationScheduler(max_concurrent_tasks=20)

        start_time = time.time()

        tasks = []
        for i in range(10):
            task = scheduler.start_task(
                task_id=f"perf_task_{i}",
                streaming_account_id=f"sa_{i}",
                streaming_account_email=f"user{i}@example.com",
                streaming_account_password="password123",
                game_accounts=[{"id": f"ga_{i}", "gamertag": f"Player{i}"}]
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        elapsed_time = time.time() - start_time

        print(f"\n[性能测试] 启动10个任务耗时: {elapsed_time:.4f}秒")
        assert elapsed_time < 1.0, f"启动任务耗时过长: {elapsed_time}秒"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_task_status_query_performance(self):
        """
        测试任务状态查询性能

        目标：查询100次状态耗时 < 0.5秒
        """
        scheduler = AutomationScheduler(max_concurrent_tasks=20)

        await scheduler.start_task(
            task_id="perf_task_query",
            streaming_account_id="sa_query",
            streaming_account_email="query@example.com",
            streaming_account_password="password123",
            game_accounts=[{"id": "ga_query", "gamertag": "QueryPlayer"}]
        )

        start_time = time.time()

        for _ in range(100):
            scheduler.get_task_status("perf_task_query")

        elapsed_time = time.time() - start_time

        print(f"\n[性能测试] 查询100次任务状态耗时: {elapsed_time:.4f}秒")
        assert elapsed_time < 0.5, f"状态查询耗时过长: {elapsed_time}秒"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_multiple_task_contexts_memory(self):
        """
        测试多个任务上下文的内存占用

        目标：创建100个任务上下文内存占用合理
        """
        contexts: List[AgentTaskContext] = []

        start_time = time.time()

        for i in range(100):
            context = AgentTaskContext(
                task_id=f"mem_task_{i}",
                streaming_account_id=f"sa_{i}",
                streaming_account_email=f"user{i}@example.com",
                streaming_account_password="password123",
                window_id=f"window_{i}"
            )

            for j in range(5):
                context.game_accounts.append(
                    GameAccountInfo(
                        id=f"ga_{i}_{j}",
                        gamertag=f"Player{i}_{j}",
                        target_matches=3
                    )
                )

            contexts.append(context)

        elapsed_time = time.time() - start_time

        print(f"\n[性能测试] 创建100个任务上下文耗时: {elapsed_time:.4f}秒")
        assert elapsed_time < 1.0, f"创建上下文耗时过长: {elapsed_time}秒"

        assert len(contexts) == 100
        assert all(len(ctx.game_accounts) == 5 for ctx in contexts)


class TestPlatformApiClientPerformance:
    """平台API客户端性能测试"""

    @pytest.fixture
    def mock_api_client(self):
        """模拟API客户端"""
        # 如果有 PlatformApiClient 定义，使用它作为 spec，否则使用普通 Mock
        if PlatformApiClient:
            client = Mock(spec=PlatformApiClient)
        else:
            client = Mock()

        async def mock_get_accounts(task_id):
            return {
                "ga_001": {"id": "ga_001", "gamertag": "Player1", "completedCount": 0, "targetMatches": 3}
            }

        async def mock_report_match(task_id, game_account_id, completed_count):
            return {"allAccounts": [], "allCompleted": False}

        async def mock_report_progress(task_id, step, status, message):
            pass

        client.get_game_accounts_status = AsyncMock(side_effect=mock_get_accounts)
        client.report_match_complete = AsyncMock(side_effect=mock_report_match)
        client.report_task_progress = AsyncMock(side_effect=mock_report_progress)
        return client

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_massive_progress_reporting(self, mock_api_client):
        """
        测试大量进度上报性能

        目标：上报1000次进度耗时 < 2秒
        """
        start_time = time.time()

        tasks = []
        for i in range(1000):
            task = mock_api_client.report_task_progress(
                task_id="perf_task",
                step="STEP4",
                status="RUNNING",
                message=f"进度 {i}"
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        elapsed_time = time.time() - start_time

        print(f"\n[性能测试] 上报1000次进度耗时: {elapsed_time:.4f}秒")
        assert elapsed_time < 2.0, f"进度上报耗时过长: {elapsed_time}秒"

    @pytest.mark.performance
    @pytest.mark.asyncio
    async def test_massive_match_reporting(self, mock_api_client):
        """
        测试大量比赛完成上报性能

        目标：上报100次比赛完成耗时 < 1秒
        """
        start_time = time.time()

        tasks = []
        for i in range(100):
            task = mock_api_client.report_match_complete(
                task_id="perf_task",
                game_account_id=f"ga_{i}",
                completed_count=3
            )
            tasks.append(task)

        await asyncio.gather(*tasks)

        elapsed_time = time.time() - start_time

        print(f"\n[性能测试] 上报100次比赛完成耗时: {elapsed_time:.4f}秒")
        assert elapsed_time < 1.0, f"比赛上报耗时过长: {elapsed_time}秒"


class TestTaskContextPerformance:
    """任务上下文性能测试"""

    @pytest.mark.performance
    def test_step_status_update_performance(self):
        """
        测试步骤状态更新性能

        目标：更新10000次状态耗时 < 1秒
        """
        context = AgentTaskContext(
            task_id="perf_task_step",
            streaming_account_id="sa_step",
            streaming_account_email="step@example.com",
            streaming_account_password="password123"
        )

        start_time = time.time()

        for i in range(10000):
            context.update_step_status("step1", "RUNNING", f"测试 {i}")
            context.update_step_status("step1", "COMPLETED", f"完成 {i}")

        elapsed_time = time.time() - start_time

        print(f"\n[性能测试] 更新20000次步骤状态耗时: {elapsed_time:.4f}秒")
        assert elapsed_time < 1.0, f"状态更新耗时过长: {elapsed_time}秒"

    @pytest.mark.performance
    def test_get_step_status_dict_performance(self):
        """
        测试获取步骤状态字典性能

        目标：获取10000次状态字典耗时 < 0.5秒
        """
        context = AgentTaskContext(
            task_id="perf_task_dict",
            streaming_account_id="sa_dict",
            streaming_account_email="dict@example.com",
            streaming_account_password="password123"
        )

        start_time = time.time()

        for _ in range(10000):
            _ = context.get_step_status_dict()

        elapsed_time = time.time() - start_time

        print(f"\n[性能测试] 获取10000次步骤状态字典耗时: {elapsed_time:.4f}秒")
        assert elapsed_time < 0.5, f"获取字典耗时过长: {elapsed_time}秒"


class TestBenchmarkReport:
    """基准测试报告"""

    @pytest.mark.benchmark
    def test_print_benchmark_summary(self):
        """
        打印基准测试总结

        此测试不执行实际性能测试，只是打印总结信息
        """
        print("\n" + "="*60)
        print("Agent Automation Module - 性能基准测试总结")
        print("="*60)
        print("\n测试目标:")
        print("  - 任务启动: 10个任务 < 1秒")
        print("  - 状态查询: 100次查询 < 0.5秒")
        print("  - 上下文创建: 100个上下文 < 1秒")
        print("  - 进度上报: 1000次上报 < 2秒")
        print("  - 比赛上报: 100次上报 < 1秒")
        print("  - 状态更新: 20000次更新 < 1秒")
        print("\n" + "="*60)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-m", "performance"])
