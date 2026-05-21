"""
任务工厂 - 统一管理和创建不同类型的自动化任务

功能说明：
- 根据任务类型创建对应的任务实例
- 支持动态注册新的任务类型
- 提供统一的任务执行入口

任务类型注册：
- stream_control: 串流控制任务
- xbox_automation: Xbox游戏自动化任务
- game_training: 游戏训练任务（预留）
- custom_action: 自定义操作任务（预留）
"""
from typing import Dict, Any, Optional, Callable
from enum import Enum
from importlib import import_module

from .base_task import BaseAutomationTask
from .platform_api_client import PlatformApiClient


class TaskType(Enum):
    """任务类型枚举"""
    STREAM_CONTROL = "stream_control"
    XBOX_AUTOMATION = "xbox_automation"
    GAME_TRAINING = "game_training"
    CUSTOM_ACTION = "custom_action"


class TaskFactory:
    """
    任务工厂类

    负责根据任务类型创建对应的任务实例
    """

    # 任务类型到任务类的映射
    _task_registry: Dict[str, Callable] = {}

    @classmethod
    def register_task(cls, task_type: str, task_class: Callable):
        """
        注册任务类型

        参数：
        - task_type: 任务类型标识
        - task_class: 任务类（需要继承自BaseAutomationTask）
        """
        cls._task_registry[task_type] = task_class
        print(f"注册任务类型: {task_type} -> {task_class.__name__}")

    @classmethod
    def create_task(cls, task_type: str, task_id: str, params: Dict[str, Any], 
                    platform_client: Optional[PlatformApiClient] = None) -> BaseAutomationTask:
        """
        创建任务实例

        参数：
        - task_type: 任务类型
        - task_id: 任务ID
        - params: 任务参数
        - platform_client: 平台API客户端（可选）

        返回：
        - BaseAutomationTask: 任务实例

        抛出：
        - ValueError: 未知的任务类型
        """
        if task_type not in cls._task_registry:
            # 尝试动态导入任务类
            cls._try_dynamic_import(task_type)
            
            if task_type not in cls._task_registry:
                raise ValueError(f"未知的任务类型: {task_type}")

        task_class = cls._task_registry[task_type]
        return task_class(task_id, params, platform_client)

    @classmethod
    def _try_dynamic_import(cls, task_type: str):
        """
        尝试动态导入任务模块

        参数：
        - task_type: 任务类型
        """
        try:
            # 尝试导入任务模块
            module_name = f"agent.task.{task_type}_task_new"
            module = import_module(module_name)
            
            # 查找任务类（命名规则：任务类型首字母大写 + Task）
            class_name = ''.join(word.capitalize() for word in task_type.split('_')) + 'Task'
            task_class = getattr(module, class_name)
            
            cls.register_task(task_type, task_class)
            print(f"动态导入任务类型: {task_type}")
        except Exception as e:
            print(f"动态导入任务类型失败: {task_type} - {e}")

    @classmethod
    def get_registered_types(cls) -> list:
        """获取所有已注册的任务类型"""
        return list(cls._task_registry.keys())


# 预注册内置任务类型
try:
    from .stream_control_task_new import StreamControlTask
    TaskFactory.register_task(TaskType.STREAM_CONTROL.value, StreamControlTask)
except ImportError as e:
    print(f"预注册StreamControlTask失败: {e}")

try:
    from .automation_task_new import XboxAutomationTask
    TaskFactory.register_task(TaskType.XBOX_AUTOMATION.value, XboxAutomationTask)
except ImportError as e:
    print(f"预注册XboxAutomationTask失败: {e}")