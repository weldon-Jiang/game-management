"""暂停期或 Step4 自动化外拦截虚拟手柄输入。"""

from typing import Callable, Optional


class InputGate:
    """
    自动化未激活或任务暂停时拦截 gamepad/DataChannel 输入。

    Step4 运行期间设 automation_active=True；暂停仅清输入，不关串流。
    """

    def __init__(self, is_paused: Callable[[], bool]):
        self._is_paused = is_paused
        self._automation_active = False

    def set_automation_active(self, active: bool) -> None:
        """
        标记 Step4 是否占用虚拟手柄。

        Step1-3 仅建立串流/input 通道，须保持 False，避免 READY 或
        场景准备阶段误发自动化按键。
        """
        self._automation_active = active

    @property
    def automation_active(self) -> bool:
        return self._automation_active

    def is_allowed(self) -> bool:
        """
        仅当 Step4 运行且未暂停时返回 True。

        同步热路径检查，位于每次虚拟手柄/DataChannel 发送之前。
        """
        if not self._automation_active:
            return False
        return not self._is_paused()
