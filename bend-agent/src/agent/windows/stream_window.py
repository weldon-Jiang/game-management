"""
Stream Window Manager - Manages Xbox streaming window state

功能说明：
- 管理Xbox流媒体窗口的状态
- 提供窗口的查找、激活、最小化、关闭等操作
- 支持窗口位置和尺寸的获取与设置
- 维护窗口状态变化事件回调

窗口状态：
- UNKNOWN: 未知状态
- CLOSED: 窗口已关闭
- OPENING: 窗口正在打开
- CONNECTING: 正在连接
- CONNECTED: 已连接
- MINIMIZED: 已最小化
- DISCONNECTED: 已断开
- ERROR: 错误状态

技术实现：
- 使用win32gui操作Windows窗口
- 支持模拟模式（win32gui不可用时）
"""
import asyncio
from enum import Enum
from typing import Optional, Callable

from ..core.logger import get_logger


class WindowState(Enum):
    """
    窗口状态枚举

    状态说明：
    - UNKNOWN: 窗口状态未知
    - CLOSED: 窗口已关闭
    - OPENING: 窗口正在打开
    - CONNECTING: 正在建立连接
    - CONNECTED: 已成功连接
    - MINIMIZED: 窗口已最小化
    - DISCONNECTED: 连接已断开
    - ERROR: 发生错误
    """
    UNKNOWN = "unknown"         # 未知状态
    CLOSED = "closed"           # 已关闭
    OPENING = "opening"         # 正在打开
    CONNECTING = "connecting"   # 正在连接
    CONNECTED = "connected"     # 已连接
    MINIMIZED = "minimized"     # 已最小化
    DISCONNECTED = "disconnected"  # 已断开
    ERROR = "error"           # 错误状态


