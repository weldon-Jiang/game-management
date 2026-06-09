"""
Xbox 手柄信号协议
==================

功能说明：
- 手柄信号的序列化与反序列化
- 通过SmartGlass协议发送到手柄
- 支持XboxStreamController集成
- 支持Xbox发送到手柄信号（优化三）

技术实现参考（streaming项目）：
- xsrp.WriteControllerData(username, signals)
- SmartGlass LAN：XboxStreamController 输入通道

作者：技术团队
版本：2.0（新增send_gamepad_state功能）
"""

import struct
import json
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

from ..core.logger import get_logger


class XboxButtonFlag(Enum):
    """
    xCloud 手柄按钮位掩码（对齐 xsrp.XSGamepadButtons / xsrpst diagrams）。

    参考 xsrpst controller_option[2]：Nexus=2, A=16, DPadDown=512, DPadUp=4096。
    """
    NEXUS = 2
    A = 16
    B = 32
    X = 64
    Y = 128
    VIEW = 256
    DPAD_DOWN = 512
    DPAD_LEFT = 1024
    DPAD_RIGHT = 2048
    DPAD_UP = 4096
    MENU = 8192
    # 别名（兼容旧调用名）
    START = 8192
    SELECT = 256
    L1 = 16384
    R1 = 32768
    L3 = 65536
    R3 = 131072


@dataclass
class ControllerSignal:
    """
    手柄信号数据类

    属性说明：
    - buttons: 位掩码表示的按钮状态
    - left_trigger: 左扳机值 (0-255)
    - right_trigger: 右扳机值 (0-255)
    - left_thumb_x: 左摇杆X轴 (-32768 到 32767)
    - left_thumb_y: 左摇杆Y轴 (-32768 到 32767)
    - right_thumb_x: 右摇杆X轴 (-32768 到 32767)
    - right_thumb_y: 右摇杆Y轴 (-32768 到 32767)
    """
    buttons: int = 0
    left_trigger: int = 0
    right_trigger: int = 0
    left_thumb_x: int = 0
    left_thumb_y: int = 0
    right_thumb_x: int = 0
    right_thumb_y: int = 0

    def set_button(self, button: XboxButtonFlag, pressed: bool = True):
        """设置按钮状态"""
        if pressed:
            self.buttons |= button.value
        else:
            self.buttons &= ~button.value

    def is_button_pressed(self, button: XboxButtonFlag) -> bool:
        """检查按钮是否按下"""
        return bool(self.buttons & button.value)

    def set_trigger(self, trigger: str, value: float):
        """
        设置扳机值

        参数：
        - trigger: 'left' 或 'right'
        - value: 0.0 到 1.0
        """
        value_int = int(max(0, min(255, value * 255)))
        if trigger.lower() == 'left':
            self.left_trigger = value_int
        else:
            self.right_trigger = value_int

    def set_thumb(self, thumb: str, x: float, y: float):
        """
        设置摇杆值

        参数：
        - thumb: 'left' 或 'right'
        - x: -1.0 到 1.0
        - y: -1.0 到 1.0
        """
        x_int = int(max(-32768, min(32767, x * 32767)))
        y_int = int(max(-32768, min(32767, y * 32767)))

        if thumb.lower() == 'left':
            self.left_thumb_x = x_int
            self.left_thumb_y = y_int
        else:
            self.right_thumb_x = x_int
            self.right_thumb_y = y_int

    def to_bytes(self) -> bytes:
        """转换为二进制数据"""
        return struct.pack(
            '!HHHHHHH',
            self.buttons,
            self.left_trigger,
            self.right_trigger,
            self.left_thumb_x,
            self.left_thumb_y,
            self.right_thumb_x,
            self.right_thumb_y
        )

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'buttons': self.buttons,
            'left_trigger': self.left_trigger,
            'right_trigger': self.right_trigger,
            'left_thumb_x': self.left_thumb_x,
            'left_thumb_y': self.left_thumb_y,
            'right_thumb_x': self.right_thumb_x,
            'right_thumb_y': self.right_thumb_y
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ControllerSignal':
        """从字典创建"""
        return cls(
            buttons=data.get('buttons', 0),
            left_trigger=data.get('left_trigger', 0),
            right_trigger=data.get('right_trigger', 0),
            left_thumb_x=data.get('left_thumb_x', 0),
            left_thumb_y=data.get('left_thumb_y', 0),
            right_thumb_x=data.get('right_thumb_x', 0),
            right_thumb_y=data.get('right_thumb_y', 0)
        )

    @classmethod
    def zero(cls) -> 'ControllerSignal':
        """创建零信号（所有值为0）"""
        return cls()

    @classmethod
    def from_gamepad_signal(cls, gamepad_signal) -> 'ControllerSignal':
        """从GamepadSignal创建（兼容xbox_gamepad.py）"""
        signal = cls()
        signal.buttons = gamepad_signal.buttons
        signal.left_trigger = gamepad_signal.left_trigger
        signal.right_trigger = gamepad_signal.right_trigger
        signal.left_thumb_x = gamepad_signal._normalize(gamepad_signal.left_thumbstick_x)
        signal.left_thumb_y = gamepad_signal._normalize(gamepad_signal.left_thumbstick_y)
        signal.right_thumb_x = gamepad_signal._normalize(gamepad_signal.right_thumbstick_x)
        signal.right_thumb_y = gamepad_signal._normalize(gamepad_signal.right_thumbstick_y)
        return signal


