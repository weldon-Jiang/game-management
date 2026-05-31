"""
Xbox 游戏手柄控制器
====================

功能说明：
- 读取Xbox手柄输入（使用pygame）
- 将手柄输入转换为Xbox协议信号
- 支持按钮、摇杆、扳机操作

技术实现参考（streaming项目）：
- SDL2 GameController (C++)
- 本实现使用 pygame 替代

作者：技术团队
版本：1.0
"""

import asyncio
import pygame
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import IntEnum

from ..core.logger import get_logger


class XboxButton(IntEnum):
    """Xbox手柄按钮枚举（对应pygame常量）"""
    A = pygame.CONTROLLER_BUTTON_A
    B = pygame.CONTROLLER_BUTTON_B
    X = pygame.CONTROLLER_BUTTON_X
    Y = pygame.CONTROLLER_BUTTON_Y
    START = pygame.CONTROLLER_BUTTON_START
    SELECT = pygame.CONTROLLER_BUTTON_BACK
    GUIDE = pygame.CONTROLLER_BUTTON_GUIDE
    L3 = pygame.CONTROLLER_BUTTON_LEFTSTICK
    R3 = pygame.CONTROLLER_BUTTON_RIGHTSTICK
    L1 = pygame.CONTROLLER_BUTTON_LEFTSHOULDER
    R1 = pygame.CONTROLLER_BUTTON_RIGHTSHOULDER
    DPAD_UP = pygame.CONTROLLER_BUTTON_DPAD_UP
    DPAD_DOWN = pygame.CONTROLLER_BUTTON_DPAD_DOWN
    DPAD_LEFT = pygame.CONTROLLER_BUTTON_DPAD_LEFT
    DPAD_RIGHT = pygame.CONTROLLER_BUTTON_DPAD_RIGHT


class XboxAxis(IntEnum):
    """Xbox手柄摇杆枚举"""
    LEFT_X = 0
    LEFT_Y = 1
    RIGHT_X = 2
    RIGHT_Y = 3
    L2 = 4
    R2 = 5


@dataclass
class GamepadInput:
    """手柄输入数据"""
    buttons: Dict[str, bool] = field(default_factory=dict)
    axes: Dict[str, float] = field(default_factory=dict)
    triggers: Dict[str, float] = field(default_factory=dict)

    def is_empty(self) -> bool:
        """检查是否有任何输入"""
        return not any(self.buttons.values()) and \
               not any(abs(v) > 0.1 for v in self.axes.values()) and \
               not any(v > 0.1 for v in self.triggers.values())


@dataclass
class GamepadSignal:
    """手柄信号数据（用于发送到Xbox）"""
    buttons: int = 0
    left_trigger: int = 0
    right_trigger: int = 0
    left_thumbstick_x: int = 0
    left_thumbstick_y: int = 0
    right_thumbstick_x: int = 0
    right_thumbstick_y: int = 0

    BUTTON_A = 0x0001
    BUTTON_B = 0x0002
    BUTTON_X = 0x0004
    BUTTON_Y = 0x0008
    BUTTON_L1 = 0x0010
    BUTTON_R1 = 0x0020
    BUTTON_START = 0x0040
    BUTTON_SELECT = 0x0080
    DPAD_UP = 0x0100
    DPAD_DOWN = 0x0200
    DPAD_LEFT = 0x0400
    DPAD_RIGHT = 0x0800

    def to_bytes(self) -> bytes:
        """转换为字节数据用于协议传输"""
        import struct
        return struct.pack(
            '!HHHHHHH',
            self.buttons,
            self.left_trigger,
            self.right_trigger,
            self._normalize(self.left_thumbstick_x),
            self._normalize(self.left_thumbstick_y),
            self._normalize(self.right_thumbstick_x),
            self._normalize(self.right_thumbstick_y)
        )

    @staticmethod
    def _normalize(value: float) -> int:
        """将浮点值(-1.0~1.0)转换为整数(-32768~32767)"""
        return int(max(-32768, min(32767, value * 32767)))


