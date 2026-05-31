"""
组件健康检查
==============

功能说明：
- 追踪组件健康状态
- 提供统一的状态报告
- 支持状态变更回调

作者：技术团队
版本：1.0
"""

import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field


class ComponentStatus(Enum):
    """
    组件状态枚举
    """
    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    OFFLINE = "offline"


@dataclass
class ComponentHealthInfo:
    """
    组件健康信息
    """
    name: str
    status: ComponentStatus = ComponentStatus.UNKNOWN
    message: str = ""
    last_check: Optional[datetime] = None
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class ComponentHealth:
    """
    组件健康检查器

    功能说明：
    - 管理多个组件的健康状态
    - 提供统一的状态查询接口
    - 支持状态变更通知
    """

    def __init__(self):
        """
        初始化健康检查器
        """
        self._components: Dict[str, ComponentHealthInfo] = {}
        self._status_callbacks: List[Callable[[str, ComponentStatus, ComponentStatus], None]] = []
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger('health_check')

    def register_component(
        self,
        name: str,
        initial_status: ComponentStatus = ComponentStatus.UNKNOWN,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        注册组件

        参数：
        - name: 组件名称
        - initial_status: 初始状态
        - metadata: 元数据
        """
        if name not in self._components:
            self._components[name] = ComponentHealthInfo(
                name=name,
                status=initial_status,
                metadata=metadata or {}
            )
            self._logger.info(f"Registered component: {name}")

    def update_status(
        self,
        name: str,
        status: ComponentStatus,
        message: str = "",
        error: Optional[str] = None
    ) -> None:
        """
        更新组件状态

        参数：
        - name: 组件名称
        - status: 新状态
        - message: 状态消息
        - error: 错误信息
        """
        if name not in self._components:
            self._logger.warning(f"Component not registered: {name}")
            return

        component = self._components[name]
        old_status = component.status

        component.status = status
        component.message = message
        component.last_check = datetime.now()

        if error:
            component.error_count += 1
            component.last_error = error

        if old_status != status:
            self._logger.info(f"Component {name} status changed: {old_status.value} -> {status.value}")
            self._notify_status_change(name, old_status, status)

    def mark_healthy(self, name: str, message: str = "") -> None:
        """
        标记组件为健康

        参数：
        - name: 组件名称
        - message: 状态消息
        """
        self.update_status(name, ComponentStatus.HEALTHY, message)

    def mark_degraded(self, name: str, message: str = "") -> None:
        """
        标记组件为降级

        参数：
        - name: 组件名称
        - message: 状态消息
        """
        self.update_status(name, ComponentStatus.DEGRADED, message)

    def mark_unhealthy(self, name: str, error: str) -> None:
        """
        标记组件为不健康

        参数：
        - name: 组件名称
        - error: 错误信息
        """
        self.update_status(name, ComponentStatus.UNHEALTHY, error=error)

    def mark_offline(self, name: str, message: str = "") -> None:
        """
        标记组件为离线

        参数：
        - name: 组件名称
        - message: 状态消息
        """
        self.update_status(name, ComponentStatus.OFFLINE, message)

    def get_status(self, name: str) -> ComponentStatus:
        """
        获取组件状态

        参数：
        - name: 组件名称

        返回：
        - 组件状态
        """
        if name not in self._components:
            return ComponentStatus.UNKNOWN
        return self._components[name].status

    def get_info(self, name: str) -> Optional[ComponentHealthInfo]:
        """
        获取组件健康信息

        参数：
        - name: 组件名称

        返回：
        - 组件健康信息
        """
        return self._components.get(name)

    def is_healthy(self) -> bool:
        """
        检查是否所有组件都健康

        返回：
        - 是否所有组件健康
        """
        return all(
            c.status in (ComponentStatus.HEALTHY, ComponentStatus.UNKNOWN)
            for c in self._components.values()
        )

    def get_overall_status(self) -> ComponentStatus:
        """
        获取整体状态

        返回：
        - 整体状态
        """
        if not self._components:
            return ComponentStatus.UNKNOWN

        statuses = [c.status for c in self._components.values()]

        if all(s == ComponentStatus.HEALTHY for s in statuses):
            return ComponentStatus.HEALTHY

        if any(s == ComponentStatus.UNHEALTHY for s in statuses):
            return ComponentStatus.UNHEALTHY

        if any(s == ComponentStatus.OFFLINE for s in statuses):
            return ComponentStatus.DEGRADED

        if any(s == ComponentStatus.DEGRADED for s in statuses):
            return ComponentStatus.DEGRADED

        return ComponentStatus.UNKNOWN

    def get_report(self) -> Dict[str, Any]:
        """
        获取健康报告

        返回：
        - 健康报告字典
        """
        return {
            'overall_status': self.get_overall_status().value,
            'is_healthy': self.is_healthy(),
            'components': {
                name: {
                    'status': info.status.value,
                    'message': info.message,
                    'last_check': info.last_check.isoformat() if info.last_check else None,
                    'error_count': info.error_count,
                    'metadata': info.metadata
                }
                for name, info in self._components.items()
            },
            'timestamp': datetime.now().isoformat()
        }

    def get_unhealthy_components(self) -> List[str]:
        """
        获取不健康的组件列表

        返回：
        - 不健康组件名称列表
        """
        return [
            name for name, info in self._components.items()
            if info.status in (ComponentStatus.UNHEALTHY, ComponentStatus.OFFLINE)
        ]

    def on_status_change(
        self,
        callback: Callable[[str, ComponentStatus, ComponentStatus], None]
    ) -> None:
        """
        注册状态变更回调

        参数：
        - callback: 回调函数，参数为(组件名, 旧状态, 新状态)
        """
        self._status_callbacks.append(callback)

    def _notify_status_change(
        self,
        name: str,
        old_status: ComponentStatus,
        new_status: ComponentStatus
    ) -> None:
        """
        通知状态变更

        参数：
        - name: 组件名称
        - old_status: 旧状态
        - new_status: 新状态
        """
        for callback in self._status_callbacks:
            try:
                callback(name, old_status, new_status)
            except Exception as e:
                self._logger.error(f"Status change callback error: {e}")

    async def watch_health(
        self,
        interval: float = 30.0,
        on_unhealthy: Optional[Callable[[List[str]], None]] = None
    ) -> None:
        """
        监控健康状态

        参数：
        - interval: 检查间隔（秒）
        - on_unhealthy: 不健康时的回调函数
        """
        while True:
            try:
                await asyncio.sleep(interval)

                unhealthy = self.get_unhealthy_components()
                if unhealthy:
                    self._logger.warning(f"Unhealthy components: {unhealthy}")
                    if on_unhealthy:
                        on_unhealthy(unhealthy)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._logger.error(f"Health watch error: {e}")


GLOBAL_HEALTH: Optional[ComponentHealth] = None


def get_health() -> ComponentHealth:
    """
    获取全局健康检查器

    返回：
    - 全局健康检查器实例
    """
    global GLOBAL_HEALTH
    if GLOBAL_HEALTH is None:
        GLOBAL_HEALTH = ComponentHealth()
    return GLOBAL_HEALTH
