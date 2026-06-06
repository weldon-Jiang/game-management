"""
任务调度器
==========

功能说明：
- 管理多个自动化任务的协程执行
- 支持并发执行多个串流账号任务
- 提供任务控制（暂停、恢复、停止）
- 处理任务异常和资源清理
- 处理密码解密（支持token兑换和AES解密）
- 请求间隔控制（防止触发Microsoft安全验证）
- 指数退避策略（失败重试机制）

核心原则：
- 每个串流账号对应一个独立协程
- 一个协程异常不影响其他协程
- 任务完成后协程结束，资源自动清理
- 同一账号登录间隔至少10分钟，避免触发安全验证

作者：技术团队
版本：2.0
"""

import asyncio
import threading
import time
import random
from typing import Dict, Optional, List, Any, Callable

from ..core.logger import get_logger
from ..utils.crypto_util import decrypt_password
from .task_context import AgentTaskContext, GameAccountInfo, XboxInfo, AutomationResult
from ..windows.task_window_manager import TaskWindowManager
from .automation_task import AgentAutomationTask
from ..api.platform_api_client import PlatformApiClient


class AutomationScheduler:
    """
    自动化任务调度器

    职责：
    - 管理多个自动化任务的并发执行
    - 为每个串流账号任务创建独立协程
    - 提供任务控制接口
    - 处理异常和资源清理
    - 请求间隔控制防止触发安全验证

    线程安全：
    - 使用线程锁保护任务状态字典
    - 每个任务独立协程，互不影响

    安全策略：
    - 同一账号最小登录间隔：5分钟（防止频繁登录触发安全验证）
    - 不同账号最小间隔：15秒（避免同一IP频繁请求）
    - 指数退避重试：失败时递增等待时间
    """

    # 安全策略配置（可根据实际情况调整）
    MIN_LOGIN_INTERVAL = 300  # 同一账号最小登录间隔（秒）- 5分钟
    MIN_ACCOUNT_INTERVAL = 15  # 不同账号最小登录间隔（秒）- 15秒

    def __init__(self, max_concurrent_tasks: int = 10, agent_id: str = None, agent_secret: str = None):
        """
        初始化任务调度器

        参数：
        - max_concurrent_tasks: 最大并发任务数
        - agent_id: Agent ID（用于HTTP认证）
        - agent_secret: Agent Secret（用于HTTP认证）
        """
        self.logger = get_logger('automation_scheduler')
        self._max_concurrent = max_concurrent_tasks
        self._semaphore = asyncio.Semaphore(max_concurrent_tasks)

        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._task_contexts: Dict[str, AgentTaskContext] = {}
        self._task_results: Dict[str, AutomationResult] = {}
        self._cancel_events: Dict[str, asyncio.Event] = {}
        self._task_objects: Dict[str, AgentAutomationTask] = {}

        self._window_manager = TaskWindowManager(max_concurrent_windows=max_concurrent_tasks)
        self._platform_client = PlatformApiClient(agent_id=agent_id, agent_secret=agent_secret)

        self._lock = threading.Lock()

        # 登录时间记录（用于间隔控制）
        self._last_login_times: Dict[str, float] = {}
        self._login_lock = asyncio.Lock()

        # Xbox主机串流状态跟踪（防止同一主机被多个任务同时串流）
        self._streaming_xbox_hosts: Dict[str, str] = {}  # xbox_id -> task_id
        self._xbox_lock = asyncio.Lock()

        self.logger.info(f"任务调度器初始化完成，最大并发: {max_concurrent_tasks}")
        self.logger.info(f"登录间隔控制: 同一账号{self.MIN_LOGIN_INTERVAL}秒, 不同账号{self.MIN_ACCOUNT_INTERVAL}秒")

    async def acquire_xbox_host(self, xbox_id: str, task_id: str) -> bool:
        """
        尝试获取Xbox主机的串流权限

        参数：
        - xbox_id: Xbox主机ID
        - task_id: 任务ID

        返回：
        - True: 获取成功
        - False: 获取失败（主机已被其他任务占用）
        """
        async with self._xbox_lock:
            if xbox_id in self._streaming_xbox_hosts:
                occupying_task = self._streaming_xbox_hosts[xbox_id]
                self.logger.warning(f"Xbox主机 {xbox_id} 已被任务 {occupying_task} 占用")
                return False
            self._streaming_xbox_hosts[xbox_id] = task_id
            self.logger.info(f"任务 {task_id} 已获取Xbox主机 {xbox_id} 的串流权限")
            return True

    async def release_xbox_host(self, xbox_id: str, task_id: str):
        """
        释放Xbox主机的串流权限

        参数：
        - xbox_id: Xbox主机ID
        - task_id: 任务ID
        """
        async with self._xbox_lock:
            if xbox_id in self._streaming_xbox_hosts:
                current_task = self._streaming_xbox_hosts[xbox_id]
                if current_task == task_id:
                    del self._streaming_xbox_hosts[xbox_id]
                    self.logger.info(f"任务 {task_id} 已释放Xbox主机 {xbox_id}")
                else:
                    self.logger.warning(f"任务 {task_id} 尝试释放不属于自己的Xbox主机 {xbox_id}")

    def get_streaming_xbox_hosts(self) -> Dict[str, str]:
        """
        获取当前正在被串流的Xbox主机列表

        返回：
        - Dict: xbox_id -> task_id
        """
        return dict(self._streaming_xbox_hosts)

    def set_credentials(self, agent_id: str, agent_secret: str):
        """
        设置Agent凭证用于HTTP认证

        参数：
        - agent_id: Agent ID
        - agent_secret: Agent Secret
        """
        self._platform_client.set_credentials(agent_id, agent_secret)

    async def start_task(
        self,
        task_id: str,
        streaming_account_id: str,
        streaming_account_email: str,
        streaming_account_password: str,
        game_accounts: List[Dict[str, Any]],
        assigned_xbox: Optional[Dict[str, Any]] = None,
        game_action_type: str = "squad_battle",
        account_platform: str = "xbox",
        auto_match_host: bool = True,
        streaming_account_auto_code: str = "",
    ) -> bool:
        """
        启动自动化任务

        参数：
        - task_id: 任务ID
        - streaming_account_id: 串流账号ID
        - streaming_account_email: 串流账号邮箱
        - streaming_account_password: 串流账号密码
        - streaming_account_auto_code: TOTP Secret Key，用于MFA自动验证码生成
        - game_accounts: 游戏账号列表
        - assigned_xbox: 分配的Xbox主机（可选）

        返回：
        - bool: 是否成功启动
        """
        if task_id in self._running_tasks:
            self.logger.warning(f"任务 {task_id} 已在运行中")
            return False

        self.logger.info(f"启动任务: {task_id}, 串流账号: {streaming_account_email}")

        # 解密流媒体账号密码（支持token兑换和AES解密）
        self.logger.info("正在解密流媒体账号密码...")
        decrypted_password = await self._decrypt_streaming_password(streaming_account_password)
        if not decrypted_password:
            self.logger.error(f"任务 {task_id} 流媒体账号密码解密失败")
            await self._platform_client.report_progress(
                task_id,
                "STEP1",
                "FAILED",
                "流媒体账号密码解密失败",
                error_code="PASSWORD_DECRYPT_FAILED",
            )
            return False
        self.logger.info("流媒体账号密码解密成功")

        context = AgentTaskContext(
            task_id=task_id,
            streaming_account_id=streaming_account_id,
            streaming_account_email=streaming_account_email,
            streaming_account_password=decrypted_password,
            streaming_account_auto_code=streaming_account_auto_code,
            window_id=f"window_{task_id}",
            game_action_type=game_action_type or "squad_battle",
            account_platform=account_platform or "xbox",
            auto_match_host=auto_match_host,
        )

        # 解密游戏账号密码
        game_accounts_with_passwords = []
        for ga in game_accounts:
            decrypted_game_password = await self._decrypt_game_account_password(ga)
            game_accounts_with_passwords.append(GameAccountInfo(
                id=ga.get("id", ""),
                gamertag=ga.get("gameName", ga.get("gamertag", "")),
                email=ga.get("email", ""),
                password=decrypted_game_password or "",
                is_primary=ga.get("isPrimary", False),
                target_matches=ga.get("dailyMatchLimit", ga.get("targetMatches", 3)),
                today_match_count=ga.get("todayMatchCount", 0)
            ))

        context.game_accounts = game_accounts_with_passwords

        if assigned_xbox:
            context.assigned_xbox = XboxInfo(
                id=assigned_xbox.get("id", ""),
                name=assigned_xbox.get("name", "Xbox"),
                ip_address=assigned_xbox.get("ipAddress", ""),
                live_id=assigned_xbox.get("liveId", ""),
                mac_address=assigned_xbox.get("macAddress", "")
            )

        cancel_event = asyncio.Event()

        # 登录间隔控制（防止触发安全验证）
        await self._wait_login_interval(streaming_account_email)

        with self._lock:
            self._cancel_events[task_id] = cancel_event
            self._task_contexts[task_id] = context

        await self._semaphore.acquire()

        asyncio_task = asyncio.create_task(
            self._run_task(task_id, context, cancel_event)
        )

        with self._lock:
            self._running_tasks[task_id] = asyncio_task

        return True

    async def _wait_login_interval(self, email: str):
        """
        等待登录间隔，避免频繁登录触发安全验证

        参数：
        - email: 串流账号邮箱
        """
        async with self._login_lock:
            now = time.time()

            # 检查同一账号登录间隔
            wait_time = 0
            if email in self._last_login_times:
                elapsed = now - self._last_login_times[email]
                if elapsed < self.MIN_LOGIN_INTERVAL:
                    wait_time = self.MIN_LOGIN_INTERVAL - elapsed
                    self.logger.info(f"账号 {email} 需要等待 {wait_time:.1f}秒后再登录（最小间隔 {self.MIN_LOGIN_INTERVAL}秒）")
                    await asyncio.sleep(wait_time)

            # 检查不同账号登录间隔
            if self._last_login_times:
                last_login_time = max(self._last_login_times.values())
                elapsed = now - last_login_time
                if elapsed < self.MIN_ACCOUNT_INTERVAL:
                    account_wait = self.MIN_ACCOUNT_INTERVAL - elapsed
                    self.logger.info(f"不同账号间隔控制，等待 {account_wait:.1f}秒")
                    await asyncio.sleep(account_wait)

            # 更新登录时间记录
            self._last_login_times[email] = time.time()
            self.logger.info(f"账号 {email} 登录时间已记录")

    def _exponential_backoff(self, attempt: int, base_delay: float = 5.0, max_delay: float = 60.0) -> float:
        """
        计算指数退避等待时间

        参数：
        - attempt: 当前重试次数（从0开始）
        - base_delay: 基础延迟时间（秒）
        - max_delay: 最大延迟时间（秒）

        返回：
        - 等待时间（秒）
        """
        delay = min(base_delay * (2 ** attempt) + random.uniform(0, base_delay * 0.5), max_delay)
        self.logger.debug(f"指数退避: 第{attempt+1}次尝试，等待 {delay:.2f}秒")
        return delay

    async def _execute_with_backoff(self, func, *args, max_retries: int = 3, **kwargs):
        """
        使用指数退避执行函数

        参数：
        - func: 要执行的异步函数
        - max_retries: 最大重试次数

        返回：
        - 函数执行结果
        """
        last_exception = None

        for attempt in range(max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e
                self.logger.warning(f"执行失败(尝试 {attempt+1}/{max_retries}): {e}")

                if attempt < max_retries - 1:
                    delay = self._exponential_backoff(attempt)
                    await asyncio.sleep(delay)

        self.logger.error(f"执行失败，已达最大重试次数 {max_retries}")
        raise last_exception

    async def _run_task(
        self,
        task_id: str,
        context: AgentTaskContext,
        cancel_event: asyncio.Event
    ):
        """
        运行单个任务的内部协程

        参数：
        - task_id: 任务ID
        - context: 任务上下文
        - cancel_event: 取消事件
        """
        task = None

        try:
            task = AgentAutomationTask(
                context=context,
                window_manager=self._window_manager,
                platform_client=self._platform_client
            )

            with self._lock:
                self._task_objects[task_id] = task

            def check_cancel():
                return cancel_event.is_set()

            result = await task.execute(check_cancel)

            with self._lock:
                self._task_results[task_id] = result

            self.logger.info(f"任务 {task_id} 执行完成: success={result.success}")

        except asyncio.CancelledError:
            self.logger.info(f"任务 {task_id} 被取消")
            await self._platform_client.report_progress(
                task_id,
                "STEP1",
                "CANCELLED",
                "任务被取消",
            )

            with self._lock:
                self._task_results[task_id] = AutomationResult(
                    success=False,
                    error_code="CANCELLED",
                    message="任务被取消"
                )

        except Exception as e:
            self.logger.error(f"任务 {task_id} 执行异常: {e}", exc_info=True)
            await self._platform_client.report_progress(
                task_id,
                "STEP1",
                "FAILED",
                f"任务调度异常: {e}",
                error_code="SCHEDULER_EXCEPTION",
            )

            with self._lock:
                self._task_results[task_id] = AutomationResult(
                    success=False,
                    error_code="EXCEPTION",
                    message=str(e)
                )

        finally:
            with self._lock:
                self._running_tasks.pop(task_id, None)
                self._task_objects.pop(task_id, None)
                self._cancel_events.pop(task_id, None)

            self._semaphore.release()

            self.logger.info(f"任务 {task_id} 协程结束")

    async def pause_task(self, task_id: str) -> bool:
        """
        暂停指定任务

        参数：
        - task_id: 任务ID

        返回：
        - bool: 是否成功
        """
        task = self._task_objects.get(task_id)
        if task:
            await task.pause()
            self.logger.info(f"任务 {task_id} 已暂停")
            return True
        return False

    async def resume_task(self, task_id: str) -> bool:
        """
        恢复指定任务

        参数：
        - task_id: 任务ID

        返回：
        - bool: 是否成功
        """
        task = self._task_objects.get(task_id)
        if task:
            await task.resume()
            self.logger.info(f"任务 {task_id} 已恢复")
            return True
        return False

    async def stop_task(self, task_id: str) -> bool:
        """
        停止指定任务

        参数：
        - task_id: 任务ID

        返回：
        - bool: 是否成功
        """
        cancel_event = self._cancel_events.get(task_id)
        if cancel_event:
            cancel_event.set()
            self.logger.info(f"任务 {task_id} 停止请求已发送")
            return True
        return False

    def get_task_status(self, task_id: str) -> Optional[str]:
        """
        获取任务状态

        参数：
        - task_id: 任务ID

        返回：
        - str: 任务状态或None
        """
        context = self._task_contexts.get(task_id)
        if context:
            return context.task_status.value
        return None

    def get_task_result(self, task_id: str) -> Optional[AutomationResult]:
        """
        获取任务结果

        参数：
        - task_id: 任务ID

        返回：
        - AutomationResult: 任务结果或None
        """
        return self._task_results.get(task_id)

    def get_running_task_count(self) -> int:
        """获取正在运行的任务数量"""
        return len(self._running_tasks)

    def get_all_task_ids(self) -> List[str]:
        """获取所有任务ID列表"""
        with self._lock:
            return list(self._task_contexts.keys())

    async def stop_all_tasks(self):
        """停止所有任务"""
        self.logger.info("停止所有任务...")

        task_ids = list(self._running_tasks.keys())
        for task_id in task_ids:
            await self.stop_task(task_id)

        await self._window_manager.close_all_windows()

        self.logger.info("所有任务已停止")

    async def close(self):
        """关闭调度器"""
        await self.stop_all_tasks()
        await self._platform_client.close()
        self.logger.info("任务调度器已关闭")

    async def _decrypt_streaming_password(self, encrypted_password: str) -> Optional[str]:
        """
        解密流媒体账号密码

        支持的密码格式：
        - token:xxx - 凭证令牌，需要先兑换为实际密码
        - hex:xxx - 十六进制加密密码
        - base64编码的AES加密密码
        - 其他格式直接返回（可能是已解密的密码）

        参数：
        - encrypted_password: 加密的密码或令牌

        返回：
        - str: 解密后的密码
        - None: 解密失败
        """
        if not encrypted_password:
            self.logger.warning("密码为空")
            return None

        try:
            # 如果是token格式（UUID格式或以token:开头），先兑换为实际密码
            is_uuid_format = len(encrypted_password) == 32 or (len(encrypted_password) == 36 and '-' in encrypted_password)
            if encrypted_password.startswith('token:') or is_uuid_format:
                token = encrypted_password[6:] if encrypted_password.startswith('token:') else encrypted_password
                self.logger.info(f"流媒体账号正在兑换凭证令牌获取密码: {token[:8]}...")

                if not self._platform_client:
                    self.logger.error("无法进行令牌交换：没有API客户端")
                    return None

                encrypted_password = await self._platform_client.exchange_credential_token(token)
                if not encrypted_password:
                    self.logger.error("流媒体账号令牌兑换失败")
                    return None
                self.logger.info("流媒体账号令牌兑换成功")

            # 如果是DISABLED格式，返回空（账号被禁用）
            if encrypted_password.startswith('DISABLED:'):
                self.logger.warning("流媒体账号已被禁用")
                return None

            # 执行AES解密
            decrypted = decrypt_password(encrypted_password)
            self.logger.debug("流媒体账号密码AES解密成功")
            return decrypted

        except Exception as e:
            self.logger.error(f"流媒体账号密码解密异常: {e}")
            return None

    async def _decrypt_game_account_password(self, ga: Dict[str, Any]) -> Optional[str]:
        """
        解密游戏账号密码

        参数：
        - ga: 游戏账号字典

        返回：
        - 解密后的密码
        - None: 解密失败
        """
        gamertag = ga.get("gameName", ga.get("gamertag", "unknown"))
        password_token = ga.get("passwordToken", "")
        if not password_token:
            self.logger.warning(f"游戏账号 {gamertag} 密码为空")
            return None

        try:
            # 如果是token格式（UUID格式或以token:开头），先兑换为实际密码
            is_uuid_format = len(password_token) == 32 or (len(password_token) == 36 and '-' in password_token)
            if password_token.startswith('token:') or is_uuid_format:
                token = password_token[6:] if password_token.startswith('token:') else password_token
                self.logger.info(f"游戏账号 {gamertag} 正在兑换凭证令牌获取密码: {token[:8]}...")

                if not self._platform_client:
                    self.logger.error("无法进行令牌交换：没有API客户端")
                    return None

                encrypted_password = await self._platform_client.exchange_credential_token(token)
                if not encrypted_password:
                    self.logger.error(f"游戏账号 {gamertag} 令牌兑换失败")
                    return None
                password_token = encrypted_password
                self.logger.info(f"游戏账号 {gamertag} 令牌兑换成功")

            # 如果是DISABLED格式，返回空（账号被禁用）
            if password_token.startswith('DISABLED:'):
                self.logger.warning(f"游戏账号 {gamertag} 已被禁用")
                return None

            # 执行AES解密
            decrypted = decrypt_password(password_token)
            self.logger.debug(f"游戏账号 {gamertag} 密码AES解密成功")
            return decrypted

        except Exception as e:
            self.logger.error(f"游戏账号 {gamertag} 密码解密异常: {e}")
            return None
