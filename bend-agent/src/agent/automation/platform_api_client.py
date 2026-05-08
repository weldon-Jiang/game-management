"""
Platform API客户端
==================

功能说明：
- 负责Agent与Platform之间的实时数据同步
- 获取游戏账号当天完成情况
- 上报比赛完成信息
- 上报任务进度

作者：技术团队
版本：1.0
"""

import asyncio
import time
from typing import Dict, Any, Optional, List, Callable

import aiohttp

from ..core.logger import get_logger
from ..core.config import config


class PlatformApiClient:
    """
    Platform API客户端

    负责Agent与Platform之间的实时数据同步

    功能：
    - 获取游戏账号当天完成情况
    - 上报比赛完成信息
    - 上报任务进度
    """

    def __init__(self, base_url: Optional[str] = None):
        """
        初始化Platform API客户端

        参数：
        - base_url: Platform API基础URL
        """
        self.logger = get_logger('platform_api_client')
        self.base_url = base_url or config.get('platform.api_url', 'http://localhost:8080/api')
        self._session: Optional[aiohttp.ClientSession] = None
        self._retry_count = 3
        self._retry_delay = 1.0

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """关闭HTTP会话"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_game_accounts_status(self, task_id: str) -> Dict[str, Dict[str, Any]]:
        """
        获取串流账号下所有游戏账号的当天完成情况

        参数：
        - task_id: 任务ID

        返回：
        - Dict: {gameAccountId: {id, gamertag, completedCount, targetMatches, completed}}
        """
        url = f"{self.base_url}/task/{task_id}/game-accounts/status"

        for attempt in range(self._retry_count):
            try:
                session = await self._get_session()
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("code") == 200:
                            data = result.get("data", [])
                            return {acc["id"]: acc for acc in data}
                        else:
                            self.logger.warning(f"获取账号状态失败: {result.get('message')}")
                            return {}
                    else:
                        self.logger.warning(f"获取账号状态HTTP错误: {response.status}")

            except asyncio.TimeoutError:
                self.logger.warning(f"获取账号状态超时 (尝试 {attempt + 1}/{self._retry_count})")
            except Exception as e:
                self.logger.error(f"获取账号状态异常: {e}")

            if attempt < self._retry_count - 1:
                await asyncio.sleep(self._retry_delay * (attempt + 1))

        return {}

    async def report_match_complete(
        self,
        task_id: str,
        game_account_id: str,
        completed_count: int
    ) -> Optional[Dict[str, Any]]:
        """
        上报比赛完成信息到平台

        参数：
        - task_id: 任务ID
        - game_account_id: 游戏账号ID
        - completed_count: 完成后当天总场次

        返回：
        - dict: 包含allAccounts和allCompleted
        """
        url = f"{self.base_url}/task/{task_id}/match/complete"
        payload = {
            "gameAccountId": game_account_id,
            "completedCount": completed_count
        }

        for attempt in range(self._retry_count):
            try:
                session = await self._get_session()
                async with session.post(url, json=payload,
                                       timeout=aiohttp.ClientTimeout(total=10)) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get("code") == 200:
                            self.logger.info(f"比赛完成上报成功: {game_account_id} - {completed_count}场")
                            return result.get("data", {})
                        else:
                            self.logger.warning(f"比赛完成上报失败: {result.get('message')}")
                            return None
                    else:
                        self.logger.warning(f"比赛完成上报HTTP错误: {response.status}")

            except asyncio.TimeoutError:
                self.logger.warning(f"比赛完成上报超时 (尝试 {attempt + 1}/{self._retry_count})")
            except Exception as e:
                self.logger.error(f"比赛完成上报异常: {e}")

            if attempt < self._retry_count - 1:
                await asyncio.sleep(self._retry_delay * (attempt + 1))

        return None

    async def report_task_progress(
        self,
        task_id: str,
        step: str,
        status: str,
        message: str,
        **kwargs
    ):
        """
        上报任务进度到平台

        参数：
        - task_id: 任务ID
        - step: 当前步骤
        - status: 状态
        - message: 消息
        - **kwargs: 其他字段
        """
        # 首先尝试通过 HTTP 接口上报（兼容 Mock 服务器和真实 API）
        try:
            url = f"{self.base_url}/task/{task_id}/progress"
            payload = {
                "taskId": task_id,
                "step": step,
                "status": status,
                "message": message,
                "timestamp": time.time(),
                **kwargs
            }
            session = await self._get_session()
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    self.logger.debug(f"任务进度上报成功(HTTP): {task_id} - {step} - {status}")
                    return
                else:
                    self.logger.warning(f"任务进度上报HTTP错误: {response.status}")
        except Exception as e:
            self.logger.debug(f"HTTP上报失败，尝试WebSocket: {e}")

        # 备选：通过 WebSocket 上报
        try:
            from ..api.websocket import websocket_client

            if websocket_client and hasattr(websocket_client, '_running') and websocket_client._running:
                payload = {
                    "taskId": task_id,
                    "step": step,
                    "status": status,
                    "message": message,
                    "timestamp": time.time(),
                    **kwargs
                }
                await websocket_client.send("task_progress", payload)
                self.logger.debug(f"任务进度上报成功(WebSocket): {task_id} - {step} - {status}")

        except Exception as e:
            self.logger.error(f"上报任务进度失败: {e}")

    async def report_task_error(
        self,
        task_id: str,
        step: str,
        error_code: str,
        error_message: str,
        error_details: Optional[str] = None
    ):
        """
        上报任务错误到平台

        参数：
        - task_id: 任务ID
        - step: 当前步骤
        - error_code: 错误码
        - error_message: 错误消息
        - error_details: 错误详情
        """
        try:
            from ..api.websocket import websocket_client

            if websocket_client and websocket_client.is_connected():
                payload = {
                    "type": "TASK_ERROR",
                    "taskId": task_id,
                    "step": step,
                    "errorCode": error_code,
                    "errorMessage": error_message,
                    "errorDetails": error_details,
                    "timestamp": time.time()
                }
                await websocket_client.send(payload)
                self.logger.info(f"任务错误上报: {task_id} - {error_code} - {error_message}")

        except Exception as e:
            self.logger.error(f"上报任务错误失败: {e}")


class ProgressReporter:
    """
    进度上报器

    封装进度上报逻辑，提供简单的接口
    """

    def __init__(self, platform_client: PlatformApiClient):
        """
        初始化进度上报器

        参数：
        - platform_client: Platform API客户端
        """
        self.platform_client = platform_client
        self.logger = get_logger('progress_reporter')

    async def report(
        self,
        task_id: str,
        step: str,
        status: str,
        message: str,
        **kwargs
    ):
        """
        上报进度

        参数：
        - task_id: 任务ID
        - step: 当前步骤
        - status: 状态
        - message: 消息
        - **kwargs: 其他字段
        """
        await self.platform_client.report_task_progress(
            task_id, step, status, message, **kwargs
        )

    async def report_error(
        self,
        task_id: str,
        step: str,
        error_code: str,
        error_message: str,
        error_details: Optional[str] = None
    ):
        """
        上报错误

        参数：
        - task_id: 任务ID
        - step: 当前步骤
        - error_code: 错误码
        - error_message: 错误消息
        - error_details: 错误详情
        """
        await self.platform_client.report_task_error(
            task_id, step, error_code, error_message, error_details
        )
