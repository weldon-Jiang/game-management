"""
Input Controller - Controls mouse, keyboard and gamepad

功能说明：
- 控制鼠标、键盘和游戏手柄输入
- 模拟用户操作实现自动化
- 提供异步操作接口

技术实现：
- 使用pyautogui库控制鼠标和键盘
- 使用inputs库控制游戏手柄
- 支持所有常用按键和鼠标操作

输入类型：
- 鼠标：点击、移动、滚动、拖拽
- 键盘：按键、文本输入、组合键
- 游戏手柄：按钮、摇杆
"""
import asyncio
from typing import Tuple, Optional
from enum import Enum

from ..core.config import config
from ..core.logger import get_logger


class MouseButton(Enum):
    """
    鼠标按钮枚举

    按钮类型：
    - LEFT: 左键
    - RIGHT: 右键
    - MIDDLE: 中键（滚轮）
    """
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class Key:
    """
    键盘按键常量类

    按键分类：
    - 特殊键：Enter、Escape、Tab、Backspace、Delete
    - 方向键：上、下、左、右
    - 修饰键：Shift、Ctrl、Alt
    - 字母键：A-Z
    """

    # 特殊按键
    ENTER = "enter"
    ESCAPE = "escape"
    TAB = "tab"
    BACKSPACE = "backspace"
    DELETE = "delete"

    # 方向键
    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"

    # 修饰键
    SHIFT = "shift"
    CONTROL = "ctrl"
    ALT = "alt"

    # 字母按键（A-Z）
    A = "a"
    B = "b"
    C = "c"
    D = "d"
    E = "e"
    F = "f"
    G = "g"
    H = "h"
    I = "i"
    J = "j"
    K = "k"
    L = "l"
    M = "m"
    N = "n"
    O = "o"
    P = "p"
    Q = "q"
    R = "r"
    S = "s"
    T = "t"
    U = "u"
    V = "v"
    W = "w"
    X = "x"
    Y = "y"
    Z = "z"


