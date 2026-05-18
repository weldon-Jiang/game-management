"""
任务上下文模块
==============

功能说明：
- 定义任务上下文和窗口信息数据结构
- 用于任务执行过程中的数据传递和状态管理

核心数据结构：
- AgentTaskContext: 任务上下文，包含任务执行所需的所有信息
- WindowInfo: 窗口信息，描述一个串流窗口的状态

作者：技术团队
版本：1.0
"""

import asyncio
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class WindowInfo:
    """
    窗口信息数据类

    属性说明：
    - window_id: 窗口唯一标识符
    - task_id: 关联的任务ID
    - streaming_account_id: 流媒体账号ID
    - xbox_ip: Xbox主机IP地址
    - handle: 窗口句柄（HWND）
    - process_id: 进程ID
    - status: 窗口状态（created/running/closed/error）
    - width: 窗口宽度
    - height: 窗口高度
    - x: 窗口X坐标
    - y: 窗口Y坐标
    - created_at: 创建时间
    - last_active_time: 最后活跃时间
    """
    window_id: str
    task_id: str
    streaming_account_id: str
    xbox_ip: str
    handle: Optional[int] = None
    process_id: Optional[int] = None
    status: str = "created"
    width: int = 1280
    height: int = 720
    x: int = 0
    y: int = 0
    created_at: datetime = None
    last_active_time: datetime = None

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        self.last_active_time = self.created_at


class AgentTaskContext:
    """
    任务上下文类

    功能说明：
    - 封装单个任务执行所需的所有上下文信息
    - 在自动化步骤之间传递数据
    - 管理任务执行状态

    属性说明：
    - task_id: 任务ID
    - streaming_account: 流媒体账号信息
    - game_accounts: 游戏账号列表
    - xbox_host: Xbox主机信息
    - window_info: 窗口信息
    - step_results: 各步骤执行结果
    - shared_data: 步骤间共享数据
    - start_time: 任务开始时间
    - current_step: 当前执行步骤
    - status: 任务状态
    """

    def __init__(self, task_id: str):
        """
        初始化任务上下文

        参数：
        - task_id: 任务唯一标识符
        """
        self.task_id = task_id
        self.streaming_account: Optional[Dict[str, Any]] = None
        self.game_accounts: List[Dict[str, Any]] = []
        self.xbox_host: Optional[Dict[str, Any]] = None
        self.window_info: Optional[WindowInfo] = None
        self.step_results: Dict[str, Any] = {}
        self.shared_data: Dict[str, Any] = {}
        self.start_time: datetime = datetime.now()
        self.current_step: str = ""
        self.status: str = "pending"
        self._lock = asyncio.Lock()

    async def set_streaming_account(self, account: Dict[str, Any]):
        """设置流媒体账号"""
        async with self._lock:
            self.streaming_account = account

    async def add_game_account(self, account: Dict[str, Any]):
        """添加游戏账号"""
        async with self._lock:
            self.game_accounts.append(account)

    async def set_xbox_host(self, host: Dict[str, Any]):
        """设置Xbox主机信息"""
        async with self._lock:
            self.xbox_host = host

    async def set_window_info(self, window_info: WindowInfo):
        """设置窗口信息"""
        async with self._lock:
            self.window_info = window_info

    async def set_step_result(self, step_name: str, result: Any):
        """设置步骤执行结果"""
        async with self._lock:
            self.step_results[step_name] = result

    async def get_step_result(self, step_name: str) -> Any:
        """获取步骤执行结果"""
        async with self._lock:
            return self.step_results.get(step_name)

    async def set_shared_data(self, key: str, value: Any):
        """设置共享数据"""
        async with self._lock:
            self.shared_data[key] = value

    async def get_shared_data(self, key: str, default=None) -> Any:
        """获取共享数据"""
        async with self._lock:
            return self.shared_data.get(key, default)

    async def update_status(self, status: str):
        """更新任务状态"""
        async with self._lock:
            self.status = status

    async def update_current_step(self, step: str):
        """更新当前步骤"""
        async with self._lock:
            self.current_step = step

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示（用于日志和调试）"""
        return {
            'task_id': self.task_id,
            'status': self.status,
            'current_step': self.current_step,
            'streaming_account_id': self.streaming_account.get('id') if self.streaming_account else None,
            'game_account_count': len(self.game_accounts),
            'xbox_ip': self.xbox_host.get('ipAddress') if self.xbox_host else None,
            'window_id': self.window_info.window_id if self.window_info else None,
            'step_results': {k: str(v) for k, v in self.step_results.items()},
            'shared_data_keys': list(self.shared_data.keys()),
            'start_time': self.start_time.isoformat()
        }