"""
任务上下文单元测试
==================

测试任务上下文数据结构的创建、状态更新等功能

作者：技术团队
版本：1.0
"""

import pytest
import asyncio
from agent.automation.task_context import (
    AgentTaskContext,
    GameAccountInfo,
    XboxInfo,
    WindowInfo,
    TaskStepStatus,
    TaskMainStatus,
    StepStatus,
    AutomationResult,
    Step1Result,
    Step2Result,
    Step3Result,
    Step4Result
)


class TestGameAccountInfo:
    """游戏账号信息测试"""

    def test_create_game_account_info(self):
        """测试创建游戏账号信息"""
        ga = GameAccountInfo(
            id="ga_001",
            gamertag="TestPlayer",
            email="test@example.com",
            password="password123",
            is_primary=True,
            target_matches=3
        )

        assert ga.id == "ga_001"
        assert ga.gamertag == "TestPlayer"
        assert ga.email == "test@example.com"
        assert ga.password == "password123"
        assert ga.is_primary is True
        assert ga.target_matches == 3

    def test_default_target_matches(self):
        """测试默认目标比赛数"""
        ga = GameAccountInfo(id="ga_001", gamertag="TestPlayer")
        assert ga.target_matches == 3


class TestXboxInfo:
    """Xbox主机信息测试"""

    def test_create_xbox_info(self):
        """测试创建Xbox主机信息"""
        xbox = XboxInfo(
            id="xbox_001",
            name="MyXbox",
            ip_address="192.168.1.100",
            live_id="ABC123",
            mac_address="00:11:22:33:44:55"
        )

        assert xbox.id == "xbox_001"
        assert xbox.name == "MyXbox"
        assert xbox.ip_address == "192.168.1.100"
        assert xbox.live_id == "ABC123"
        assert xbox.mac_address == "00:11:22:33:44:55"

    def test_empty_xbox_info(self):
        """测试创建空的Xbox信息"""
        xbox = XboxInfo()
        assert xbox.id == ""
        assert xbox.name == ""
        assert xbox.ip_address == ""


class TestAgentTaskContext:
    """Agent任务上下文测试"""

    def test_create_task_context(self):
        """测试创建任务上下文"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="stream@example.com",
            streaming_account_password="password123"
        )

        assert context.task_id == "task_001"
        assert context.streaming_account_id == "sa_001"
        assert context.streaming_account_email == "stream@example.com"
        assert context.streaming_account_password == "password123"
        assert context.task_status == TaskMainStatus.PENDING
        assert context.current_step == "PENDING"

    def test_pause_event_initialization(self):
        """测试暂停事件初始化"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        assert context.pause_event is not None
        assert context.pause_event.is_set() is True

    def test_update_step_status(self):
        """测试更新步骤状态"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        context.update_step_status("step1", TaskStepStatus.RUNNING, "步骤1执行中")

        assert context.step1_status.status == TaskStepStatus.RUNNING
        assert context.step1_status.message == "步骤1执行中"
        assert context.step1_status.start_time is not None

    def test_update_step_status_to_completed(self):
        """测试更新步骤状态为完成"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        context.update_step_status("step1", TaskStepStatus.RUNNING, "执行中")
        context.update_step_status("step1", TaskStepStatus.COMPLETED, "完成")

        assert context.step1_status.status == TaskStepStatus.COMPLETED
        assert context.step1_status.end_time is not None

    def test_update_task_status(self):
        """测试更新任务主状态"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        context.update_task_status(TaskMainStatus.RUNNING, "任务运行中")

        assert context.task_status == TaskMainStatus.RUNNING
        assert context.current_step == "RUNNING"

    def test_get_step_status_dict(self):
        """测试获取步骤状态字典"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        status_dict = context.get_step_status_dict()

        assert "step1" in status_dict
        assert "step2" in status_dict
        assert "step3" in status_dict
        assert "step4" in status_dict
        assert status_dict["step1"] == "pending"

    def test_pause_and_resume(self):
        """测试暂停和恢复"""
        context = AgentTaskContext(
            task_id="task_001",
            streaming_account_id="sa_001",
            streaming_account_email="test@example.com",
            streaming_account_password="password123"
        )

        assert context.is_paused() is False

        context.pause()
        assert context.is_paused() is True
        assert context.pause_event.is_set() is False

        context.resume()
        assert context.is_paused() is False
        assert context.pause_event.is_set() is True


class TestStepStatus:
    """步骤状态测试"""

    def test_create_step_status(self):
        """测试创建步骤状态"""
        status = StepStatus(name="STEP1")
        assert status.name == "STEP1"
        assert status.status == TaskStepStatus.PENDING
        assert status.message == ""

    def test_to_dict(self):
        """测试转换为字典"""
        status = StepStatus(name="STEP1", status=TaskStepStatus.COMPLETED, message="完成")
        status.end_time = 1234567890.0

        d = status.to_dict()

        assert d["name"] == "STEP1"
        assert d["status"] == "completed"
        assert d["message"] == "完成"
        assert d["endTime"] == 1234567890.0


class TestAutomationResult:
    """自动化结果测试"""

    def test_success_result(self):
        """测试成功结果"""
        result = AutomationResult(success=True, message="任务完成", total_matches=10)
        assert result.success is True
        assert result.message == "任务完成"
        assert result.total_matches == 10

    def test_failed_result(self):
        """测试失败结果"""
        result = AutomationResult(
            success=False,
            failed_step="STEP2",
            error_code="XBOX_CONNECT_FAILED",
            message="Xbox连接失败"
        )
        assert result.success is False
        assert result.failed_step == "STEP2"
        assert result.error_code == "XBOX_CONNECT_FAILED"


class TestStepResults:
    """步骤结果测试"""

    def test_step1_result_success(self):
        """测试步骤1成功结果"""
        result = Step1Result(success=True, message="登录成功")
        assert result.success is True
        assert result.message == "登录成功"

    def test_step1_result_failure(self):
        """测试步骤1失败结果"""
        result = Step1Result(
            success=False,
            error_code="INVALID_CREDENTIALS",
            message="账号密码错误"
        )
        assert result.success is False
        assert result.error_code == "INVALID_CREDENTIALS"

    def test_step2_result_success(self):
        """测试步骤2成功结果"""
        xbox = XboxInfo(name="MyXbox", ip_address="192.168.1.100")
        result = Step2Result(success=True, message="连接成功", xbox_info=xbox)
        assert result.success is True
        assert result.xbox_info.name == "MyXbox"

    def test_step4_result_success(self):
        """测试步骤4成功结果"""
        result = Step4Result(success=True, message="完成10场比赛", total_matches=10)
        assert result.success is True
        assert result.total_matches == 10


class TestTaskEnums:
    """任务枚举测试"""

    def test_step_status_values(self):
        """测试步骤状态枚举值"""
        assert TaskStepStatus.PENDING.value == "pending"
        assert TaskStepStatus.RUNNING.value == "running"
        assert TaskStepStatus.COMPLETED.value == "completed"
        assert TaskStepStatus.FAILED.value == "failed"
        assert TaskStepStatus.SKIPPED.value == "skipped"

    def test_main_status_values(self):
        """测试任务主状态枚举值"""
        assert TaskMainStatus.PENDING.value == "pending"
        assert TaskMainStatus.RUNNING.value == "running"
        assert TaskMainStatus.PAUSED.value == "paused"
        assert TaskMainStatus.COMPLETED.value == "completed"
        assert TaskMainStatus.FAILED.value == "failed"
        assert TaskMainStatus.CANCELLED.value == "cancelled"
