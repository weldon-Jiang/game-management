"""
Video Frame Capture - Captures frames from Xbox streaming window
================================================================

功能说明：
- 从Xbox流媒体窗口捕获视频帧
- 提供窗口内容截图功能
- 支持帧的编码和转换
- 维护帧缓存和帧计数器
- 支持GPU加速解码
- 支持高性能视频流模式（方案C优化）

技术实现：
- 使用win32 API捕获窗口内容（默认）
- 可选GPU加速解码（通过GPUFrameCapture）
- 支持RTP视频流接收（通过VideoStreamController）
- 使用PIL和numpy处理图像数据
- 支持RGB格式输出
- 异步捕获避免阻塞

帧数据结构：
- data: numpy数组（高度 x 宽度 x 3 RGB）
- frame_id: 唯一标识符
- timestamp: 捕获时间戳
- width/height: 帧尺寸

作者：技术团队
版本：3.0（新增高性能视频流模式）
"""

import asyncio
import numpy as np
from typing import Optional, Tuple
from dataclasses import dataclass

from ..core.config import config
from ..core.logger import get_logger

try:
    from .gpu_frame_capture import GPUFrameCapture
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    GPUFrameCapture = None


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
    - fps: 帧率（新增）
    """
    data: np.ndarray                  # 帧图像数据
    frame_id: str                    # 帧唯一标识符
    timestamp: float                  # 捕获时间戳
    width: int                       # 帧宽度
    height: int                      # 帧高度
    fps: float = 0.0                 # 捕获帧率

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
    - 支持GPU加速解码（可选）
    - 支持高性能视频流模式（方案C优化）

    捕获模式优先级：
    1. RTP视频流模式（最高性能，30-60fps）
    2. 直接捕获模式（中等性能，20-30fps）
    3. 窗口截图模式（基础性能，10-15fps）

    使用方式：
    - 创建实例后调用 capture_frame() 捕获单帧
    - 调用 start_capture() 开始持续捕获
    - 调用 capture_region() 捕获指定区域
    - 使用 GPU 模式：VideoFrameCapture(use_gpu=True)
    """

    def __init__(self, window, use_gpu: bool = False):
        """
        初始化视频捕获器

        参数说明：
        - window: StreamWindow窗口管理器实例
        - use_gpu: 是否使用GPU加速（默认False）
        """
        self.window = window  # 窗口管理器
        self._running = False  # 捕获运行状态
        self._capture_interval = config.get('video.capture_interval', 0.1)  # 捕获间隔
        self._frame_counter = 0  # 帧计数器
        self._last_frame: Optional[Frame] = None  # 最后捕获的帧
        self.logger = get_logger('video')  # 日志记录器
        self._capture_lock = asyncio.Lock()

        self._use_gpu = use_gpu and GPU_AVAILABLE
        self._gpu_capture: Optional[GPUFrameCapture] = None
        
        # 方案C新增：高性能视频流控制器
        self._video_controller = None  # 视频流控制器（RTP模式）
        self._webrtc_controller = None  # WebRTC帧控制器（云端串流）
        self._direct_capture = None    # 直接捕获控制器
        self._capture_mode = 'window'  # 捕获模式: 'webrtc' | 'rtp' | 'direct' | 'gpu' | 'window'

        if self._use_gpu:
            self.logger.info("GPU加速已启用")
            self._gpu_capture = GPUFrameCapture(use_gpu=True)
        else:
            self.logger.info("使用窗口截图模式（无GPU加速）")

    def set_video_controller(self, controller):
        """
        设置视频流控制器（方案C）

        参数：
        - controller: VideoStreamController实例
        """
        self._video_controller = controller
        if controller:
            self.logger.info("已设置视频流控制器")

    def set_webrtc_controller(self, controller):
        """设置 WebRTC 帧控制器（云端串流）。"""
        self._webrtc_controller = controller
        if controller:
            self.logger.info("已设置 WebRTC 帧控制器")

    def set_direct_capture(self, capture):
        """
        设置直接捕获控制器（方案C）

        参数：
        - capture: DirectCaptureController实例
        """
        self._direct_capture = capture
        if capture:
            self.logger.info("已设置直接捕获控制器")

    def set_capture_mode(self, mode: str):
        """
        设置捕获模式（方案C）

        参数：
        - mode: 捕获模式 ('webrtc' | 'rtp' | 'direct' | 'gpu' | 'window')
        """
        self._capture_mode = mode
        self.logger.info(f"捕获模式已设置为: {mode}")

    @property
    def last_frame(self) -> Optional[Frame]:
        """
        获取最后捕获的帧

        返回值：Frame对象，如果没有则返回None
        """
        return self._last_frame

    async def initialize_gpu(
        self,
        stream_url: Optional[str] = None,
        codec: str = "h264",
        width: int = 1280,
        height: int = 720
    ) -> bool:
        """
        初始化GPU加速

        参数说明：
        - stream_url: 视频流URL（可选）
        - codec: 视频编码格式
        - width: 宽度
        - height: 高度

        返回值：
        - True: 初始化成功
        - False: 初始化失败
        """
        if not self._use_gpu or self._gpu_capture is None:
            self.logger.warning("GPU模式未启用")
            return False

        try:
            success = await self._gpu_capture.initialize(
                stream_url=stream_url,
                codec=codec,
                width=width,
                height=height
            )
            if success:
                self.logger.info("GPU帧捕获初始化成功")
            return success
        except Exception as e:
            self.logger.error(f"GPU初始化失败: {e}")
            return False

    async def capture_frame(self) -> Optional[Frame]:
        """
        捕获单个视频帧

        返回值：
        - 成功：Frame对象
        - 失败：None

        实现说明（方案C优化）：
        1. 如果有视频流控制器且模式为RTP，优先使用RTP模式（最高性能）
        2. 如果有直接捕获控制器且模式为direct，使用直接捕获（中等性能）
        3. 如果启用GPU且已初始化，使用GPU捕获（中等性能）
        4. 否则使用窗口截图（基础性能）
        """
        async with self._capture_lock:
            return await self._capture_frame_unlocked()

    async def _capture_frame_unlocked(self) -> Optional[Frame]:
        # 云端 WebRTC 视频流（最高优先级）
        if self._capture_mode == 'webrtc' and self._webrtc_controller:
            return await self._capture_webrtc_frame()

        # 方案C优化：优先使用RTP视频流
        if self._capture_mode == 'rtp' and self._video_controller:
            return await self._capture_rtp_frame()
        
        # 方案C优化：使用直接捕获
        if self._capture_mode == 'direct' and self._direct_capture:
            return await self._capture_direct_frame()
        
        # GPU模式
        if self._use_gpu and self._gpu_capture and self._gpu_capture.is_initialized:
            return await self._capture_gpu_frame()

        return await self._capture_window_frame()

    async def _capture_webrtc_frame(self) -> Optional[Frame]:
        """使用 WebRTC video track 捕获帧。"""
        try:
            if not self._webrtc_controller:
                self.logger.warning("WebRTC 控制器不可用")
                return None

            frame_data = await self._webrtc_controller.get_frame(timeout=0.5)
            if frame_data is not None and isinstance(frame_data, np.ndarray):
                self._frame_counter += 1
                loop = asyncio.get_event_loop()
                frame_id = f"frame_{self._frame_counter}_{int(loop.time() * 1000)}"
                frame = Frame(
                    data=frame_data,
                    frame_id=frame_id,
                    timestamp=loop.time(),
                    width=frame_data.shape[1] if len(frame_data.shape) > 1 else 1280,
                    height=frame_data.shape[0] if len(frame_data.shape) > 1 else 720,
                    fps=getattr(self._webrtc_controller, 'fps', 0.0),
                )
                self._last_frame = frame
                return frame

            self.logger.warning("WebRTC 帧为空")
            return None
        except Exception as e:
            self.logger.error(f"WebRTC 帧捕获失败: {e}")
            return None

    async def _capture_rtp_frame(self) -> Optional[Frame]:
        """使用RTP视频流捕获帧（最高性能）"""
        try:
            if not self._video_controller:
                return await self._capture_window_frame()

            frame_data = await self._video_controller.get_frame(timeout=0.5)

            if frame_data is not None and isinstance(frame_data, np.ndarray):
                self._frame_counter += 1
                loop = asyncio.get_event_loop()
                frame_id = f"frame_{self._frame_counter}_{int(loop.time() * 1000)}"
                
                frame = Frame(
                    data=frame_data,
                    frame_id=frame_id,
                    timestamp=loop.time(),
                    width=frame_data.shape[1] if len(frame_data.shape) > 1 else 1280,
                    height=frame_data.shape[0] if len(frame_data.shape) > 1 else 720,
                    fps=self._video_controller.fps if hasattr(self._video_controller, 'fps') else 0.0
                )
                self._last_frame = frame
                return frame
            else:
                self.logger.warning("RTP帧为空，降级到窗口截图")
                return await self._capture_window_frame()

        except Exception as e:
            self.logger.error(f"RTP帧捕获失败，回退到窗口截图: {e}")
            return await self._capture_window_frame()

    async def _capture_direct_frame(self) -> Optional[Frame]:
        """使用直接捕获模式（中等性能）"""
        try:
            if not self._direct_capture:
                return await self._capture_window_frame()

            frame_data = await self._direct_capture.get_frame(timeout=0.5)

            if frame_data is not None:
                self._frame_counter += 1
                loop = asyncio.get_event_loop()
                frame_id = f"frame_{self._frame_counter}_{int(loop.time() * 1000)}"
                
                frame = Frame(
                    data=frame_data,
                    frame_id=frame_id,
                    timestamp=loop.time(),
                    width=frame_data.shape[1] if len(frame_data.shape) > 1 else 1280,
                    height=frame_data.shape[0] if len(frame_data.shape) > 1 else 720,
                    fps=getattr(self._direct_capture, 'fps', 0.0)
                )
                self._last_frame = frame
                return frame
            else:
                return await self._capture_window_frame()

        except Exception as e:
            self.logger.error(f"直接捕获失败，回退到窗口截图: {e}")
            return await self._capture_window_frame()

    async def _capture_gpu_frame(self) -> Optional[Frame]:
        """使用GPU捕获帧"""
        try:
            frame_data = await self._gpu_capture.capture_frame()

            if frame_data is not None:
                self._frame_counter += 1
                loop = asyncio.get_event_loop()
                frame_id = f"frame_{self._frame_counter}_{int(loop.time() * 1000)}"
                self._last_frame = Frame(
                    data=frame_data,
                    frame_id=frame_id,
                    timestamp=loop.time(),
                    width=frame_data.shape[1] if len(frame_data.shape) > 1 else 0,
                    height=frame_data.shape[0] if len(frame_data.shape) > 1 else 0
                )
                return self._last_frame

        except Exception as e:
            self.logger.error(f"GPU帧捕获失败，回退到窗口截图: {e}")

        return await self._capture_window_frame()

    async def _capture_window_frame(self) -> Optional[Frame]:
        """
        使用窗口截图捕获帧

        返回值：
        - 成功：Frame对象
        - 失败：None
        """
        try:
            loop = asyncio.get_event_loop()
            rect = await self.window.get_client_rect()

            if not rect:
                return None

            x, y, width, height = rect
            self.logger.debug(f"Capturing frame from {x},{y} size {width}x{height}")

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

    async def start_gpu_capture(self, frame_provider, on_frame=None):
        """
        开始GPU持续捕获

        参数：
        - frame_provider: 帧数据提供者（返回H.264数据的协程）
        - on_frame: 帧回调函数（可选）
        """
        if not self._use_gpu or self._gpu_capture is None:
            self.logger.warning("GPU模式未启用")
            return

        await self._gpu_capture.start_capture(frame_provider, on_frame)
        self.logger.info("GPU持续捕获已启动")

    def stop_gpu_capture(self):
        """停止GPU捕获"""
        if self._gpu_capture:
            self._gpu_capture.stop_capture()
            self.logger.info("GPU捕获已停止")

    def get_gpu_stats(self) -> Optional[dict]:
        """
        获取GPU捕获统计

        返回值：
        - GPU统计信息字典
        """
        if self._gpu_capture:
            stats = self._gpu_capture.get_stats()
            return {
                'frames_captured': stats.frames_captured,
                'capture_fps': stats.capture_fps,
                'decode_fps': stats.decode_fps,
                'avg_capture_time_ms': stats.avg_capture_time_ms,
                'avg_decode_time_ms': stats.avg_decode_time_ms,
                'buffer_size': stats.buffer_size,
                'dropped_frames': stats.dropped_frames
            }
        return None

    def get_gpu_info(self) -> Optional[dict]:
        """
        获取GPU解码器信息

        返回值：
        - GPU信息字典
        """
        if self._gpu_capture:
            return self._gpu_capture.get_decoder_info()
        return None

    @property
    def is_gpu_enabled(self) -> bool:
        """检查是否启用了GPU加速"""
        return self._use_gpu

    @property
    def is_gpu_initialized(self) -> bool:
        """检查GPU是否已初始化"""
        return self._gpu_capture is not None and self._gpu_capture.is_initialized

    async def close(self):
        """关闭捕获器，释放资源"""
        if self._video_controller:
            await self._video_controller.stop()
        if self._direct_capture:
            await self._direct_capture.stop()
        if self._gpu_capture:
            await self._gpu_capture.close()
        self.logger.info("VideoFrameCapture已关闭")

    def get_performance_stats(self) -> dict:
        """
        获取性能统计信息（方案C新增）

        返回值：
        - 性能统计字典
        """
        stats = {
            'capture_mode': self._capture_mode,
            'frame_counter': self._frame_counter,
            'has_video_controller': self._video_controller is not None,
            'has_direct_capture': self._direct_capture is not None,
            'has_gpu_capture': self._gpu_capture is not None
        }

        if self._video_controller and hasattr(self._video_controller, 'get_stats'):
            stats['video_controller'] = self._video_controller.get_stats()
            stats['video_controller']['fps'] = self._video_controller.fps

        if self._direct_capture and hasattr(self._direct_capture, 'fps'):
            stats['direct_capture_fps'] = self._direct_capture.fps

        if self._gpu_capture:
            stats['gpu'] = self.get_gpu_stats()

        return stats

    def log_performance_stats(self):
        """记录性能统计到日志"""
        stats = self.get_performance_stats()
        
        fps = 0.0
        if 'video_controller' in stats:
            fps = stats['video_controller'].get('fps', 0.0)
        elif 'direct_capture_fps' in stats:
            fps = stats['direct_capture_fps']
        
        mode_names = {
            'rtp': 'RTP视频流',
            'direct': '直接捕获',
            'gpu': 'GPU加速',
            'window': '窗口截图'
        }
        mode_name = mode_names.get(self._capture_mode, self._capture_mode)
        
        self.logger.info(f"捕获性能: 模式={mode_name}, 帧率={fps:.1f}fps, 帧数={stats['frame_counter']}")
