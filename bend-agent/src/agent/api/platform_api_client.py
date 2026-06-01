"""
Platform API客户端 v2.0
=====================

功能说明：
- 负责Agent与Platform之间的实时数据同步
- 统一使用 /api/v1/agent-callback 前缀
- 所有参数通过请求体JSON传递
- 支持向后兼容旧接口

作者：技术团队
版本：2.0
"""

import asyncio
import time
from typing import Dict, Any, Optional, List

import aiohttp

from ..core.logger import get_logger
from ..core.config import config
from ..core.credentials_provider import get_credentials
from .auth_headers import build_agent_auth_headers


class PlatformApiClient:
    """
    Platform API客户端 v2.0

    统一接口规范：
    - 所有回调接口使用 /api/v1/agent-callback 前缀
    - 所有参数通过请求体JSON传递
    - 使用 X-Agent-Id 和 X-Agent-Secret 请求头认证
    """

    def __init__(self, base_url: Optional[str] = None, agent_id: Optional[str] = None, agent_secret: Optional[str] = None):
        self.logger = get_logger('platform_api_client')
        self.base_url = base_url or config.get('platform.api_url', 'http://localhost:8060/api')
        self._api_version = 'v1'

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
        self._agent_id = agent_id
        self._agent_secret = agent_secret

    async def _get_headers(self) -> Dict[str, str]:
        agent_id = self._agent_id
        agent_secret = self._agent_secret

        if not agent_id or not agent_secret:
            agent_id, agent_secret = get_credentials()

        headers = build_agent_auth_headers(
            agent_id,
            agent_secret,
            extra={'X-API-Version': self._api_version},
        )

        if not agent_id or not agent_secret:
            self.logger.warning(
                "Agent凭证缺失 - agent_id: %s, agent_secret: %s",
                '存在' if agent_id else '缺失',
                '存在' if agent_secret else '缺失',
            )

        return headers

    def _get_callback_url(self, endpoint: str) -> str:
        return f"{self.base_url}/{self._api_version}/agent-callback/{endpoint}"

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        self._closed = True
        if self._session and not self._session.closed:
            try:
                await asyncio.wait_for(self._session.close(), timeout=5.0)
            except asyncio.TimeoutError:
                self.logger.warning("关闭HTTP会话超时")
            except Exception as e:
                self.logger.debug(f"关闭HTTP会话异常: {e}")

    async def report_progress(
        self,
        task_id: str,
        step: str,
        status: str,
        message: str,
        game_account_id: Optional[str] = None,
        today_completed: Optional[int] = None,
        daily_limit: Optional[int] = None,
        error_code: Optional[str] = None,
        error_details: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        统一进度上报接口 v2.0

        功能：
        - 替代原有的 report_task_status、report_task_progress、update_game_account_status
        - 支持详细的步骤级进度上报
        - 自动处理任务状态转换和游戏账号状态更新

        参数：
        - task_id: 任务ID（必需）
        - step: 当前步骤 (STEP1|STEP2|STEP3|STEP4)
        - status: 状态 (RUNNING|COMPLETED|FAILED|GAME_PREPARING|GAMING|CANCELLED)
        - message: 状态描述
        - game_account_id: 游戏账号ID（可选）
        - today_completed: 今日完成次数（可选）
        - daily_limit: 每日最大次数（可选）
        - error_code: 错误码（可选）
        - error_details: 错误详情（可选）
        - **kwargs: 其他字段

        返回：
        - dict: 包含 received, action (CONTINUE|STOP|CANCEL) 等
        """
        url = self._get_callback_url('progress')
        headers = await self._get_headers()

        payload = {
            'taskId': task_id,
            'timestamp': int(time.time() * 1000),
            'data': {
                'step': step,
                'status': status,
                'message': message
            }
        }

        if game_account_id:
            payload['data']['gameAccountId'] = game_account_id

        if any([today_completed is not None, daily_limit is not None]):
            payload['data']['metrics'] = {}
            if today_completed is not None:
                payload['data']['metrics']['todayCompleted'] = today_completed
            if daily_limit is not None:
                payload['data']['metrics']['dailyLimit'] = daily_limit

        if error_code or error_details:
            payload['data']['error'] = {}
            if error_code:
                payload['data']['error']['code'] = error_code
            if error_details:
                payload['data']['error']['details'] = error_details

        payload['data'].update(kwargs)

        try:
            self.logger.info(f"【v2.0】统一进度上报 - URL: {url}, TaskID: {task_id}, Step: {step}, Status: {status}")
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('code') == 200:
                        self.logger.info(f"进度上报成功 - TaskID: {task_id}, Action: {result.get('data', {}).get('action')}")
                        return result.get('data', {})
                    else:
                        self.logger.warning(f"进度上报失败 - Code: {result.get('code')}, Message: {result.get('message')}")
                        return {}
                else:
                    response_body = await response.text()
                    self.logger.warning(f"进度上报HTTP错误: {response.status}, 响应: {response_body}")
                    return {}
        except Exception as e:
            self.logger.error(f"进度上报异常: {e}")
            return {}

    async def get_task_info(self, task_id: str) -> Optional[Dict[str, Any]]:
        """
        获取任务信息

        参数：
        - task_id: 任务ID

        返回：
        - dict: 包含 taskId, streamingAccount, gameAccounts, taskType 等
        """
        url = self._get_callback_url(f'task/{task_id}')
        headers = await self._get_headers()

        try:
            session = await self._get_session()
            async with session.get(url, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('code') == 200:
                        return result.get('data')
                    else:
                        self.logger.warning(f"获取任务信息失败: {result.get('message')}")
                        return None
                else:
                    self.logger.warning(f"获取任务信息HTTP错误: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"获取任务信息异常: {e}")
            return None

    async def lock_xbox_host(self, xbox_host_id: str, task_id: Optional[str] = None) -> bool:
        """
        锁定Xbox主机（v2.0）

        参数：
        - xbox_host_id: Xbox主机ID
        - task_id: 任务ID（可选）

        返回：
        - True: 锁定成功
        - False: 锁定失败（主机已被锁定或不存在）
        """
        url = self._get_callback_url(f'xbox/{xbox_host_id}/lock')
        headers = await self._get_headers()

        payload = {}
        if task_id:
            payload['taskId'] = task_id

        try:
            session = await self._get_session()
            async with session.post(url, json=payload if payload else None, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('code') == 200:
                        locked = result.get('data', {}).get('locked', False)
                        if locked:
                            self.logger.info(f"成功锁定Xbox主机: {xbox_host_id}")
                        else:
                            self.logger.warning(f"锁定Xbox主机失败: {xbox_host_id}")
                        return locked
                    else:
                        self.logger.warning(f"锁定Xbox主机失败: {result.get('message')}")
                        return False
                else:
                    self.logger.warning(f"锁定Xbox主机HTTP错误: {response.status}")
                    return False
        except Exception as e:
            self.logger.error(f"锁定Xbox主机异常: {e}")
            return False

    async def unlock_xbox_host(self, xbox_host_id: str, task_id: Optional[str] = None) -> bool:
        """
        解锁Xbox主机（v2.0）

        参数：
        - xbox_host_id: Xbox主机ID
        - task_id: 任务ID（可选）

        返回：
        - True: 解锁成功
        - False: 解锁失败
        """
        url = self._get_callback_url(f'xbox/{xbox_host_id}/unlock')
        headers = await self._get_headers()

        payload = {}
        if task_id:
            payload['taskId'] = task_id

        try:
            session = await self._get_session()
            async with session.post(url, json=payload if payload else None, headers=headers,
                                   timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('code') == 200:
                        unlocked = result.get('data', {}).get('unlocked', False)
                        if unlocked:
                            self.logger.info(f"成功解锁Xbox主机: {xbox_host_id}")
                        else:
                            self.logger.warning(f"解锁Xbox主机失败: {xbox_host_id}")
                        return unlocked
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
        获取Xbox主机状态（v2.0）

        参数：
        - xbox_host_id: Xbox主机ID

        返回：
        - Dict: 主机状态信息
        - None: 获取失败
        """
        url = self._get_callback_url(f'xbox/{xbox_host_id}')
        headers = await self._get_headers()

        try:
            session = await self._get_session()
            async with session.get(url, headers=headers,
                                  timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('code') == 200:
                        return result.get('data')
                    else:
                        self.logger.warning(f"获取主机状态失败: {result.get('message')}")
                        return None
                else:
                    self.logger.warning(f"获取主机状态HTTP错误: {response.status}")
                    return None
        except Exception as e:
            self.logger.error(f"获取主机状态异常: {e}")
            return None

    async def exchange_credential_token(self, token: str) -> Optional[str]:
        """
        兑换凭证令牌获取实际密码（v2.0）

        参数：
        - token: 凭证令牌

        返回：
        - str: 加密的密码字符串
        - None: 兑换失败
        """
        url = self._get_callback_url('credentials/exchange')
        headers = await self._get_headers()

        payload = {'token': token}

        try:
            session = await self._get_session()
            async with session.post(url, json=payload, headers=headers,
                                    timeout=aiohttp.ClientTimeout(total=10)) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('code') == 200:
                        data = result.get('data')
                        if isinstance(data, dict):
                            return data.get('credential')
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

    # ==================== 兼容旧接口（标记为deprecated） ====================

    async def report_task_status(self, task_id: str, status: str, message: Optional[str] = None) -> Dict[str, Any]:
        """
        @deprecated 使用 report_progress 替代

        上报任务状态到平台
        """
        self.logger.warning("【deprecated】使用旧接口 report_task_status，请迁移至 report_progress")
        return await self.report_progress(task_id, 'STEP0', status.upper(), message or '')

    async def update_game_account_status(self, task_id: str, game_account_id: str, status: str,
                                         today_completed: Optional[int] = None,
                                         daily_limit: Optional[int] = None) -> Dict[str, Any]:
        """
        @deprecated 使用 report_progress 替代

        更新游戏账号状态
        """
        self.logger.warning("【deprecated】使用旧接口 update_game_account_status，请迁移至 report_progress")

        status_map = {
            'pending': 'RUNNING',
            'running': 'RUNNING',
            'game_preparing': 'GAME_PREPARING',
            'gaming': 'GAMING',
            'completed': 'COMPLETED',
            'failed': 'FAILED',
            'cancelled': 'CANCELLED'
        }

        return await self.report_progress(
            task_id, 'STEP4', status_map.get(status, status.upper()), '',
            game_account_id=game_account_id,
            today_completed=today_completed,
            daily_limit=daily_limit
        )

    async def get_game_accounts_status(self, task_id: str) -> Dict[str, Dict[str, Any]]:
        """
        @deprecated 使用 get_task_info 替代

        获取串流账号下所有游戏账号的当天完成情况
        """
        self.logger.warning("【deprecated】使用旧接口 get_game_accounts_status，请迁移至 get_task_info")

        task_info = await self.get_task_info(task_id)
        if not task_info:
            return {}

        result = {}
        for ga in task_info.get('gameAccounts', []):
            result[ga['id']] = ga

        return result

    async def report_match_complete(
        self,
        task_id: str,
        game_account_id: str,
        completed_count: int
    ) -> Optional[Dict[str, Any]]:
        """
        @deprecated 使用 report_progress 替代

        上报比赛完成信息到平台
        """
        self.logger.warning("【deprecated】使用旧接口 report_match_complete，请迁移至 report_progress")

        result = await self.report_progress(
            task_id, 'STEP4', 'COMPLETED',
            f'比赛完成: {completed_count}场',
            game_account_id=game_account_id,
            today_completed=completed_count
        )

        return result

    async def report_task_progress(
        self,
        task_id: str,
        step: str,
        status: str,
        message: str,
        **kwargs
    ):
        """
        @deprecated 使用 report_progress 替代

        上报任务进度到平台
        """
        self.logger.warning("【deprecated】使用旧接口 report_task_progress，请迁移至 report_progress")
        return await self.report_progress(task_id, step, status, message, **kwargs)

    async def report_task_error(
        self,
        task_id: str,
        step: str,
        error_code: str,
        error_message: str,
        error_details: Optional[str] = None
    ):
        """
        @deprecated 使用 report_progress 替代

        上报任务错误到平台
        """
        self.logger.warning("【deprecated】使用旧接口 report_task_error，请迁移至 report_progress")
        return await self.report_progress(
            task_id, step, 'FAILED', error_message,
            error_code=error_code,
            error_details=error_details
        )


class ProgressReporter:
    """
    进度上报器 v2.0

    封装进度上报逻辑，提供简单的接口
    """

    def __init__(self, platform_client: PlatformApiClient):
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
        上报进度（v2.0统一接口）
        """
        return await self.platform_client.report_progress(
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
        上报错误（v2.0统一接口）
        """
        return await self.platform_client.report_progress(
            task_id, step, 'FAILED', error_message,
            error_code=error_code,
            error_details=error_details
        )
