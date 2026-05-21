"""
基础任务接口 - 统一所有自动化任务的执行框架

功能说明：
- 定义自动化任务的标准接口
- 提供统一的状态上报机制
- 支持步骤状态和子任务状态上报
- 支持取消检查和超时处理

所有自动化任务类型都应继承此类并实现 execute 方法
"""
import asyncio
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Callable, List
from enum import Enum
from datetime import datetime

from ..core.logger import get_logger
from ..api.platform_api_client import PlatformApiClient


class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMEOUT = "timeout"


class StepStatus(Enum):
    """步骤状态枚举"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class BaseAutomationTask(ABC):
    """
    自动化任务基类

    所有自动化任务类型都应继承此类并实现以下方法：
    - _execute_steps(): 执行具体的任务步骤

    属性：
    - task_id: 任务ID
    - task_type: 任务类型
    - status: 当前任务状态
    - current_step: 当前执行步骤
    - step_status: 步骤状态字典
    - platform_client: 平台API客户端
    """

    def __init__(self, task_id: str, task_type: str, platform_client: Optional[PlatformApiClient] = None):
        self.task_id = task_id
        self.task_type = task_type
        self.status = TaskStatus.PENDING
        self.current_step = None
        self.step_status: Dict[str, str] = {}
        self.platform_client = platform_client or PlatformApiClient()
        self.logger = get_logger(f'task_{task_type}_{task_id}')
        self._cancel_event = asyncio.Event()
        self._start_time = None

    def cancel(self):
        """取消任务"""
        self._cancel_event.set()
        self.status = TaskStatus.CANCELLED
        self.logger.info(f"任务已取消: {self.task_id}")

    def is_cancelled(self) -> bool:
        """检查任务是否被取消"""
        return self._cancel_event.is_set()

    async def _report_task_status(self, status: TaskStatus, message: Optional[str] = None):
        """上报任务状态到平台"""
        self.status = status
        try:
            await self.platform_client.report_task_status(
                self.task_id,
                status.value,
                message
            )
            self.logger.debug(f"上报任务状态: {status.value}, 消息: {message}")
        except Exception as e:
            self.logger.error(f"上报任务状态失败: {e}")

    async def _report_step_status(self, step_name: str, status: StepStatus, message: Optional[str] = None):
        """上报步骤状态到平台"""
        self.current_step = step_name
        self.step_status[step_name] = status.value
        
        try:
            await self.platform_client.report_task_progress(
                self.task_id,
                step_name,
                status.value,
                message
            )
            self.logger.debug(f"上报步骤状态: {step_name} -> {status.value}, 消息: {message}")
        except Exception as e:
            self.logger.error(f"上报步骤状态失败: {e}")

    async def _report_subtask_status(self, subtask_id: str, status: str, 
                                    today_completed: Optional[int] = None, 
                                    daily_limit: Optional[int] = None):
        """上报子任务状态到平台"""
        try:
            await self.platform_client.update_game_account_status(
                self.task_id,
                subtask_id,
                status,
                today_completed,
                daily_limit
            )
            self.logger.debug(f"上报子任务状态: {subtask_id} -> {status}")
        except Exception as e:
            self.logger.error(f"上报子任务状态失败: {e}")

    @abstractmethod
    async def _execute_steps(self, check_cancel: Callable[[], bool]) -> Dict[str, Any]:
        """
        执行具体的任务步骤（子类必须实现）

        参数：
        - check_cancel: 取消检查函数

        返回：
        - 任务执行结果
        """
        pass

    async def execute(self, timeout_seconds: int = 3600) -> Dict[str, Any]:
        """
        执行任务（统一入口）

        参数：
        - timeout_seconds: 超时时间（秒），默认3600秒

        返回：
        - 任务执行结果
        """
        self._start_time = datetime.now()
        
        try:
            await self._report_task_status(TaskStatus.RUNNING, "任务开始执行")
            self.logger.info(f"=== 开始执行任务: {self.task_id}, 类型: {self.task_type} ===")

            def check_cancel():
                if self.is_cancelled():
                    return True
                # 检查超时
                if timeout_seconds > 0:
                    elapsed = (datetime.now() - self._start_time).total_seconds()
                    if elapsed > timeout_seconds:
                        self.logger.error(f"任务超时: {self.task_id}")
                        raise asyncio.TimeoutError(f"任务执行超时 ({timeout_seconds}秒)")
                return False

            result = await self._execute_steps(check_cancel)

            if self.is_cancelled():
                await self._report_task_status(TaskStatus.CANCELLED, "任务被取消")
                return {
                    'success': False,
                    'taskId': self.task_id,
                    'error': '任务被取消'
                }

            await self._report_task_status(TaskStatus.COMPLETED, "任务执行完成")
            self.logger.info(f"任务执行完成: {self.task_id}")
            
            return {
                'success': True,
                'taskId': self.task_id,
                'result': result,
                'stepStatus': self.step_status
            }

        except asyncio.TimeoutError as e:
            await self._report_task_status(TaskStatus.TIMEOUT, str(e))
            self.logger.error(f"任务超时: {self.task_id} - {e}")
            return {
                'success': False,
                'taskId': self.task_id,
                'error': str(e)
            }

        except Exception as e:
            await self._report_task_status(TaskStatus.FAILED, str(e))
            self.logger.error(f"任务执行失败: {self.task_id} - {e}", exc_info=True)
            return {
                'success': False,
                'taskId': self.task_id,
                'error': str(e),
                'stepStatus': self.step_status
            }