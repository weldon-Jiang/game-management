"""
Agent自动化主任务类
====================

功能说明：
- 整合四个步骤的执行
- 管理任务上下文和状态流转
- 处理暂停、恢复、停止等控制命令

作者：技术团队
版本：1.0
"""

import asyncio
from typing import Callable, Optional, Any, Dict

from ..core.logger import get_logger
from .task_context import (
    AgentTaskContext,
    AutomationResult,
    TaskMainStatus
)
from .task_window_manager import TaskWindowManager
from .step1_stream_account_login import step1_execute_login
from .step2_xbox_streaming import step2_execute_streaming
from .step3_gpu_decode import step3_execute_decode
from .step4_game_automation import step4_execute_gaming
from .platform_api_client import PlatformApiClient


class AgentAutomationTask:
    """
    Agent自动化任务执行器

    整合Step1、Step2、Step3、Step4的执行，管理任务生命周期

    重要原则：
    - 一个AgentAutomationTask对象对应一个串流账号、一个任务、一个窗口
    - 任务与窗口一一对应，不可复用
    - 任务完成后窗口自动关闭
    """

    def __init__(
        self,
        context: AgentTaskContext,
        window_manager: TaskWindowManager,
        platform_client: Optional[PlatformApiClient] = None
    ):
        """
        初始化自动化任务

        参数：
        - context: 任务上下文（一个串流账号对应一个context）
        - window_manager: 窗口管理器（用于管理窗口生命周期）
        - platform_client: Platform API客户端（可选）
        """
        self.context = context
        self.window_manager = window_manager
        self.platform_client = platform_client or PlatformApiClient()
        self.logger = get_logger(f'automation_task_{context.task_id}')
        self.window_info = None

    async def execute(self, check_cancel: Callable[[], bool]) -> AutomationResult:
        """
        执行自动化任务（四个步骤）

        流程：
        1. 步骤一：串流账号登录
        2. 步骤二：Xbox串流连接
        3. 步骤三：显卡解码流转
        4. 步骤四：游戏比赛自动化

        参数：
        - check_cancel: 取消检查函数

        返回：
        - AutomationResult: 最终执行结果
        """
        self.logger.info(f"=== 开始执行自动化任务: {self.context.task_id} ===")
        self.context.update_task_status(TaskMainStatus.RUNNING, "任务开始执行")

        try:
            step1_result = await step1_execute_login(
                self.context,
                check_cancel,
                self._report_progress
            )

            if not step1_result.success:
                self.logger.error(f"步骤一失败: {step1_result.message}")
                await self._cleanup()
                return AutomationResult(
                    success=False,
                    failed_step="STEP1",
                    message=step1_result.message,
                    error_code=step1_result.error_code
                )

            step2_result = await step2_execute_streaming(
                self.context,
                check_cancel,
                self._report_progress
            )

            if not step2_result.success:
                self.logger.error(f"步骤二失败: {step2_result.message}")
                await self._cleanup()
                return AutomationResult(
                    success=False,
                    failed_step="STEP2",
                    message=step2_result.message,
                    error_code=step2_result.error_code
                )

            step3_result = await step3_execute_decode(
                self.context,
                check_cancel,
                self._report_progress
            )

            if not step3_result.success:
                self.logger.error(f"步骤三失败: {step3_result.message}")
                await self._cleanup()
                return AutomationResult(
                    success=False,
                    failed_step="STEP3",
                    message=step3_result.message,
                    error_code=step3_result.error_code
                )

            step4_result = await step4_execute_gaming(
                self.context,
                check_cancel,
                self._report_progress,
                self.platform_client
            )

            if not step4_result.success:
                self.logger.error(f"步骤四失败: {step4_result.message}")
                await self._cleanup()
                return AutomationResult(
                    success=False,
                    failed_step="STEP4",
                    message=step4_result.message,
                    error_code=step4_result.error_code
                )

            success_msg = f"自动化任务完成，共完成 {step4_result.total_matches} 场比赛"
            self.logger.info(f"=== {success_msg} ===")
            self.context.update_task_status(TaskMainStatus.COMPLETED, success_msg)
            await self._report_progress(self.context.task_id, "COMPLETED", "COMPLETED", success_msg)

            await self._cleanup()

            return AutomationResult(
                success=True,
                message=success_msg,
                total_matches=step4_result.total_matches
            )

        except asyncio.CancelledError:
            self.logger.info("任务被取消")
            self.context.update_task_status(TaskMainStatus.CANCELLED, "任务被取消")
            await self._report_progress(
                self.context.task_id, "CANCELLED", "CANCELLED", "任务被取消"
            )
            await self._cleanup()
            return AutomationResult(
                success=False,
                error_code="CANCELLED",
                message="任务被取消"
            )

        except Exception as e:
            error_msg = f"任务执行异常: {str(e)}"
            self.logger.error(f"{error_msg}", exc_info=True)
            self.context.update_task_status(TaskMainStatus.FAILED, error_msg)
            await self._report_progress(
                self.context.task_id,
                "FAILED",
                "FAILED",
                error_msg
            )
            await self._cleanup()
            return AutomationResult(
                success=False,
                error_code="EXCEPTION",
                message=error_msg
            )

    async def pause(self):
        """暂停任务"""
        self.context.pause()
        self.logger.info("任务已暂停")
        await self._report_progress(
            self.context.task_id,
            "PAUSED",
            "PAUSED",
            "任务已暂停"
        )

    async def resume(self):
        """恢复任务"""
        self.context.resume()
        self.logger.info("任务已恢复")
        await self._report_progress(
            self.context.task_id,
            "RESUMED",
            "RUNNING",
            "任务已恢复"
        )

    async def stop(self):
        """停止任务"""
        self.logger.info("请求停止任务")
        self.context.pause_event.set()
        if self.platform_client:
            await self.platform_client.close()

    async def _report_progress(
        self,
        task_id: str,
        step: str,
        status: str,
        message: str,
        **kwargs
    ):
        """
        上报进度到平台

        参数：
        - task_id: 任务ID
        - step: 当前步骤
        - status: 状态
        - message: 消息
        - **kwargs: 其他字段
        """
        if self.platform_client:
            await self.platform_client.report_task_progress(
                task_id, step, status, message, **kwargs
            )

    async def _cleanup(self):
        """清理任务资源并关闭窗口"""
        try:
            if self.context.xbox_session:
                try:
                    await self.context.xbox_session.disconnect()
                except Exception as e:
                    self.logger.warning(f"断开Xbox会话失败: {e}")

            if self.window_info and self.window_manager:
                try:
                    await self.window_manager.close_window(self.window_info.window_id)
                except Exception as e:
                    self.logger.warning(f"关闭窗口失败: {e}")

            self.logger.info(f"任务 {self.context.task_id} 资源已清理")

        except Exception as e:
            self.logger.error(f"清理资源时出错: {e}")
