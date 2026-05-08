"""
任务调度器
==========

功能说明：
- 管理多个自动化任务的协程执行
- 支持并发执行多个串流账号任务
- 提供任务控制（暂停、恢复、停止）
- 处理任务异常和资源清理

核心原则：
- 每个串流账号对应一个独立协程
- 一个协程异常不影响其他协程
- 任务完成后协程结束，资源自动清理

作者：技术团队
版本：1.0
"""

import asyncio
import threading
from typing import Dict, Optional, List, Any, Callable

from ..core.logger import get_logger
from .task_context import AgentTaskContext, GameAccountInfo, XboxInfo, AutomationResult
from .task_window_manager import TaskWindowManager
from .automation_task import AgentAutomationTask
from .platform_api_client import PlatformApiClient


class AutomationScheduler:
    """
    自动化任务调度器

    职责：
    - 管理多个自动化任务的并发执行
    - 为每个串流账号任务创建独立协程
    - 提供任务控制接口
    - 处理异常和资源清理

    线程安全：
    - 使用线程锁保护任务状态字典
    - 每个任务独立协程，互不影响
    """

    def __init__(self, max_concurrent_tasks: int = 10):
        """
        初始化任务调度器

        参数：
        - max_concurrent_tasks: 最大并发任务数
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
        self._platform_client = PlatformApiClient()

        self._lock = threading.Lock()

        self.logger.info(f"任务调度器初始化完成，最大并发: {max_concurrent_tasks}")

    async def start_task(
        self,
        task_id: str,
        streaming_account_id: str,
        streaming_account_email: str,
        streaming_account_password: str,
        game_accounts: List[Dict[str, Any]],
        assigned_xbox: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        启动自动化任务

        参数：
        - task_id: 任务ID
        - streaming_account_id: 串流账号ID
        - streaming_account_email: 串流账号邮箱
        - streaming_account_password: 串流账号密码
        - game_accounts: 游戏账号列表
        - assigned_xbox: 分配的Xbox主机（可选）

        返回：
        - bool: 是否成功启动
        """
        if task_id in self._running_tasks:
            self.logger.warning(f"任务 {task_id} 已在运行中")
            return False

        self.logger.info(f"启动任务: {task_id}, 串流账号: {streaming_account_email}")

        context = AgentTaskContext(
            task_id=task_id,
            streaming_account_id=streaming_account_id,
            streaming_account_email=streaming_account_email,
            streaming_account_password=streaming_account_password,
            window_id=f"window_{task_id}"
        )

        context.game_accounts = [
            GameAccountInfo(
                id=ga.get("id", ""),
                gamertag=ga.get("gamertag", ""),
                email=ga.get("email", ""),
                password=ga.get("password", ""),
                is_primary=ga.get("isPrimary", False),
                target_matches=ga.get("targetMatches", 3)
            )
            for ga in game_accounts
        ]

        if assigned_xbox:
            context.assigned_xbox = XboxInfo(
                id=assigned_xbox.get("id", ""),
                name=assigned_xbox.get("name", "Xbox"),
                ip_address=assigned_xbox.get("ipAddress", ""),
                live_id=assigned_xbox.get("liveId", ""),
                mac_address=assigned_xbox.get("macAddress", "")
            )

        cancel_event = asyncio.Event()
        cancel_event.set()

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

            with self._lock:
                self._task_results[task_id] = AutomationResult(
                    success=False,
                    error_code="CANCELLED",
                    message="任务被取消"
                )

        except Exception as e:
            self.logger.error(f"任务 {task_id} 执行异常: {e}", exc_info=True)

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
