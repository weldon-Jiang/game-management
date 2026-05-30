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
import base64
from typing import Dict, Any, Optional, List, Callable

import aiohttp

from ..core.logger import get_logger
from ..core.config import config
from ..core.credentials_provider import get_credentials


class PlatformApiClient:
    """
    Platform API客户端

    负责Agent与Platform之间的实时数据同步

    功能：
    - 获取游戏账号当天完成情况
    - 上报比赛完成信息
    - 上报任务进度
    """

    def __init__(self, base_url: Optional[str] = None, agent_id: Optional[str] = None, agent_secret: Optional[str] = None):
        """
        初始化Platform API客户端

        参数：
        - base_url: Platform API基础URL
        - agent_id: Agent ID（用于HTTP认证），可选，不传则从凭证文件读取
        - agent_secret: Agent Secret（用于HTTP认证），可选，不传则从凭证文件读取
        """
        self.logger = get_logger('platform_api_client')
        self.base_url = base_url or config.get('platform.api_url', 'http://localhost:8060/api')
        # 如果没有显式传入凭证，则从凭证管理器获取
        if agent_id is not None and agent_secret is not None:
            self._agent_id = agent_id
            self._agent_secret = agent_secret
        else:
            self._agent_id = None
            self._agent_secret = None
        self._session: Optional[aiohttp.ClientSession] = None
        self._retry_count = 3
        self._retry_delay = 1.0
        self._closed = False

    def set_credentials(self, agent_id: str, agent_secret: str):
        """
        设置Agent凭证用于HTTP认证

        参数：
        - agent_id: Agent ID
        - agent_secret: Agent Secret
        """
        self._agent_id = agent_id
        self._agent_secret = agent_secret

    async def _get_headers(self) -> Dict[str, str]:
        """获取HTTP请求头（包含认证信息）"""
        headers = {'Content-Type': 'application/json'}
        
        # 优先使用实例变量，其次从凭证管理器获取（get_credentials直接从文件读取，不缓存）
        agent_id = self._agent_id
        agent_secret = self._agent_secret
        
        if not agent_id or not agent_secret:
            agent_id, agent_secret = get_credentials()
        
        if agent_id and agent_secret:
            headers['X-Agent-Id'] = agent_id
            # Base64编码 agent_secret（后端期望收到Base64编码的secret）
            encoded_secret = base64.b64encode(agent_secret.encode('utf-8')).decode('utf-8')
            headers['X-Agent-Secret'] = encoded_secret
            # 调试日志
            self.logger.info(f"认证信息 - agentId: {agent_id}, 原始secret长度: {len(agent_secret)}, Base64编码后: {encoded_secret}")
        else:
            self.logger.warning(f"Agent凭证缺失 - agent_id: {'存在' if agent_id else '缺失'}, agent_secret: {'存在' if agent_secret else '缺失'}")
        
        return headers

    async def _get_session(self) -> aiohttp.ClientSession:
        """获取或创建HTTP会话"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """关闭HTTP会话"""
        self._closed = True
        if self._session and not self._session.closed:
            try:
                await asyncio.wait_for(self._session.close(), timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("关闭HTTP会话超时")
            except Exception as e:
                self.logger.debug(f"关闭HTTP会话异常: {e}")

    async def report_task_status(self, task_id: str, status: str, message: Optional[str] = None) -> Dict[str, Any]:
        """
        上报任务状态到平台

        参数：
        - task_id: 任务ID
        - status: 任务状态 (pending/running/completed/failed/cancelled/timeout)
        - message: 状态消息（可选）

        返回：
        - 平台响应数据
        """
        url = f"{self.base_url}/agent-callback/task/{task_id}/status"
        headers = await self._get_headers()
        payload = {"status": status}
        if message:
            payload["message"] = message

        try:
            self.logger.info(f"上报状态请求 - URL: {url}, Headers: X-Agent-Id={headers.get('X-Agent-Id')}")
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    response_body = await response.text()
                    self.logger.warning(f"上报任务状态HTTP错误: {response.status}, 响应: {response_body}")
                    return {}
        except Exception as e:
            self.logger.error(f"上报任务状态异常: {e}")
            return {}

    async def update_game_account_status(self, task_id: str, game_account_id: str, status: str,
                                         today_completed: Optional[int] = None,
                                         daily_limit: Optional[int] = None) -> Dict[str, Any]:
        """
        更新游戏账号状态（子任务状态）

        参数：
        - task_id: 任务ID
        - game_account_id: 游戏账号ID
        - status: 状态 (pending/running/game_preparing/gaming/completed/failed/cancelled/timeout)
        - today_completed: 今日完成次数（可选）
        - daily_limit: 每日最大次数（可选）

        返回：
        - 平台响应数据
        """
        url = f"{self.base_url}/agent-callback/task/{task_id}/game-account/{game_account_id}/status"
        headers = await self._get_headers()
        payload = {"status": status}
        if today_completed is not None:
            payload["todayCompleted"] = today_completed
        if daily_limit is not None:
            payload["dailyLimit"] = daily_limit

        try:
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    return result
                else:
                    self.logger.warning(f"更新游戏账号状态HTTP错误: {response.status}")
                    return {}
        except Exception as e:
            self.logger.error(f"更新游戏账号状态异常: {e}")
            return {}

    async def get_game_accounts_status(self, task_id: str) -> Dict[str, Dict[str, Any]]:
        """
        获取串流账号下所有游戏账号的当天完成情况

        参数：
        - task_id: 任务ID

        返回：
        - Dict: {gameAccountId: {id, gamertag, completedCount, targetMatches, completed}}
        """
        url = f"{self.base_url}/{task_id}/game-accounts/status"
        headers = await self._get_headers()

        for attempt in range(self._retry_count):
            try:
                session = await self._get_session()
                async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as response:
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
        url = f"{self.base_url}/{task_id}/match/complete"
        headers = await self._get_headers()
        params = {
            "gameAccountId": game_account_id,
            "completedCount": completed_count
        }

        for attempt in range(self._retry_count):
            try:
                session = await self._get_session()
                async with session.post(url, params=params, headers=headers,
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
        if self._closed:
            self.logger.debug(f"客户端已关闭，跳过进度上报: {task_id}")
            return

        try:
            url = f"{self.base_url}/{task_id}/progress"
            headers = await self._get_headers()
            payload = {
                "taskId": task_id,
                "step": step,
                "status": status,
                "message": message,
                "timestamp": time.time(),
                **kwargs
            }
            self.logger.info(f"上报请求 - URL: {url}, Headers: X-Agent-Id={headers.get('X-Agent-Id')}")
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=5)) as response:
                if response.status == 200:
                    self.logger.debug(f"任务进度上报成功(HTTP): {task_id} - {step} - {status}")
                    return
                else:
                    response_body = await response.text()
                    self.logger.warning(f"任务进度上报HTTP错误: {response.status}, 响应: {response_body}")
        except Exception as e:
            self.logger.debug(f"HTTP上报失败: {e}")

        self.logger.debug(f"任务进度上报失败: {task_id} - {step} - {status}")

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
        await self.report_task_progress(
            task_id,
            step,
            "FAILED",
            error_message,
            errorCode=error_code,
            errorDetails=error_details
        )

    async def exchange_credential_token(self, token: str) -> Optional[str]:
        """
        兑换凭证令牌获取实际密码

        参数：
        - token: 凭证令牌

        返回：
        - str: 加密的密码字符串
        - None: 兑换失败
        """
        # base_url 已包含 /api 前缀（如 http://localhost:8060/api）
        # 不需要再添加 /api
        url = f"{self.base_url}/agent/credentials/exchange"
        headers = await self._get_headers()

        try:
            session = await self._get_session()
            async with session.post(url, params={"token": token}, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 200:
                        data = result.get("data")
                        if isinstance(data, dict):
                            return data.get("password")
                        return data
                    else:
                        self.logger.warning(f"凭证兑换失败: {result.get('message')}")
                        return None
                else:
                    self.logger.warning(f"凭证兑换HTTP错误: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"凭证兑换异常: {e}")
            return None

    async def lock_xbox_host(self, xbox_host_id: str) -> bool:
        """
        锁定Xbox主机，防止其他Agent占用

        参数：
        - xbox_host_id: Xbox主机ID（数据库ID）

        返回：
        - True: 锁定成功
        - False: 锁定失败（主机已被锁定或不存在）
        """
        url = f"{self.base_url}/xbox-host/{xbox_host_id}/lock"
        headers = await self._get_headers()

        try:
            session = await self._get_session()
            async with session.post(url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 200:
                        self.logger.info(f"成功锁定Xbox主机: {xbox_host_id}")
                        return True
                    else:
                        self.logger.warning(f"锁定Xbox主机失败: {result.get('message')}")
                        return False
                else:
                    self.logger.warning(f"锁定Xbox主机HTTP错误: {response.status}")
                    return False
        except Exception as e:
            self.logger.error(f"锁定Xbox主机异常: {e}")
            return False

    async def unlock_xbox_host(self, xbox_host_id: str) -> bool:
        """
        解锁Xbox主机

        参数：
        - xbox_host_id: Xbox主机ID（数据库ID）

        返回：
        - True: 解锁成功
        - False: 解锁失败
        """
        url = f"{self.base_url}/xbox-host/{xbox_host_id}/unlock"
        headers = await self._get_headers()

        try:
            session = await self._get_session()
            async with session.post(url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 200:
                        self.logger.info(f"成功解锁Xbox主机: {xbox_host_id}")
                        return True
                    else:
                        self.logger.warning(f"解锁Xbox主机失败: {result.get('message')}")
                        return False
                else:
                    self.logger.warning(f"解锁Xbox主机HTTP错误: {response.status}")
                    return False
        except Exception as e:
            self.logger.error(f"解锁Xbox主机异常: {e}")
            return False

    async def get_xbox_host_status(self, xbox_host_id: str) -> Optional[Dict[str, Any]]:
        """
        获取Xbox主机状态（包括锁定状态）

        参数：
        - xbox_host_id: Xbox主机ID（数据库ID）

        返回：
        - Dict: 主机状态信息，包含 locked, lockedByAgentId, lockExpiresTime 等字段
        - None: 获取失败
        """
        url = f"{self.base_url}/xbox-host/{xbox_host_id}"
        headers = await self._get_headers()

        try:
            session = await self._get_session()
            async with session.get(url, headers=headers,
                                  timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("code") == 200:
                        return result.get("data")
                    else:
                        self.logger.warning(f"获取主机状态失败: {result.get('message')}")
                        return None
                else:
                    self.logger.warning(f"获取主机状态HTTP错误: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"获取主机状态异常: {e}")
            return None


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
