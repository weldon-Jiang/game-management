"""
SDL2自绘串流窗口
================

功能说明：
- 使用pygame创建自绘串流窗口
- 支持视频帧渲染
- 与pygame手柄控制器统一
- 提供高效的帧捕获能力

技术实现参考（streaming项目）：
- SDL2窗口创建
- pygame渲染
- surfarray帧捕获

作者：技术团队
版本：1.0
"""

import asyncio
import time
from typing import Optional, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
import numpy as np

from ..core.logger import get_logger

try:
    import pygame
    PYGAME_AVAILABLE = True
except ImportError:
    PYGAME_AVAILABLE = False
    pygame = None


class SDLWindowState(Enum):
    """SDL窗口状态枚举"""
    UNINITIALIZED = "uninitialized"
    INITIALIZING = "initializing"
    READY = "ready"
    RUNNING = "running"
    PAUSED = "paused"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class SDLWindowConfig:
    """SDL窗口配置"""
    width: int = 1280
    height: int = 720
    title: str = "Bend Agent - Xbox Streaming"
    flags: int = 0
    vsync: bool = True
    double_buffer: bool = True
    hardware_surface: bool = True


class SDLStreamWindow:
    """
    SDL2自绘串流窗口

    功能说明：
    - 创建和管理SDL窗口
    - 渲染视频帧到窗口
    - 提供高效的帧捕获
    - 与pygame手柄统一

    使用方式：
    - window = SDLStreamWindow()
    - await window.initialize(config)
    - window.update_frame(frame)
    - captured = window.capture_frame()

    架构说明：
    ┌─────────────────────────────────────────────────────────┐
    │                  SDLStreamWindow                        │
    │                                                         │
    │  ┌─────────────────────────────────────────────────┐   │
    │  │              pygame.display                     │   │
    │  │                                                  │   │
    │  │  ┌─────────────────────────────────────────┐   │   │
    │  │  │            视频帧 Surface                 │   │   │
    │  │  └─────────────────────────────────────────┘   │   │
    │  │                    │                           │   │
    │  │                    ▼                           │   │
    │  │  ┌─────────────────────────────────────────┐   │   │
    │  │  │         pygame.surfarray                │   │   │
    │  │  │         → numpy数组                     │   │   │
    │  │  └─────────────────────────────────────────┘   │   │
    │  └─────────────────────────────────────────────────┘   │
    └─────────────────────────────────────────────────────────┘
    """

    def __init__(self, config: Optional[SDLWindowConfig] = None):
        self.logger = get_logger('sdl_window')
        self._config = config or SDLWindowConfig()
        self._state = SDLWindowState.UNINITIALIZED
        self._screen = None
        self._frame_surface = None
        self._running = False
        self._event_callbacks: dict = {}
        self._frame_callback: Optional[Callable] = None
        self._last_frame_time = 0
        self._frame_count = 0
        self._fps = 0.0

        if not PYGAME_AVAILABLE:
            self.logger.warning("pygame不可用，SDL窗口功能将不可用")

    async def initialize(self, config: Optional[SDLWindowConfig] = None) -> bool:
        """
        初始化SDL窗口

        参数：
        - config: 窗口配置（可选）

        返回值：
        - True: 初始化成功
        - False: 初始化失败
        """
        if not PYGAME_AVAILABLE:
            self.logger.error("pygame不可用，无法初始化SDL窗口")
            self._state = SDLWindowState.ERROR
            return False

        try:
            self._state = SDLWindowState.INITIALIZING

            if config:
                self._config = config

            pygame.init()

            flags = pygame.HWSURFACE | pygame.DOUBLEBUF
            if self._config.vsync:
                flags |= pygame.FULLSCREEN

            self._screen = pygame.display.set_mode(
                (self._config.width, self._config.height),
                flags
            )
            pygame.display.set_caption(self._config.title)

            self._frame_surface = pygame.Surface(
                (self._config.width, self._config.height),
                depth=24
            )

            self._running = True
            self._state = SDLWindowState.READY
            self.logger.info(f"SDL窗口初始化成功: {self._config.width}x{self._config.height}")

            return True

        except Exception as e:
            self.logger.error(f"SDL窗口初始化失败: {e}")
            self._state = SDLWindowState.ERROR
            return False

    def update_frame(self, frame: np.ndarray):
        """
        更新窗口画面

        参数：
        - frame: 视频帧（numpy数组，HWC格式）

        实现说明：
        - numpy数组转换为pygame Surface
        - 渲染到屏幕
        - 更新FPS统计
        """
        if not self._running or self._screen is None:
            return

        try:
            start_time = time.time()

            if frame.shape[2] == 3:
                frame_rgb = frame
            else:
                import cv2
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            frame_rgb = np.transpose(frame_rgb, (1, 0, 2))

            self._frame_surface = pygame.surfarray.make_surface(frame_rgb)

            self._screen.fill((0, 0, 0))
            scaled = pygame.transform.scale(
                self._frame_surface,
                (self._config.width, self._config.height)
            )
            self._screen.blit(scaled, (0, 0))

            pygame.display.flip()

            self._update_fps(time.time() - start_time)

            if self._frame_callback:
                self._frame_callback(frame)

        except Exception as e:
            self.logger.error(f"更新帧失败: {e}")

    def _update_fps(self, frame_time: float):
        """更新FPS统计"""
        self._frame_count += 1
        self._last_frame_time = frame_time

        if self._frame_count % 30 == 0:
            self._fps = 1.0 / frame_time if frame_time > 0 else 0

    def capture_frame(self) -> Optional[np.ndarray]:
        """
        捕获当前窗口帧

        返回值：
        - 捕获的帧（numpy数组，HWC格式，BGR格式）或None
        """
        if not self._running or self._screen is None:
            return None

        try:
            frame = pygame.surfarray.array3d(self._screen)

            frame = np.transpose(frame, (1, 0, 2))

            import cv2
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            return frame_bgr

        except Exception as e:
            self.logger.error(f"捕获帧失败: {e}")
            return None

    def get_bgr_frame(self) -> Optional[np.ndarray]:
        """获取BGR格式帧（用于OpenCV）"""
        return self.capture_frame()

    def get_rgb_frame(self) -> Optional[np.ndarray]:
        """获取RGB格式帧"""
        if not self._running or self._screen is None:
            return None

        try:
            frame = pygame.surfarray.array3d(self._screen)
            return np.transpose(frame, (1, 0, 2))
        except Exception as e:
            self.logger.error(f"获取RGB帧失败: {e}")
            return None

    def set_frame_callback(self, callback: Callable[[np.ndarray], None]):
        """
        设置帧回调

        参数：
        - callback: 每帧回调函数
        """
        self._frame_callback = callback

    def process_events(self) -> bool:
        """
        处理pygame事件

        返回值：
        - True: 继续运行
        - False: 收到退出事件
        """
        if not PYGAME_AVAILABLE:
            return False

        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return False

                if event.type in self._event_callbacks:
                    self._event_callbacks[event.type](event)

            return True

        except Exception as e:
            self.logger.error(f"处理事件失败: {e}")
            return True

    def register_event_callback(self, event_type: int, callback: Callable):
        """
        注册事件回调

        参数：
        - event_type: pygame事件类型
        - callback: 回调函数
        """
        self._event_callbacks[event_type] = callback

    def clear(self):
        """清空窗口"""
        if self._screen:
            self._screen.fill((0, 0, 0))
            pygame.display.flip()

    def pause(self):
        """暂停窗口"""
        self._state = SDLWindowState.PAUSED

    def resume(self):
        """恢复窗口"""
        if self._state == SDLWindowState.PAUSED:
            self._state = SDLWindowState.RUNNING

    def close(self):
        """关闭窗口"""
        self._running = False
        self._state = SDLWindowState.CLOSED

        if PYGAME_AVAILABLE:
            pygame.quit()

        self.logger.info("SDL窗口已关闭")

    async def wait_for_close(self):
        """等待窗口关闭"""
        while self._running:
            if not self.process_events():
                break
            await asyncio.sleep(0.01)

        self.close()

    def get_stats(self) -> dict:
        """
        获取窗口统计信息

        返回值：
        - 统计信息字典
        """
        return {
            'state': self._state.value,
            'resolution': f"{self._config.width}x{self._config.height}",
            'fps': self._fps,
            'frame_time_ms': self._last_frame_time * 1000,
            'frames_rendered': self._frame_count,
            'running': self._running
        }

    @property
    def state(self) -> SDLWindowState:
        """获取窗口状态"""
        return self._state

    @property
    def is_running(self) -> bool:
        """检查窗口是否运行中"""
        return self._running

    @property
    def width(self) -> int:
        """获取窗口宽度"""
        return self._config.width

    @property
    def height(self) -> int:
        """获取窗口高度"""
        return self._config.height

    @property
    def surface(self):
        """获取pygame Surface"""
        return self._screen


class SDLFrameCapture:
    """
    SDL窗口帧捕获器

    功能说明：
    - 从SDL窗口高效捕获帧
    - 支持多种格式输出
    - 提供统计信息

    使用方式：
    - capture = SDLFrameCapture(window)
    - frame = await capture.capture_frame()
    """

    def __init__(self, window: SDLStreamWindow):
        self.logger = get_logger('sdl_capture')
        self._window = window
        self._capture_count = 0
        self._last_capture_time = 0

    async def capture_frame(self) -> Optional[np.ndarray]:
        """
        捕获帧

        返回值：
        - 捕获的帧或None
        """
        start_time = time.time()
        frame = self._window.capture_frame()

        if frame is not None:
            self._capture_count += 1
            self._last_capture_time = (time.time() - start_time) * 1000

        return frame

    def get_stats(self) -> dict:
        """
        获取捕获统计

        返回值：
        - 统计信息字典
        """
        return {
            'frames_captured': self._capture_count,
            'last_capture_time_ms': self._last_capture_time,
            'window_stats': self._window.get_stats()
        }

    @property
    def capture_count(self) -> int:
        """获取捕获帧数"""
        return self._capture_count


sdl_stream_window = SDLStreamWindow()
