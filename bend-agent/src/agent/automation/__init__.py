"""
Bend Agent 自动化模块
====================

功能说明：
- 负责执行自动化任务（串流账号登录 -> Xbox串流 -> 游戏比赛）
- 支持多并发任务执行，每个串流账号对应一个独立窗口
- 实时同步任务状态到平台

模块结构：
- task_context: 任务上下文管理
- task_window_manager: 窗口管理器（一个任务一个窗口）
- step1_stream_account_login: 步骤一：串流账号登录
- step2_xbox_streaming: 步骤二：Xbox串流连接
- step3_gpu_decode: 步骤三：显卡解码流转
- step4_game_automation: 步骤四：游戏比赛自动化
- platform_api_client: 平台API客户端（实时同步）
- automation_task: 主自动化任务类
- automation_scheduler: 任务调度器（协程管理）

作者：技术团队
版本：1.0
"""

from .task_context import AgentTaskContext, GameAccountInfo, WindowInfo
from .task_window_manager import TaskWindowManager
from .automation_task import AgentAutomationTask
from .automation_scheduler import AutomationScheduler

__all__ = [
    'AgentTaskContext',
    'GameAccountInfo',
    'WindowInfo',
    'TaskWindowManager',
    'AgentAutomationTask',
    'AutomationScheduler',
]