"""
Bend Agent 任务模块
===================

功能说明：
- 任务调度和执行管理
- 自动化任务编排
- 任务上下文管理

模块结构：
- task_context: 任务上下文管理
- task_executor: 任务执行器
- automation_task: 自动化任务类
- automation_scheduler: 任务调度器

作者：技术团队
版本：1.0
"""

from .task_context import (
    AgentTaskContext,
    GameAccountInfo,
    XboxInfo,
    WindowInfo,
    StepStatus,
    Step1Result,
    Step2Result,
    Step3Result,
    Step4Result,
    AutomationResult,
    TaskStepStatus,
    TaskMainStatus
)

# task_executor 不在 __init__.py 中导入，避免初始化问题
# 运行时通过 from .task_executor import TaskExecutor 导入

__all__ = [
    'AgentTaskContext',
    'GameAccountInfo',
    'XboxInfo',
    'WindowInfo',
    'StepStatus',
    'Step1Result',
    'Step2Result',
    'Step3Result',
    'Step4Result',
    'AutomationResult',
    'TaskStepStatus',
    'TaskMainStatus',
]