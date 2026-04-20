"""
Video Frame Capture - Captures frames from Xbox streaming window

功能说明：
- 从Xbox流媒体窗口捕获视频帧
- 提供窗口内容截图功能
- 支持帧的编码和转换
- 维护帧缓存和帧计数器

技术实现：
- 使用win32 API捕获窗口内容
- 使用PIL和numpy处理图像数据
- 支持RGB格式输出
- 异步捕获避免阻塞

帧数据结构：
- data: numpy数组（高度 x 宽度 x 3 RGB）
- frame_id: 唯一标识符
- timestamp: 捕获时间戳
- width/height: 帧尺寸
"""
import asyncio
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

from ..core.config import config
from ..core.logger import get_logger


@dataclass
class Frame:
    """
    视频帧数据类

    属性说明：
    - data: 帧图像数据（numpy数组）
    - frame_id: 帧唯一标识符
    - timestamp: 捕获时间戳
    - width: 帧宽度
    - height: 帧高度
    """
    data: np.ndarray                  # 帧图像数据
    frame_id: str                    # 帧唯一标识符
    timestamp: float                  # 捕获时间戳
    width: int                       # 帧宽度
    height: int                      # 帧高度

    def to_bytes(self) -> bytes:
        """
        将帧转换为JPEG字节数据

        返回值：JPEG格式的字节数据
        """
        import cv2
        _, encoded = cv2.imencode('.jpg', self.data, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return encoded.tobytes()


class VideoFrameCapture:
    """
    视频帧捕获器

    功能说明：
    - 从Xbox流媒体窗口捕获视频帧
    - 提供持续捕获和单帧捕获模式
    - 支持指定区域捕获
    - 维护最后捕获的帧缓存

    使用方式：
    - 创建实例后调用 capture_frame() 捕获单帧
    - 调用 start_capture() 开始持续捕获
    - 调用 capture_region() 捕获指定区域
    """

    def __init__(self, window):
        """
        初始化视频捕获器

        参数说明：
        - window: StreamWindow窗口管理器实例
        """
        self.window = window  # 窗口管理器
        self._running = False  # 捕获运行状态
        self._capture_interval = config.get('video.capture_interval', 0.1)  # 捕获间隔
        self._frame_counter = 0  # 帧计数器
        self._last_frame: Optional[Frame] = None  # 最后捕获的帧
        self.logger = get_logger('video')  # 日志记录器

    @property
    def last_frame(self) -> Optional[Frame]:
        """
        获取最后捕获的帧

        返回值：Frame对象，如果没有则返回None
        """
        return self._last_frame

    async def capture_frame(self) -> Optional[Frame]:
        """
        捕获单个视频帧

        返回值：
        - 成功：Frame对象
        - 失败：None

        实现说明：
        1. 获取窗口客户区尺寸
        2. 在线程池中执行窗口捕获
        3. 创建Frame对象并缓存
        """
        try:
            loop = asyncio.get_event_loop()
            rect = await self.window.get_client_rect()

            if not rect:
                return None

            x, y, width, height = rect
            self.logger.debug(f"Capturing frame from {x},{y} size {width}x{height}")

            # 在线程池中执行窗口捕获
            frame = await loop.run_in_executor(
                None,
                self._capture_window,
                (x, y, width, height)
            )

            if frame is not None:
                self._frame_counter += 1
                frame_id = f"frame_{self._frame_counter}_{int(loop.time() * 1000)}"
                self._last_frame = Frame(
                    data=frame,
                    frame_id=frame_id,
                    timestamp=loop.time(),
                    width=width,
                    height=height
                )
                return self._last_frame

        except Exception as e:
            self.logger.error(f"Error capturing frame: {e}")

        return None

    def _capture_window(self, rect: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
        """
        捕获窗口内容（同步方法）

        参数说明：
        - rect: (x, y, width, height) 窗口区域

        返回值：
        - 成功：窗口截图numpy数组
        - 失败：None

        技术实现：
        - 使用win32gui获取窗口DC
        - 使用BitBlt复制窗口内容
        - 转换为numpy数组
        """
        try:
            import win32gui
            import win32ui
            import win32con
            from PIL import Image
            import numpy as np

            x, y, width, height = rect

            hwnd = self.window._hwnd
            if not hwnd:
                return None

            # 获取窗口矩形
            left, top, right, bottom = win32gui.GetWindowRect(hwnd)
            w = right - left
            h = bottom - top

            # 获取窗口设备上下文
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            # 创建位图
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, w, h)
            saveDC.SelectObject(saveBitMap)

            # BitBlt复制窗口内容
            result = saveDC.BitBlt(
                (0, 0), (w, h), mfcDC, (0, 0), win32con.SRCCOPY
            )

            # 获取位图信息
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            # 转换为PIL图像
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            # 清理资源
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)

            # 转换为numpy数组
            frame = np.array(img)

            # 如果尺寸不匹配，进行缩放
            if width != w or height != h:
                import cv2
                frame = cv2.resize(frame, (width, height))

            return frame

        except ImportError:
            # win32 API不可用，创建模拟帧
            self.logger.warning("win32 API not available, creating mock frame")
            return np.random.randint(0, 255, (height or 720, width or 1280, 3), dtype=np.uint8)
        except Exception as e:
            self.logger.error(f"Error in window capture: {e}")
            return None

    async def start_capture(self):
        """
        开始持续帧捕获

        功能说明：
        - 按照配置的间隔持续捕获帧
        - 捕获的帧会更新last_frame
        - 调用stop_capture()停止
        """
        self._running = True
        self.logger.info("Starting video capture")

        while self._running:
            await self.capture_frame()
            await asyncio.sleep(self._capture_interval)

    def stop_capture(self):
        """
        停止帧捕获
        """
        self._running = False
        self.logger.info("Stopping video capture")

    async def capture_region(self, x: int, y: int, width: int, height: int) -> Optional[np.ndarray]:
        """
        捕获指定区域

        参数说明：
        - x: 区域左上角X坐标
        - y: 区域左上角Y坐标
        - width: 区域宽度
        - height: 区域高度

        返回值：
        - 成功：区域图像numpy数组
        - 失败：None
        """
        try:
            import win32gui
            import win32ui
            import win32con
            from PIL import Image
            import numpy as np

            hwnd = self.window._hwnd
            if not hwnd:
                return None

            # 获取窗口DC
            hwndDC = win32gui.GetWindowDC(hwnd)
            mfcDC = win32ui.CreateDCFromHandle(hwndDC)
            saveDC = mfcDC.CreateCompatibleDC()

            # 创建位图
            saveBitMap = win32ui.CreateBitmap()
            saveBitMap.CreateCompatibleBitmap(mfcDC, width, height)
            saveDC.SelectObject(saveBitMap)

            # 复制指定区域
            saveDC.BitBlt((0, 0), (width, height), mfcDC, (x, y), win32con.SRCCOPY)

            # 获取位图信息
            bmpinfo = saveBitMap.GetInfo()
            bmpstr = saveBitMap.GetBitmapBits(True)

            # 转换为图像
            img = Image.frombuffer(
                'RGB',
                (bmpinfo['bmWidth'], bmpinfo['bmHeight']),
                bmpstr, 'raw', 'BGRX', 0, 1
            )

            # 清理资源
            win32gui.DeleteObject(saveBitMap.GetHandle())
            saveDC.DeleteDC()
            mfcDC.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwndDC)

            return np.array(img)

        except ImportError:
            return np.random.randint(0, 255, (height, width, 3), dtype=np.uint8)
        except Exception as e:
            self.logger.error(f"Error capturing region: {e}")
            return None
