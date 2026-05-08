"""
Mock Platform API Server
=======================

用于Agent自动化模块测试的Mock服务器

作者：技术团队
版本：1.0
"""

from aiohttp import web
import json
import logging
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


class MockPlatformServer:
    """
    Mock Platform服务器

    提供以下API：
    - GET /api/task/{taskId}/game-accounts/status
    - POST /api/task/{taskId}/match/complete
    - POST /api/task/{taskId}/progress
    """

    def __init__(self, host: str = "localhost", port: int = 8888):
        self.host = host
        self.port = port
        self.app = web.Application()
        self._setup_routes()
        self._tasks: Dict[str, Dict] = {}
        self._game_accounts: Dict[str, Dict] = {}
        self._progress_reports: List[Dict] = []
        self._match_reports: List[Dict] = []
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None

    def _setup_routes(self):
        """设置路由"""
        self.app.router.add_get('/api/task/{taskId}/game-accounts/status', self.get_game_accounts_status)
        self.app.router.add_post('/api/task/{taskId}/match/complete', self.report_match_complete)
        self.app.router.add_post('/api/task/{taskId}/progress', self.report_task_progress)

    def set_task(self, task_id: str, task_data: Dict):
        """设置任务数据"""
        self._tasks[task_id] = task_data

    def set_game_accounts(self, streaming_account_id: str, accounts: List[Dict]):
        """设置游戏账号数据"""
        self._game_accounts[streaming_account_id] = accounts

    def get_progress_reports(self) -> List[Dict]:
        """获取所有进度上报"""
        return self._progress_reports

    def get_match_reports(self) -> List[Dict]:
        """获取所有比赛完成上报"""
        return self._match_reports

    def reset(self):
        """重置所有数据"""
        self._tasks = {}
        self._game_accounts = {}
        self._progress_reports = []
        self._match_reports = []

    async def get_game_accounts_status(self, request):
        """获取游戏账号状态"""
        task_id = request.match_info['taskId']

        if task_id not in self._tasks:
            return web.json_response({
                "code": 404,
                "message": "Task not found"
            }, status=404)

        task = self._tasks[task_id]
        streaming_account_id = task.get('streamingAccountId')

        if not streaming_account_id or streaming_account_id not in self._game_accounts:
            return web.json_response({
                "code": 200,
                "data": []
            })

        accounts = self._game_accounts[streaming_account_id]

        formatted_accounts = []
        for acc in accounts:
            formatted_accounts.append({
                "id": acc.get("id"),
                "gamertag": acc.get("gamertag"),
                "completedCount": acc.get("completedCount", 0),
                "targetMatches": acc.get("targetMatches", 3),
                "completed": acc.get("completedCount", 0) >= acc.get("targetMatches", 3)
            })

        return web.json_response({
            "code": 200,
            "data": formatted_accounts
        })

    async def report_match_complete(self, request):
        """上报比赛完成"""
        task_id = request.match_info['taskId']
        data = await request.json()

        game_account_id = data.get('gameAccountId')
        completed_count = data.get('completedCount', 0)

        report = {
            "taskId": task_id,
            "gameAccountId": game_account_id,
            "completedCount": completed_count,
            "timestamp": 1234567890.0
        }
        self._match_reports.append(report)

        if task_id in self._tasks:
            task = self._tasks[task_id]
            streaming_account_id = task.get('streamingAccountId')

            if streaming_account_id in self._game_accounts:
                accounts = self._game_accounts[streaming_account_id]
                for acc in accounts:
                    if acc.get('id') == game_account_id:
                        acc['completedCount'] = completed_count
                        break

        all_accounts = []
        all_completed = False
        if task_id in self._tasks:
            task = self._tasks[task_id]
            streaming_account_id = task.get('streamingAccountId')
            if streaming_account_id in self._game_accounts:
                all_accounts = self._game_accounts[streaming_account_id]
                all_completed = all(
                    acc.get('completedCount', 0) >= acc.get('targetMatches', 3)
                    for acc in all_accounts
                )

        return web.json_response({
            "code": 200,
            "data": {
                "allAccounts": all_accounts,
                "allCompleted": all_completed
            }
        })

    async def report_task_progress(self, request):
        """上报任务进度"""
        task_id = request.match_info['taskId']
        data = await request.json()

        report = {
            "taskId": task_id,
            "step": data.get('step'),
            "status": data.get('status'),
            "message": data.get('message'),
            "extraData": data.get('extra_data'),
            "timestamp": 1234567890.0
        }
        self._progress_reports.append(report)

        if task_id in self._tasks:
            self._tasks[task_id]['lastProgress'] = report

        return web.json_response({
            "code": 200,
            "message": "Progress reported"
        })

    async def start(self):
        """启动服务器"""
        self._runner = web.AppRunner(self.app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, self.host, self.port)
        await self._site.start()
        logger.info(f"Mock Platform server started at http://{self.host}:{self.port}")

    async def stop(self):
        """停止服务器"""
        if self._site:
            await self._runner.cleanup()
            logger.info("Mock Platform server stopped")


async def create_mock_server(host: str = "localhost", port: int = 8888) -> MockPlatformServer:
    """创建并启动Mock服务器"""
    server = MockPlatformServer(host, port)
    await server.start()
    return server


if __name__ == "__main__":
    import asyncio

    async def main():
        server = MockPlatformServer()

        server.set_task("test_task_001", {
            "id": "test_task_001",
            "streamingAccountId": "sa_001"
        })

        server.set_game_accounts("sa_001", [
            {"id": "ga_001", "gamertag": "Player1", "completedCount": 0, "targetMatches": 3},
            {"id": "ga_002", "gamertag": "Player2", "completedCount": 0, "targetMatches": 3}
        ])

        await server.start()

        try:
            while True:
                await asyncio.sleep(3600)
        except KeyboardInterrupt:
            await server.stop()

    asyncio.run(main())