class InputController:
    """
    输入控制器

    功能说明：
    - 控制鼠标操作（点击、移动、滚动）
    - 控制键盘操作（按键、文本输入）
    - 提供异步操作接口
    - 支持组合键操作

    使用方式：
    - 创建实例后直接调用各种输入方法
    - 所有方法都是异步的，需要await
    """

    def __init__(self):
        """初始化输入控制器"""
        self._click_delay = config.get('input.click_delay', 0.1)  # 点击后延迟
        self._key_press_delay = config.get('input.key_press_delay', 0.05)  # 按键延迟
        self._move_duration = config.get('input.move_duration', 0.2)  # 移动持续时间
        self.logger = get_logger('input')  # 日志记录器

    async def click(
        self,
        x: Optional[int] = None,
        y: Optional[int] = None,
        button: MouseButton = MouseButton.LEFT,
        clicks: int = 1
    ):
        """
        鼠标点击

        参数说明：
        - x: 点击X坐标（可选）
        - y: 点击Y坐标（可选）
        - button: 鼠标按钮，默认左键
        - clicks: 点击次数，默认1次

        注意：
        - 如果指定坐标，会先移动鼠标
        - 点击后会有配置的延迟
        """
        try:
            import pyautogui

            if x is not None and y is not None:
                await self.move_to(x, y)

            pyautogui.click(button.value, clicks=clicks)
            self.logger.debug(f"Clicked {button.value} at ({x}, {y})")
            await asyncio.sleep(self._click_delay)

        except ImportError:
            self.logger.warning("pyautogui not available")
        except Exception as e:
            self.logger.error(f"Click error: {e}")

    async def double_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        双击

        参数说明：
        - x: 点击X坐标（可选）
        - y: 点击Y坐标（可选）
        """
        await self.click(x, y, clicks=2)

    async def right_click(self, x: Optional[int] = None, y: Optional[int] = None):
        """
        右键点击

        参数说明：
        - x: 点击X坐标（可选）
        - y: 点击Y坐标（可选）
        """
        await self.click(x, y, button=MouseButton.RIGHT)

    async def move_to(self, x: int, y: int, duration: Optional[float] = None):
        """
        移动鼠标到指定位置

        参数说明：
        - x: 目标X坐标
        - y: 目标Y坐标
        - duration: 移动持续时间（秒）
        """
        try:
            import pyautogui

            if duration is None:
                duration = self._move_duration

            pyautogui.moveTo(x, y, duration=duration)
            self.logger.debug(f"Moved mouse to ({x}, {y})")

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Move error: {e}")

    async def move_relative(self, dx: int, dy: int, duration: Optional[float] = None):
        """
        相对移动鼠标

        参数说明：
        - dx: X轴偏移量
        - dy: Y轴偏移量
        - duration: 移动持续时间
        """
        try:
            import pyautogui

            if duration is None:
                duration = self._move_duration

            pyautogui.move(dx, dy, duration=duration)

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Move relative error: {e}")

    async def drag_to(
        self,
        x: int,
        y: int,
        duration: Optional[float] = None,
        button: MouseButton = MouseButton.LEFT
    ):
        """
        拖拽鼠标到目标位置

        参数说明：
        - x: 目标X坐标
        - y: 目标Y坐标
        - duration: 拖拽持续时间
        - button: 鼠标按钮
        """
        try:
            import pyautogui

            if duration is None:
                duration = 0.5

            pyautogui.dragTo(x, y, duration=duration, button=button.value)

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Drag error: {e}")

    async def scroll(self, clicks: int):
        """
        滚动鼠标滚轮

        参数说明：
        - clicks: 滚动格数（正数向上，负数向下）
        """
        try:
            import pyautogui
            pyautogui.scroll(clicks)
            self.logger.debug(f"Scrolled {clicks} clicks")
        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Scroll error: {e}")

    async def press_key(self, key: str):
        """
        按下并释放按键

        参数说明：
        - key: 按键名称
        """
        try:
            import pyautogui

            pyautogui.press(key)
            await asyncio.sleep(self._key_press_delay)
            self.logger.debug(f"Pressed key: {key}")

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Key press error: {e}")

    async def type_text(self, text: str, interval: Optional[float] = None):
        """
        输入文本

        参数说明：
        - text: 要输入的文本
        - interval: 每个字符之间的间隔
        """
        try:
            import pyautogui

            if interval is None:
                interval = self._key_press_delay

            pyautogui.write(text, interval=interval)
            self.logger.debug(f"Typed text: {text[:20]}...")

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Type text error: {e}")

    async def key_down(self, key: str):
        """
        按下按键（保持按下状态）

        参数说明：
        - key: 按键名称
        """
        try:
            import pyautogui
            pyautogui.keyDown(key)
        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Key down error: {e}")

    async def key_up(self, key: str):
        """
        释放按键

        参数说明：
        - key: 按键名称
        """
        try:
            import pyautogui
            pyautogui.keyUp(key)
        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Key up error: {e}")

    async def press_keys(self, *keys):
        """
        同时按下多个键（组合键）

        参数说明：
        - keys: 按键名称列表

        示例：
        - await press_keys('ctrl', 'c')  # Ctrl+C 复制
        """
        try:
            import pyautogui
            pyautogui.hotkey(*keys)
            await asyncio.sleep(self._key_press_delay)
        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Hotkey error: {e}")

    async def get_position(self) -> Tuple[int, int]:
        """
        获取当前鼠标位置

        返回值：(x, y) 坐标元组
        """
        try:
            import pyautogui
            return pyautogui.position()
        except ImportError:
            return (0, 0)
        except Exception as e:
            self.logger.error(f"Get position error: {e}")
            return (0, 0)


class GamepadController:
    """
    游戏手柄控制器

    功能说明：
    - 控制Xbox游戏手柄
    - 支持按钮和摇杆操作
    - 使用inputs库与游戏手柄通信
    """

    def __init__(self):
        """初始化游戏手柄控制器"""
        self._connected = False  # 连接状态
        self.logger = get_logger('gamepad')  # 日志记录器

    def connect(self) -> bool:
        """
        连接游戏手柄

        返回值：
        - True: 连接成功
        - False: 连接失败
        """
        try:
            from inputs import devices
            gamepads = devices.gamepads
            if gamepads:
                self._connected = True
                self.logger.info("Gamepad connected")
                return True
        except ImportError:
            self.logger.warning("inputs library not available")
        except Exception as e:
            self.logger.error(f"Gamepad connect error: {e}")
        return False

    def disconnect(self):
        """
        断开游戏手柄连接
        """
        self._connected = False
        self.logger.info("Gamepad disconnected")

    def press_button(self, button_name: str):
        """
        按下手柄按钮

        参数说明：
        - button_name: 按钮名称（a, b, x, y, start, select等）
        """
        try:
            from inputs import get_gamepad

            button_map = {
                'a': 'BTN_SOUTH',
                'b': 'BTN_EAST',
                'x': 'BTN_NORTH',
                'y': 'BTN_WEST',
                'start': 'BTN_START',
                'select': 'BTN_SELECT',
                'lstick': 'BTN_THUMBL',
                'rstick': 'BTN_THUMBR',
            }

            abs_code = button_map.get(button_name.lower())
            if abs_code:
                import os
                os.system(f"evtest /dev/input/event0 --code {abs_code} 2>/dev/null &")
        except Exception as e:
            self.logger.error(f"Gamepad button error: {e}")

    def moveStick(self, stick: str, x: int, y: int):
        """
        移动模拟摇杆

        参数说明：
        - stick: 摇杆名称（left/right）
        - x: X轴值（-32768 到 32767）
        - y: Y轴值（-32768 到 32767）
        """
        try:
            from inputs import get_gamepad

            if stick == 'left':
                self._send_abs('ABS_X', x)
                self._send_abs('ABS_Y', y)
            elif stick == 'right':
                self._send_abs('ABS_Z', x)
                self._send_abs('ABS_RZ', y)
        except Exception as e:
            self.logger.error(f"Stick move error: {e}")

    def _send_abs(self, code: str, value: int):
        """
        发送绝对坐标事件

        参数说明：
        - code: 事件代码
        - value: 坐标值
        """
        try:
            import subprocess
            subprocess.run([
                'python', '-c',
                f'import os; os.system("evtest /dev/input/event0 --type 3 --code {code} --value {value} 2>/dev/null")'
            ], capture_output=True)
        except:
            pass