class XboxGamepadController:
    """
    Xbox 游戏手柄控制器

    功能说明：
    - 初始化pygame手柄系统
    - 读取手柄输入状态
    - 将输入转换为Xbox协议信号

    使用方式：
    - 创建实例后调用 initialize() 初始化
    - 使用 read_input() 读取当前输入
    - 使用 get_signals() 获取Xbox协议信号
    """

    DEADZONE = 0.1

    def __init__(self, controller_id: int = 0):
        self.logger = get_logger('xbox_gamepad')
        self.controller_id = controller_id
        self.controller: Optional[pygame.joystick.Joystick] = None
        self._initialized = False
        self._running = False
        self._input_task: Optional[asyncio.Task] = None
        self._input_callback: Optional[callable] = None
        self._current_input = GamepadInput()

    async def initialize(self) -> bool:
        """
        初始化手柄控制器

        返回值：
        - True: 初始化成功
        - False: 初始化失败
        """
        try:
            pygame.init()
            pygame.joystick.init()

            if pygame.joystick.get_count() == 0:
                self.logger.warning("未检测到手柄")
                return False

            if pygame.joystick.get_count() <= self.controller_id:
                self.logger.warning(f"手柄ID {self.controller_id} 不存在")
                return False

            self.controller = pygame.joystick.Joystick(self.controller_id)
            self.controller.init()

            self._initialized = True
            self._running = True
            self.logger.info(f"手柄已连接: {self.controller.get_name()}")

            self._input_task = asyncio.create_task(self._input_loop())

            return True

        except Exception as e:
            self.logger.error(f"手柄初始化失败: {e}")
            return False

    async def _input_loop(self):
        """输入读取循环"""
        while self._running and self._initialized:
            try:
                pygame.event.pump()
                input_data = self._read_current_input()
                self._current_input = input_data

                if self._input_callback and not input_data.is_empty():
                    signals = self._input_to_signals(input_data)
                    self._input_callback(signals)

                await asyncio.sleep(0.016)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"输入读取异常: {e}")

    def _read_current_input(self) -> GamepadInput:
        """读取当前手柄输入"""
        if not self.controller:
            return GamepadInput()

        input_data = GamepadInput()

        for name, btn in XboxButton.__members__.items():
            try:
                input_data.buttons[name.lower()] = bool(self.controller.get_button(btn))
            except:
                input_data.buttons[name.lower()] = False

        input_data.axes['left_x'] = self._apply_deadzone(self.controller.get_axis(XboxAxis.LEFT_X))
        input_data.axes['left_y'] = self._apply_deadzone(self.controller.get_axis(XboxAxis.LEFT_Y))
        input_data.axes['right_x'] = self._apply_deadzone(self.controller.get_axis(XboxAxis.RIGHT_X))
        input_data.axes['right_y'] = self._apply_deadzone(self.controller.get_axis(XboxAxis.RIGHT_Y))

        input_data.triggers['l2'] = (self.controller.get_axis(XboxAxis.L2) + 1) / 2
        input_data.triggers['r2'] = (self.controller.get_axis(XboxAxis.R2) + 1) / 2

        return input_data

    def _apply_deadzone(self, value: float) -> float:
        """应用死区"""
        if abs(value) < self.DEADZONE:
            return 0.0
        sign = 1 if value > 0 else -1
        return sign * (abs(value) - self.DEADZONE) / (1 - self.DEADZONE)

    def _input_to_signals(self, input_data: GamepadInput) -> GamepadSignal:
        """将输入转换为Xbox信号"""
        signals = GamepadSignal()

        if input_data.buttons.get('a'):
            signals.buttons |= GamepadSignal.BUTTON_A
        if input_data.buttons.get('b'):
            signals.buttons |= GamepadSignal.BUTTON_B
        if input_data.buttons.get('x'):
            signals.buttons |= GamepadSignal.BUTTON_X
        if input_data.buttons.get('y'):
            signals.buttons |= GamepadSignal.BUTTON_Y
        if input_data.buttons.get('l1'):
            signals.buttons |= GamepadSignal.BUTTON_L1
        if input_data.buttons.get('r1'):
            signals.buttons |= GamepadSignal.BUTTON_R1
        if input_data.buttons.get('start'):
            signals.buttons |= GamepadSignal.BUTTON_START
        if input_data.buttons.get('select'):
            signals.buttons |= GamepadSignal.BUTTON_SELECT
        if input_data.buttons.get('dpad_up'):
            signals.buttons |= GamepadSignal.DPAD_UP
        if input_data.buttons.get('dpad_down'):
            signals.buttons |= GamepadSignal.DPAD_DOWN
        if input_data.buttons.get('dpad_left'):
            signals.buttons |= GamepadSignal.DPAD_LEFT
        if input_data.buttons.get('dpad_right'):
            signals.buttons |= GamepadSignal.DPAD_RIGHT

        signals.left_trigger = int(input_data.triggers.get('l2', 0) * 255)
        signals.right_trigger = int(input_data.triggers.get('r2', 0) * 255)

        signals.left_thumbstick_x = input_data.axes.get('left_x', 0)
        signals.left_thumbstick_y = input_data.axes.get('left_y', 0)
        signals.right_thumbstick_x = input_data.axes.get('right_x', 0)
        signals.right_thumbstick_y = input_data.axes.get('right_y', 0)

        return signals

    def read_input(self) -> GamepadInput:
        """
        读取当前输入状态（同步）

        返回值：
        - GamepadInput: 当前输入状态
        """
        return self._current_input

    def get_signals(self) -> GamepadSignal:
        """
        获取Xbox协议信号

        返回值：
        - GamepadSignal: Xbox信号数据
        """
        return self._input_to_signals(self._current_input)

    def set_input_callback(self, callback: callable):
        """
        设置输入回调函数

        参数：
        - callback: 回调函数，接收 GamepadSignal 参数
        """
        self._input_callback = callback

    async def press_button(self, button: str, duration: float = 0.1):
        """
        模拟按下按钮（用于自动化）

        参数：
        - button: 按钮名称
        - duration: 按下持续时间（秒）
        """
        self.logger.debug(f"Press button: {button}")

        original_input = self._current_input

        temp_input = GamepadInput()
        temp_input.buttons[button.lower()] = True
        self._current_input = temp_input

        await asyncio.sleep(duration)

        self._current_input = original_input

    async def move_stick(self, stick: str, x: float, y: float, duration: float = 0.1):
        """
        模拟摇杆移动（用于自动化）

        参数：
        - stick: 摇杆名称 (left/right)
        - x: X轴值 (-1.0 到 1.0)
        - y: Y轴值 (-1.0 到 1.0)
        - duration: 持续时间（秒）
        """
        self.logger.debug(f"Move stick: {stick} ({x}, {y})")

        original_input = self._current_input

        temp_input = GamepadInput()
        if stick.lower() == 'left':
            temp_input.axes['left_x'] = x
            temp_input.axes['left_y'] = y
        else:
            temp_input.axes['right_x'] = x
            temp_input.axes['right_y'] = y

        self._current_input = temp_input
        await asyncio.sleep(duration)

        self._current_input = original_input

    async def shutdown(self):
        """关闭手柄控制器"""
        self._running = False

        if self._input_task:
            self._input_task.cancel()
            try:
                await self._input_task
            except asyncio.CancelledError:
                pass

        if self.controller:
            self.controller.quit()

        pygame.joystick.quit()
        self._initialized = False
        self.logger.info("手柄控制器已关闭")

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    @property
    def controller_name(self) -> str:
        """获取手柄名称"""
        if self.controller:
            return self.controller.get_name()
        return "Not connected"


xbox_gamepad_controller = XboxGamepadController()
