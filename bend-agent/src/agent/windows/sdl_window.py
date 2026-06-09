"""
SDL2自绘串流窗口
================

功能说明：
- 使用pygame创建自绘串流窗口（仅用于显示，不参与自动化识别）
- 窗口固定 1280x720、可拖拽、不可缩放、可隐藏
- 画面捕获/模板匹配使用 RTP/GPU 解码原始帧（对齐 streaming 项目 game_mat 逻辑）

技术实现参考（streaming项目）：
- xsrp.StreamWindow.setFixedSize() 固定窗口尺寸
- game_mat 为原始捕获帧，capture_mat 仅用于窗口显示缩放

作者：技术团队
版本：1.1
"""

import asyncio
import sys
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
    HIDDEN = "hidden"
    CLOSED = "closed"
    ERROR = "error"


@dataclass
class SDLWindowConfig:
    """SDL窗口配置"""
    width: int = 1280
    height: int = 720
    title: str = "Bend Agent - Xbox Streaming"
    vsync: bool = True
    double_buffer: bool = True
    hardware_surface: bool = True
    resizable: bool = False
    hide_on_close: bool = False
    fit_aspect: bool = True


class SDLStreamWindow:
    """
    SDL2自绘串流窗口（显示专用）

    与 streaming StreamWindow 对齐：
    - 固定窗口尺寸（setFixedSize），可拖拽标题栏移动
    - 原始视频帧保存在 _last_source_frame，模板匹配不依赖窗口像素
    - 窗口隐藏不影响 RTP / GPU 解码链路
    """

    def __init__(self, config: Optional[SDLWindowConfig] = None):
        self.logger = get_logger('sdl_window')
        self._config = config or SDLWindowConfig()
        self._state = SDLWindowState.UNINITIALIZED
        self._screen = None
        self._frame_surface = None
        self._running = False
        self._visible = True
        self._hwnd: Optional[int] = None
        self._event_callbacks: dict = {}
        self._frame_callback: Optional[Callable] = None
        self._last_frame_time = 0
        self._frame_count = 0
        self._fps = 0.0
        # game_mat：解码原始帧；capture_mat：仅窗口显示缩放副本
        self._game_mat: Optional[np.ndarray] = None
        self._capture_mat: Optional[np.ndarray] = None
        self._source_size: Tuple[int, int] = (0, 0)
        self._last_render_monotonic = 0.0
        self._display_fps_max = 30.0
        self._close_callback: Optional[Callable[[], None]] = None
        self._close_requested = False

        if not PYGAME_AVAILABLE:
            self.logger.warning("pygame不可用，SDL窗口功能将不可用")

    async def initialize(self, config: Optional[SDLWindowConfig] = None) -> bool:
        """初始化固定尺寸窗口化 SDL 窗口。"""
        if not PYGAME_AVAILABLE:
            self.logger.error("pygame不可用，无法初始化SDL窗口")
            self._state = SDLWindowState.ERROR
            return False

        try:
            self._state = SDLWindowState.INITIALIZING

            if config:
                self._config = config

            if self._config.vsync:
                import os
                os.environ.setdefault('SDL_VIDEO_VSYNC', '1')

            pygame.init()

            flags = 0
            if self._config.hardware_surface:
                flags |= pygame.HWSURFACE
            if self._config.double_buffer:
                flags |= pygame.DOUBLEBUF
            if self._config.resizable:
                flags |= pygame.RESIZABLE

            self._screen = pygame.display.set_mode(
                (self._config.width, self._config.height),
                flags,
                vsync=1 if self._config.vsync else 0,
            )
            pygame.display.set_caption(self._config.title)

            self._frame_surface = pygame.Surface(
                (self._config.width, self._config.height),
                depth=24
            )

            self._apply_window_constraints()
            self._center_on_screen()

            self._running = True
            self._state = SDLWindowState.READY
            self.logger.info(
                "SDL窗口初始化成功: %sx%s title=%s hwnd=%s rect=%s "
                "(windowed, fixed-size, draggable)",
                self._config.width,
                self._config.height,
                self._config.title,
                self._get_hwnd(),
                self._get_window_rect(),
            )

            return True

        except TypeError:
            # pygame < 2.0 无 vsync 参数
            try:
                flags = pygame.HWSURFACE | pygame.DOUBLEBUF
                self._screen = pygame.display.set_mode(
                    (self._config.width, self._config.height),
                    flags
                )
                pygame.display.set_caption(self._config.title)
                self._frame_surface = pygame.Surface(
                    (self._config.width, self._config.height),
                    depth=24
                )
                self._apply_window_constraints()
                self._center_on_screen()
                self._running = True
                self._state = SDLWindowState.READY
                self.logger.info(
                    "SDL窗口初始化成功: %sx%s title=%s hwnd=%s rect=%s",
                    self._config.width,
                    self._config.height,
                    self._config.title,
                    self._get_hwnd(),
                    self._get_window_rect(),
                )
                return True
            except Exception as e:
                self.logger.error(f"SDL窗口初始化失败: {e}")
                self._state = SDLWindowState.ERROR
                return False
        except Exception as e:
            self.logger.error(f"SDL窗口初始化失败: {e}")
            self._state = SDLWindowState.ERROR
            return False

    def _get_hwnd(self) -> Optional[int]:
        if self._hwnd:
            return self._hwnd
        if not PYGAME_AVAILABLE:
            return None
        try:
            wm_info = pygame.display.get_wm_info()
            self._hwnd = wm_info.get('window') or wm_info.get('hwnd')
        except Exception:
            self._hwnd = None
        return self._hwnd

    def _get_window_rect(self) -> Optional[Tuple[int, int, int, int]]:
        if sys.platform != 'win32':
            return None
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = self._get_hwnd()
            if not hwnd:
                return None
            rect = wintypes.RECT()
            if ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                return rect.left, rect.top, rect.right, rect.bottom
        except Exception:
            return None
        return None

    def _bring_to_front(self):
        """尽力将可见 SDL 任务窗口置前。"""
        if sys.platform != 'win32':
            return
        try:
            import ctypes

            hwnd = self._get_hwnd()
            if not hwnd:
                return

            user32 = ctypes.windll.user32
            SW_RESTORE = 9
            HWND_TOPMOST = -1
            HWND_NOTOPMOST = -2
            SWP_NOMOVE = 0x0002
            SWP_NOSIZE = 0x0001
            SWP_SHOWWINDOW = 0x0040

            user32.ShowWindow(hwnd, SW_RESTORE)
            user32.SetWindowPos(
                hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
            user32.SetForegroundWindow(hwnd)
            user32.SetWindowPos(
                hwnd, HWND_NOTOPMOST, 0, 0, 0, 0,
                SWP_NOMOVE | SWP_NOSIZE | SWP_SHOWWINDOW,
            )
        except Exception as e:
            self.logger.warning(f"前置窗口失败: {e}")

    def set_close_callback(self, callback: Optional[Callable[[], None]]) -> None:
        """用户点击标题栏关闭按钮时调用。"""
        self._close_callback = callback

    def _apply_window_constraints(self):
        """Windows：固定客户区、标准标题栏（关闭/最小化）、不可缩放。"""
        if sys.platform != 'win32':
            return
        try:
            import ctypes
            from ctypes import wintypes

            hwnd = self._get_hwnd()
            if not hwnd:
                return

            GWL_STYLE = -16
            WS_OVERLAPPED = 0x00000000
            WS_CAPTION = 0x00C00000
            WS_SYSMENU = 0x00080000
            WS_MINIMIZEBOX = 0x00020000
            WS_THICKFRAME = 0x00040000
            WS_MAXIMIZEBOX = 0x00010000
            WS_HSCROLL = 0x00100000
            WS_VSCROLL = 0x00200000

            user32 = ctypes.windll.user32
            style = (
                WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_MINIMIZEBOX
            )
            user32.SetWindowLongW(hwnd, GWL_STYLE, style)

            rect = wintypes.RECT(0, 0, self._config.width, self._config.height)
            user32.AdjustWindowRectEx(ctypes.byref(rect), style, False, 0)
            outer_w = rect.right - rect.left
            outer_h = rect.bottom - rect.top

            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            x = max(0, (screen_w - outer_w) // 2)
            y = max(0, (screen_h - outer_h) // 2)

            SWP_NOZORDER = 0x0004
            SWP_FRAMECHANGED = 0x0020
            user32.SetWindowPos(
                hwnd, 0, x, y, outer_w, outer_h,
                SWP_NOZORDER | SWP_FRAMECHANGED,
            )
            user32.ShowScrollBar(hwnd, 0, False)  # SB_HORZ
            user32.ShowScrollBar(hwnd, 1, False)  # SB_VERT
            self.logger.debug(
                "窗口样式已应用: hwnd=%s client=%sx%s outer=%sx%s",
                hwnd,
                self._config.width,
                self._config.height,
                outer_w,
                outer_h,
            )
        except Exception as e:
            self.logger.warning(f"应用窗口约束失败: {e}")

    def _center_on_screen(self):
        """将窗口居中显示。"""
        if sys.platform != 'win32':
            return
        try:
            import ctypes

            hwnd = self._get_hwnd()
            if not hwnd:
                return

            user32 = ctypes.windll.user32
            screen_w = user32.GetSystemMetrics(0)
            screen_h = user32.GetSystemMetrics(1)
            x = max(0, (screen_w - self._config.width) // 2)
            y = max(0, (screen_h - self._config.height) // 2)
            user32.SetWindowPos(hwnd, 0, x, y, 0, 0, 0x0001 | 0x0004)  # NOSIZE | NOZORDER
        except Exception as e:
            self.logger.debug(f"窗口居中失败: {e}")

    def set_display_fps_max(self, fps: float) -> None:
        """显示刷新上限（对齐 streaming DECODE_VIDEO_FPS，默认 30）。"""
        self._display_fps_max = max(1.0, float(fps))

    def present_frame(self, frame: np.ndarray) -> None:
        """
        写入最新解码帧为 game_mat（识别/捕获源）。

        窗口隐藏时仍更新 game_mat，保证模板匹配不依赖 SDL 像素。
        """
        if frame is None or getattr(frame, "size", 0) == 0:
            return
        try:
            if len(frame.shape) < 3:
                return
            if frame.shape[2] == 3:
                frame_bgr = np.ascontiguousarray(frame)
            else:
                import cv2
                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
            self._game_mat = frame_bgr.copy()
            self._source_size = (frame_bgr.shape[1], frame_bgr.shape[0])
        except Exception as e:
            self.logger.error(f"present_frame 失败: {e}")

    def _build_capture_mat(self) -> Optional[np.ndarray]:
        """由 game_mat 生成 capture_mat（仅显示缩放，对齐 streaming resize）。"""
        if self._game_mat is None:
            return None
        src_h, src_w = self._game_mat.shape[:2]
        dst_w, dst_h = self._config.width, self._config.height
        if src_w <= 0 or src_h <= 0:
            return None
        if src_w == dst_w and src_h == dst_h:
            return self._game_mat.copy()
        import cv2
        return cv2.resize(
            self._game_mat,
            (dst_w, dst_h),
            interpolation=cv2.INTER_LINEAR,
        )

    def render_display(self, force: bool = False) -> bool:
        """
        将 capture_mat 刷到 SDL 窗口；按 display_fps_max 节流。

        返回 True 表示本帧已绘制。
        """
        if not self._running or self._screen is None or not self._visible:
            return False
        if self._game_mat is None:
            return False

        min_interval = 1.0 / self._display_fps_max
        now = time.monotonic()
        if not force and (now - self._last_render_monotonic) < min_interval:
            return False

        try:
            start_time = time.time()
            capture = self._build_capture_mat()
            if capture is None:
                return False
            self._capture_mat = capture

            frame_rgb = np.ascontiguousarray(capture[:, :, ::-1])
            frame_rgb_t = np.transpose(frame_rgb, (1, 0, 2))
            self._frame_surface = pygame.surfarray.make_surface(frame_rgb_t)

            self._screen.fill((0, 0, 0))
            src_w, src_h = capture.shape[1], capture.shape[0]
            dst_w, dst_h = self._config.width, self._config.height
            if self._config.fit_aspect and (src_w != dst_w or src_h != dst_h):
                scale = min(dst_w / src_w, dst_h / src_h)
                draw_w = max(1, int(src_w * scale))
                draw_h = max(1, int(src_h * scale))
                scaled = pygame.transform.smoothscale(
                    self._frame_surface, (draw_w, draw_h)
                )
                x = (dst_w - draw_w) // 2
                y = (dst_h - draw_h) // 2
                self._screen.blit(scaled, (x, y))
            else:
                self._screen.blit(self._frame_surface, (0, 0))

            pygame.display.flip()
            self._last_render_monotonic = now
            self._update_fps(time.time() - start_time)

            if self._frame_callback and self._game_mat is not None:
                self._frame_callback(self._game_mat)
            return True
        except Exception as e:
            self.logger.error(f"render_display 失败: {e}")
            return False

    def update_frame(self, frame: np.ndarray):
        """兼容旧调用：present + render（显示泵应改用 present_frame/render_display 分离）。"""
        self.present_frame(frame)
        self.render_display(force=True)

    def _update_fps(self, frame_time: float):
        """更新FPS统计"""
        self._frame_count += 1
        self._last_frame_time = frame_time

        if self._frame_count % 30 == 0:
            self._fps = 1.0 / frame_time if frame_time > 0 else 0

    def get_game_mat(self) -> Optional[np.ndarray]:
        """返回 game_mat 副本（识别/捕获唯一来源）。"""
        if self._game_mat is not None:
            return self._game_mat.copy()
        return None

    def capture_frame(self) -> Optional[np.ndarray]:
        """
        返回 game_mat 副本（BGR），与 streaming 识别路径一致。

        不读取窗口像素，避免隐藏/缩放影响模板匹配。
        """
        if self._game_mat is not None:
            return self._game_mat.copy()

        if not self._running or self._screen is None or not self._visible:
            return None

        try:
            frame = pygame.surfarray.array3d(self._screen)
            frame = np.transpose(frame, (1, 0, 2))
            import cv2
            return cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
        except Exception as e:
            self.logger.error(f"捕获帧失败: {e}")
            return None

    def get_bgr_frame(self) -> Optional[np.ndarray]:
        """获取BGR格式帧（用于OpenCV）"""
        return self.capture_frame()

    def get_rgb_frame(self) -> Optional[np.ndarray]:
        """获取RGB格式帧"""
        frame = self.capture_frame()
        if frame is None:
            return None
        import cv2
        return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    def hide(self):
        """隐藏窗口（自动化继续运行）。"""
        if sys.platform == 'win32':
            try:
                import ctypes
                hwnd = self._get_hwnd()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 0)  # SW_HIDE
            except Exception as e:
                self.logger.warning(f"隐藏窗口失败: {e}")
        self._visible = False
        self._state = SDLWindowState.HIDDEN
        self.logger.info("SDL窗口已隐藏")

    def show(self):
        """显示窗口。"""
        self._hwnd = None
        if sys.platform == 'win32':
            try:
                import ctypes
                hwnd = self._get_hwnd()
                if hwnd:
                    ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            except Exception as e:
                self.logger.warning(f"显示窗口失败: {e}")
        self._apply_window_constraints()
        self._bring_to_front()
        self._visible = True
        if self._running:
            self._state = SDLWindowState.RUNNING
        self.logger.info(
            "SDL窗口已显示: title=%s hwnd=%s rect=%s",
            self._config.title,
            self._get_hwnd(),
            self._get_window_rect(),
        )

    @property
    def is_visible(self) -> bool:
        return self._visible

    def set_frame_callback(self, callback: Callable[[np.ndarray], None]):
        """设置帧回调"""
        self._frame_callback = callback

    def process_events(self) -> bool:
        """
        处理pygame事件。

        关闭按钮默认隐藏窗口而非退出，避免中断自动化。
        """
        if not PYGAME_AVAILABLE:
            return False

        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self._close_requested = True
                    if self._close_callback:
                        try:
                            self._close_callback()
                        except Exception as exc:
                            self.logger.warning("close callback failed: %s", exc)
                        continue
                    if self._config.hide_on_close:
                        self.hide()
                        continue
                    self.close()
                    return False

                if event.type in self._event_callbacks:
                    self._event_callbacks[event.type](event)

            return True

        except Exception as e:
            self.logger.error(f"处理事件失败: {e}")
            return True

    def register_event_callback(self, event_type: int, callback: Callable):
        """注册事件回调"""
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
            try:
                pygame.display.quit()
            except Exception:
                pass

        self.logger.info("SDL窗口已关闭")

    async def destroy(self):
        """任务清理别名；键盘映射仍活跃时不调用 pygame.quit()。"""
        self._running = False
        self._state = SDLWindowState.CLOSED
        if sys.platform == "win32":
            try:
                import ctypes
                hwnd = self._get_hwnd()
                if hwnd:
                    ctypes.windll.user32.DestroyWindow(hwnd)
            except Exception as e:
                self.logger.debug("DestroyWindow: %s", e)
        self.logger.info("SDL窗口已销毁")

    async def wait_for_close(self):
        """等待窗口关闭"""
        while self._running:
            if not self.process_events():
                break
            await asyncio.sleep(0.01)

        self.close()

    def get_stats(self) -> dict:
        """获取窗口统计信息"""
        return {
            'state': self._state.value,
            'display_resolution': f"{self._config.width}x{self._config.height}",
            'source_resolution': f"{self._source_size[0]}x{self._source_size[1]}",
            'fps': self._fps,
            'frame_time_ms': self._last_frame_time * 1000,
            'frames_rendered': self._frame_count,
            'running': self._running,
            'visible': self._visible,
        }

    @property
    def state(self) -> SDLWindowState:
        return self._state

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def width(self) -> int:
        return self._config.width

    @property
    def height(self) -> int:
        return self._config.height

    @property
    def surface(self):
        return self._screen


class SDLFrameCapture:
    """SDL窗口帧捕获器（降级路径，优先返回原始源帧）"""

    def __init__(self, window: SDLStreamWindow):
        self.logger = get_logger('sdl_capture')
        self._window = window
        self._capture_count = 0
        self._last_capture_time = 0

    async def capture_frame(self) -> Optional[np.ndarray]:
        start_time = time.time()
        frame = self._window.capture_frame()

        if frame is not None:
            self._capture_count += 1
            self._last_capture_time = (time.time() - start_time) * 1000

        return frame

    def get_stats(self) -> dict:
        return {
            'frames_captured': self._capture_count,
            'last_capture_time_ms': self._last_capture_time,
            'window_stats': self._window.get_stats()
        }

    @property
    def capture_count(self) -> int:
        return self._capture_count


sdl_stream_window = SDLStreamWindow()
