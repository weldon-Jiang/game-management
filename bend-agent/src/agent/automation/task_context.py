"""
任务上下文管理
==============

功能说明：
- 定义Agent自动化任务的数据结构
- 管理任务状态和上下文信息
- 记录每个步骤的执行状态

作者：技术团队
版本：1.0
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum


class TaskStepStatus(Enum):
    """任务步骤状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TaskMainStatus(Enum):
    """任务主状态"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class GameAccountInfo:
    """
    游戏账号信息

    属性说明：
    - id: 游戏账号唯一标识
    - gamertag: 游戏昵称（Xbox Live显示名称）
    - email: 关联的微软账号邮箱
    - password: 密码（已解密）
    - is_primary: 是否为主账号
    - target_matches: 目标比赛数（每天3场）
    """
    id: str
    gamertag: str
    email: str = ""
    password: str = ""
    is_primary: bool = False
    target_matches: int = 3


@dataclass
class XboxInfo:
    """
    Xbox主机信息

    属性说明：
    - id: Xbox主机唯一标识
    - name: Xbox主机名称
    - ip_address: IP地址
    - live_id: Xbox Live ID
    - mac_address: MAC地址
    """
    id: str = ""
    name: str = ""
    ip_address: str = ""
    live_id: str = ""
    mac_address: str = ""


@dataclass
class WindowInfo:
    """
    窗口信息

    属性说明：
    - window_id: 窗口唯一ID
    - streaming_account_id: 关联的串流账号ID
    - task_id: 关联的任务ID
    - window_handle: 窗口句柄
    - state: 窗口状态
    - created_time: 创建时间
    """
    window_id: str
    streaming_account_id: str
    task_id: str
    window_handle: Optional[int] = None
    state: str = "created"
    created_time: Optional[float] = None


@dataclass
class StepStatus:
    """
    步骤状态

    属性说明：
    - name: 步骤名称
    - status: 步骤状态
    - start_time: 开始时间
    - end_time: 结束时间
    - message: 状态消息
    - error: 错误信息
    """
    name: str
    status: TaskStepStatus = TaskStepStatus.PENDING
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    message: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "status": self.status.value,
            "startTime": self.start_time,
            "endTime": self.end_time,
            "message": self.message,
            "error": self.error
        }


@dataclass
class AgentTaskContext:
    """
    Agent自动化任务上下文

    贯穿四个步骤，每个串流账号独有一份

    重要原则：一个AgentTaskContext对象对应一个串流账号、一个任务、一个窗口

    属性说明：
    - task_id: 任务ID（唯一标识）
    - streaming_account_id: 串流账号ID
    - streaming_account_email: 串流账号邮箱
    - streaming_account_password: 串流账号密码（已解密）
    - window_id: 关联的窗口ID
    - game_accounts: 游戏账号列表
    - assigned_xbox: 指定Xbox主机（可选）
    - current_step: 当前步骤
    - task_status: 任务主状态
    - pause_event: 暂停事件
    """

    task_id: str
    streaming_account_id: str
    streaming_account_email: str
    streaming_account_password: str
    window_id: str = ""
    game_accounts: List[GameAccountInfo] = field(default_factory=list)
    assigned_xbox: Optional[XboxInfo] = None

    current_step: str = "PENDING"
    task_status: TaskMainStatus = TaskMainStatus.PENDING
    pause_event: Optional[asyncio.Event] = None

    microsoft_tokens: Optional[Any] = None
    xbox_tokens: Optional[Any] = None
    xbox_session: Optional[Any] = None
    frame_capture: Optional[Any] = None

    current_game_account_index: int = 0
    matches_completed_today: Dict[str, int] = field(default_factory=dict)

    step1_status: StepStatus = field(default_factory=lambda: StepStatus(name="STEP1"))
    step2_status: StepStatus = field(default_factory=lambda: StepStatus(name="STEP2"))
    step3_status: StepStatus = field(default_factory=lambda: StepStatus(name="STEP3"))
    step4_status: StepStatus = field(default_factory=lambda: StepStatus(name="STEP4"))

    last_report_time: float = 0
    report_interval: float = 5.0

    created_at: float = field(default_factory=time.time)

    def __post_init__(self):
        """初始化后处理"""
        if self.pause_event is None:
            self.pause_event = asyncio.Event()
            self.pause_event.set()

    def update_step_status(self, step_name: str, status: TaskStepStatus,
                          message: str = "", error: Optional[str] = None):
        """
        更新步骤状态

        参数：
        - step_name: 步骤名称
        - status: 新状态
        - message: 状态消息
        - error: 错误信息
        """
        step_status = getattr(self, f"{step_name.lower()}_status", None)
        if step_status:
            step_status.status = status
            step_status.message = message
            step_status.error = error

            if status == TaskStepStatus.RUNNING:
                step_status.start_time = time.time()
            elif status in [TaskStepStatus.COMPLETED, TaskStepStatus.FAILED, TaskStepStatus.SKIPPED]:
                step_status.end_time = time.time()

    def update_task_status(self, status: TaskMainStatus, message: str = ""):
        """
        更新任务主状态

        参数：
        - status: 新状态
        - message: 状态消息
        """
        self.task_status = status
        self.current_step = status.value.upper()

    def get_step_status_dict(self) -> Dict[str, str]:
        """
        获取所有步骤状态的字典

        返回：
        - Dict: {step1: "COMPLETED", step2: "RUNNING", ...}
        """
        return {
            "step1": self.step1_status.status.value,
            "step2": self.step2_status.status.value,
            "step3": self.step3_status.status.value,
            "step4": self.step4_status.status.value
        }

    def is_paused(self) -> bool:
        """检查任务是否暂停"""
        return self.pause_event is not None and not self.pause_event.is_set()

    async def wait_if_paused(self):
        """如果任务暂停则等待"""
        if self.pause_event:
            await self.pause_event.wait()

    def pause(self):
        """暂停任务"""
        if self.pause_event:
            self.pause_event.clear()
        self.update_task_status(TaskMainStatus.PAUSED)

    def resume(self):
        """恢复任务"""
        if self.pause_event:
            self.pause_event.set()
        self.update_task_status(TaskMainStatus.RUNNING)


@dataclass
class AutomationResult:
    """
    自动化任务执行结果

    属性说明：
    - success: 是否成功
    - failed_step: 失败的步骤（如果有）
    - message: 结果消息
    - total_matches: 总比赛数
    - error_code: 错误码
    - error_details: 错误详情
    """
    success: bool
    failed_step: Optional[str] = None
    message: str = ""
    total_matches: int = 0
    error_code: Optional[str] = None
    error_details: Optional[str] = None


@dataclass
class Step1Result:
    """步骤一结果：串流账号登录"""
    success: bool
    message: str = ""
    error_code: Optional[str] = None
    microsoft_tokens: Optional[Any] = None
    xbox_tokens: Optional[Any] = None


@dataclass
class Step2Result:
    """步骤二结果：Xbox串流连接"""
    success: bool
    message: str = ""
    error_code: Optional[str] = None
    xbox_info: Optional[XboxInfo] = None


@dataclass
class Step3Result:
    """步骤三结果：显卡解码流转"""
    success: bool
    message: str = ""
    error_code: Optional[str] = None


@dataclass
class Step4Result:
    """步骤四结果：游戏比赛自动化"""
    success: bool
    message: str = ""
    error_code: Optional[str] = None
    total_matches: int = 0