class ControllerProtocol:
    """
    手柄信号协议处理器

    功能说明：
    - 管理Xbox SmartGlass协议中的手柄信号
    - 发送信号到Xbox流会话
    - 支持动作序列执行

    使用方式：
    - 创建实例后调用 send_signal() 发送信号
    - 使用 execute_sequence() 执行动作序列
    """

    def __init__(self, stream_controller=None):
        self.logger = get_logger('controller_protocol')
        self._stream_controller = stream_controller
        self._input_gate = None

    def set_input_gate(self, gate) -> None:
        """绑定 InputGate：暂停/非自动化期拦截 send_signal。"""
        self._input_gate = gate

    def set_stream_controller(self, controller):
        """
        设置流控制器

        参数：
        - controller: XboxStreamController 实例
        """
        self._stream_controller = controller
        controller_name = type(controller).__name__ if controller else "None"
        self.logger.info(f"流控制器已设置: {controller_name}")

    async def send_signal(self, signal: ControllerSignal) -> bool:
        """
        发送手柄信号到Xbox（Step4 自动化路径，受 InputGate 约束）。
        """
        if self._input_gate is not None and not self._input_gate.is_allowed():
            return False
        return await self._send_signal_ungated(signal)

    async def send_manual_signal(self, signal: ControllerSignal) -> bool:
        """
        人工操控路径（READY 阶段 InputPump / 物理手柄），不受 InputGate 拦截。
        """
        return await self._send_signal_ungated(signal)

    async def _send_signal_ungated(self, signal: ControllerSignal) -> bool:
        if not self._stream_controller:
            self.logger.warning("未设置流控制器，无法发送信号")
            return False

        try:
            return await self._stream_controller.send_gamepad_state(
                signal.to_dict()
            )
        except Exception as e:
            self.logger.error(f"发送手柄信号失败: {e}")
            return False

    async def send_signal_continuous(
        self,
        signal: ControllerSignal,
        duration: float = 0.1
    ) -> bool:
        """
        发送持续手柄信号（优化三）

        功能说明：
        - 发送手柄信号并保持一段时间
        - 然后发送零信号释放

        参数：
        - signal: 手柄信号数据
        - duration: 持续时间（秒）

        返回：
        - True: 发送成功
        - False: 发送失败
        """
        import asyncio

        if not self._stream_controller:
            self.logger.warning("未设置流控制器，无法发送信号")
            return False

        success1 = await self.send_signal(signal)
        await asyncio.sleep(duration)

        zero_signal = ControllerSignal.zero()
        success2 = await self.send_signal(zero_signal)

        return success1 and success2

    async def press_button(self, button: XboxButtonFlag, duration: float = 0.1):
        """
        按下手柄按钮

        参数：
        - button: 按钮
        - duration: 按下持续时间（秒）
        """
        import asyncio

        signal = ControllerSignal()
        signal.set_button(button, True)
        self.logger.info(f"[手柄操作] 按下按钮: {button.name}")
        await self.send_signal(signal)

        await asyncio.sleep(duration)

        signal.set_button(button, False)
        self.logger.info(f"[手柄操作] 释放按钮: {button.name}")
        await self.send_signal(signal)

    async def move_thumb(self, thumb: str, x: float, y: float, duration: float = 0.1):
        """
        移动摇杆

        参数：
        - thumb: 'left' 或 'right'
        - x: X轴值 (-1.0 到 1.0)
        - y: Y轴值 (-1.0 到 1.0)
        - duration: 持续时间（秒）
        """
        import asyncio

        signal = ControllerSignal()
        signal.set_thumb(thumb, x, y)
        thumb_name = thumb.upper()
        self.logger.info(f"[手柄操作] 移动{thumb_name}摇杆: ({x:.2f}, {y:.2f})")
        await self.send_signal(signal)

        await asyncio.sleep(duration)

        zero_signal = ControllerSignal()
        self.logger.info(f"[手柄操作] 释放{thumb_name}摇杆")
        await self.send_signal(zero_signal)

    async def execute_sequence(self, sequence: List[Dict[str, Any]]):
        """
        执行动作序列

        参数：
        - sequence: 动作序列，每项包含 type、params、duration

        示例：
        [
            {"type": "button", "button": "A", "duration": 0.1},
            {"type": "thumb", "thumb": "left", "x": 0, "y": -1, "duration": 0.5},
            {"type": "wait", "duration": 0.2}
        ]
        """
        import asyncio

        for action in sequence:
            action_type = action.get('type')

            if action_type == 'button':
                button = XboxButtonFlag[action.get('button', 'A')]
                duration = action.get('duration', 0.1)
                await self.press_button(button, duration)

            elif action_type == 'thumb':
                thumb = action.get('thumb', 'left')
                x = action.get('x', 0)
                y = action.get('y', 0)
                duration = action.get('duration', 0.1)
                await self.move_thumb(thumb, x, y, duration)

            elif action_type == 'wait':
                duration = action.get('duration', 0.1)
                await asyncio.sleep(duration)

    async def navigate_to(self, path: List[str]):
        """
        导航到指定位置（模拟手柄导航）

        参数：
        - path: 导航路径，如 ['up', 'up', 'right', 'A']

        支持的方向：up, down, left, right
        支持的确认：A, B
        """
        button_map = {
            'up': XboxButtonFlag.DPAD_UP,
            'down': XboxButtonFlag.DPAD_DOWN,
            'left': XboxButtonFlag.DPAD_LEFT,
            'right': XboxButtonFlag.DPAD_RIGHT,
            'a': XboxButtonFlag.A,
            'b': XboxButtonFlag.B
        }

        for action in path:
            action_lower = action.lower()
            if action_lower in button_map:
                self.logger.info(f"[手柄操作] 导航: {action}")
                await self.press_button(button_map[action_lower])
            else:
                self.logger.warning(f"未知导航动作: {action}")


controller_protocol = ControllerProtocol()