class StreamWindow:
    """
    Xbox流媒体窗口管理器

    功能说明：
    - 管理Xbox App窗口的创建、激活、销毁
    - 提供窗口位置和尺寸控制
    - 维护窗口状态和事件回调
    - 支持模拟模式（开发/测试用）

    使用方式：
    - 创建实例后使用 find_window() 查找窗口
    - 使用 activate() 激活窗口
    - 使用 get_position/set_position 管理窗口位置
    - 使用 on_state_changed() 注册状态变化回调
    """

    def __init__(self, window_title: str = "Xbox App"):
        """
        初始化窗口管理器

        参数说明：
        - window_title: Xbox窗口标题，默认"Xbox App"
        """
        self.window_title = window_title  # 窗口标题
        self._state = WindowState.UNKNOWN  # 当前窗口状态
        self._hwnd: Optional[int] = None  # 窗口句柄（Windows内部标识）
        self._callbacks: dict = {}  # 回调函数字典
        self.logger = get_logger('window')  # 日志记录器

    @property
    def state(self) -> WindowState:
        """
        获取当前窗口状态

        返回值：WindowState枚举值
        """
        return self._state

    def set_state(self, new_state: WindowState):
        """
        设置窗口状态

        参数说明：
        - new_state: 新的窗口状态

        功能说明：
        - 如果状态发生变化，触发回调
        - 记录状态变化日志
        """
        if self._state != new_state:
            old_state = self._state
            self._state = new_state
            self.logger.info(f"Window state changed: {old_state.value} -> {new_state.value}")
            self._trigger_callback('state_changed', new_state, old_state)

    def on_state_changed(self, callback: Callable):
        """
        注册窗口状态变化回调

        参数说明：
        - callback: 回调函数，签名为 callback(new_state, old_state)
        """
        self._callbacks['state_changed'] = callback

    def _trigger_callback(self, event: str, *args):
        """
        触发注册的回调函数

        参数说明：
        - event: 事件名称
        - args: 传递给回调函数的参数
        """
        if event in self._callbacks:
            try:
                self._callbacks[event](*args)
            except Exception as e:
                self.logger.error(f"Callback error: {e}")

    async def find_window(self) -> bool:
        """
        查找Xbox流媒体窗口

        返回值：
        - True: 找到窗口
        - False: 未找到窗口

        实现说明：
        - 使用win32gui.FindWindow查找窗口
        - 找不到时进入模拟模式
        """
        try:
            import win32gui
            import win32con

            self._hwnd = win32gui.FindWindow(None, self.window_title)
            if self._hwnd:
                self.logger.info(f"Found window: {self.window_title} (hwnd={self._hwnd})")
                return True
            else:
                self.logger.debug(f"Window not found: {self.window_title}")
                return False

        except ImportError:
            # win32gui不可用，进入模拟模式
            self.logger.warning("win32gui not available, running in simulation mode")
            self._hwnd = 12345  # 模拟窗口句柄
            return True
        except Exception as e:
            self.logger.error(f"Error finding window: {e}")
            return False

    async def activate(self) -> bool:
        """
        激活窗口（将窗口置于前台）

        返回值：
        - True: 激活成功
        - False: 激活失败

        实现说明：
        - 如果窗口最小化，先恢复
        - 然后设置为前台窗口
        """
        try:
            import win32gui
            import win32con

            if not self._hwnd:
                await self.find_window()

            if self._hwnd:
                if win32gui.IsIconic(self._hwnd):
                    win32gui.ShowWindow(self._hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(self._hwnd)
                self.logger.info("Window activated")
                return True
            return False

        except ImportError:
            self.logger.info("Running in simulation mode")
            return True
        except Exception as e:
            self.logger.error(f"Error activating window: {e}")
            return False

    async def minimize(self):
        """
        最小化窗口

        功能说明：
        - 将窗口最小化到任务栏
        - 更新状态为MINIMIZED
        """
        try:
            import win32gui
            import win32con

            if self._hwnd:
                win32gui.ShowWindow(self._hwnd, win32con.SW_MINIMIZE)
                self.set_state(WindowState.MINIMIZED)

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Error minimizing window: {e}")

    async def close(self):
        """
        关闭窗口

        功能说明：
        - 发送关闭消息到窗口
        - 更新状态为CLOSED
        """
        try:
            import win32gui
            import win32con

            if self._hwnd:
                win32gui.PostMessage(self._hwnd, win32con.WM_CLOSE, 0, 0)
                self.set_state(WindowState.CLOSED)

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Error closing window: {e}")

    async def get_position(self) -> Optional[tuple]:
        """
        获取窗口位置和尺寸

        返回值：
        - (left, top, right, bottom) 四个坐标值
        - None: 获取失败

        注意：
        - 坐标单位是像素
        - right和bottom不是宽高，而是对角点坐标
        """
        try:
            import win32gui

            if self._hwnd:
                return win32gui.GetWindowRect(self._hwnd)
            return None

        except ImportError:
            return (0, 0, 1280, 720)
        except Exception as e:
            self.logger.error(f"Error getting position: {e}")
            return None

    async def set_position(self, left: int, top: int, width: int, height: int):
        """
        设置窗口位置和尺寸

        参数说明：
        - left: 左边距（像素）
        - top: 顶边距（像素）
        - width: 窗口宽度（像素）
        - height: 窗口高度（像素）
        """
        try:
            import win32gui
            import win32con

            if self._hwnd:
                win32gui.MoveWindow(self._hwnd, left, top, width, height, True)

        except ImportError:
            pass
        except Exception as e:
            self.logger.error(f"Error setting position: {e}")

    async def get_client_rect(self) -> Optional[tuple]:
        """
        获取窗口客户区矩形（不含标题栏和边框）

        返回值：
        - (left, top, width, height) 客户区位置和尺寸
        - None: 获取失败
        """
        try:
            import win32gui
            import win32con

            if self._hwnd:
                left, top, right, bottom = win32gui.GetClientRect(self._hwnd)
                return (left, top, right - left, bottom - top)
            return None

        except ImportError:
            return (0, 0, 1280, 720)
        except Exception as e:
            self.logger.error(f"Error getting client rect: {e}")
            return None

    async def is_visible(self) -> bool:
        """
        检查窗口是否可见

        返回值：
        - True: 窗口可见
        - False: 窗口不可见
        """
        try:
            import win32gui

            if self._hwnd:
                return win32gui.IsWindowVisible(self._hwnd)
            return False

        except ImportError:
            return True
        except Exception as e:
            self.logger.error(f"Error checking visibility: {e}")
            return False
