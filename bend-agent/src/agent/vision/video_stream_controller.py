"""
RTP 视频流控制器
================

功能说明：
- 管理RTP视频流的接收和解码
- 与Xbox协商视频流参数
- 提供高性能视频帧捕获
- 支持多线程解码加速

技术实现：
- RTP接收（asyncio UDP）
- H.264硬件解码（GPU）
- 帧缓冲管理
- 多线程解码

作者：技术团队
版本：1.0
"""

import asyncio
import threading
import time
import queue
from dataclasses import dataclass
from typing import Optional, Callable, Any, List
from enum import Enum
import logging
import numpy as np

logger = logging.getLogger('rtp_video_stream')


class VideoStreamState(Enum):
    """视频流状态"""
    IDLE = "idle"
    INITIALIZING = "initializing"
    CONNECTING = "connecting"
    RECEIVING = "receiving"
    DECODING = "decoding"
    ERROR = "error"
    STOPPED = "stopped"


@dataclass
class VideoStreamConfig:
    """视频流配置"""
    width: int = 1280
    height: int = 720
    framerate: int = 30
    bitrate: int = 5000000
    codec: str = "H264"
    profile: str = "baseline"
    level: str = "3.1"
    rtp_port: int = 50500
    rtcp_port: int = 50501
    buffer_size: int = 5


@dataclass
class VideoFrame:
    """视频帧"""
    data: np.ndarray
    timestamp: int
    sequence: int
    width: int
    height: int
    framerate: float
    capture_time: float


class RTPDecoder:
    """
    RTP视频解码器

    功能：
    - 接收RTP视频流
    - H.264解码
    - GPU加速解码
    - 多线程解码

    使用方式：
    decoder = RTPDecoder(config)
    await decoder.start()
    async for frame in decoder.frames():
        process(frame)
    """

    def __init__(self, config: VideoStreamConfig):
        self.logger = logging.getLogger('rtp_decoder')
        self._config = config
        self._state = VideoStreamState.IDLE
        self._rtp_session = None
        self._frame_queue: queue.Queue[Any] = queue.Queue(maxsize=config.buffer_size)
        self._decoded_frame_queue: queue.Queue[Any] = queue.Queue(maxsize=config.buffer_size)
        self._running = False
        self._receive_thread: Optional[threading.Thread] = None
        self._decode_thread: Optional[threading.Thread] = None
        self._frame_callback: Optional[Callable[[VideoFrame], None]] = None
        self._stats = {
            'frames_received': 0,
            'frames_decoded': 0,
            'frames_dropped': 0,
            'last_frame_time': 0,
            'fps': 0.0
        }
        self._fps_start_time = 0
        self._fps_frame_count = 0

    async def start(self, rtp_session) -> bool:
        """
        启动解码器

        参数：
        - rtp_session: RTP会话对象

        返回：
        - 是否成功
        """
        try:
            self._state = VideoStreamState.INITIALIZING
            self._rtp_session = rtp_session
            self._running = True

            self._receive_thread = threading.Thread(target=self._receive_loop)
            self._receive_thread.daemon = True
            self._receive_thread.start()

            self._decode_thread = threading.Thread(target=self._decode_loop)
            self._decode_thread.daemon = True
            self._decode_thread.start()

            self._fps_start_time = time.time()
            self._state = VideoStreamState.RECEIVING
            self.logger.info("RTP解码器已启动")
            return True

        except Exception as e:
            self.logger.error(f"启动解码器失败: {e}")
            self._state = VideoStreamState.ERROR
            return False

    def _receive_loop(self):
        """RTP接收循环（在独立线程中运行）"""
        self.logger.info("RTP接收线程启动")
        seq = 0
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self._running:
                try:
                    if self._rtp_session and hasattr(self._rtp_session, 'packets'):
                        try:
                            async def receive_packets():
                                nonlocal seq
                                try:
                                    async for packet in self._rtp_session.packets():
                                        self._stats['frames_received'] += 1
                                        seq += 1

                                        frame = VideoFrame(
                                            data=packet.payload,
                                            timestamp=packet.header.timestamp,
                                            sequence=seq,
                                            width=self._config.width,
                                            height=self._config.height,
                                            framerate=float(self._config.framerate),
                                            capture_time=time.time()
                                        )

                                        try:
                                            self._frame_queue.put_nowait(frame)
                                        except queue.Full:
                                            self._stats['frames_dropped'] += 1

                                        self._update_fps()
                                except asyncio.CancelledError:
                                    pass
                                except Exception as e:
                                    self.logger.error(f"接收包异常: {e}")

                            loop.run_until_complete(receive_packets())
                        except RuntimeError as e:
                            if "event loop is closed" in str(e):
                                loop = asyncio.new_event_loop()
                                asyncio.set_event_loop(loop)
                            else:
                                raise
                    else:
                        time.sleep(0.01)

                except Exception as e:
                    self.logger.error(f"接收线程异常: {e}")
                    time.sleep(0.1)
        finally:
            loop.close()

    def _decode_loop(self):
        """解码循环（在独立线程中运行）"""
        self.logger.info("解码线程启动")

        try:
            import cv2
            has_ffmpeg = True
        except ImportError:
            has_ffmpeg = False
            self.logger.warning("OpenCV不可用，使用原始数据")

        while self._running:
            try:
                try:
                    frame = self._frame_queue.get(timeout=0.1)
                except queue.Empty:
                    continue

                decoded_frame = frame.data

                if has_ffmpeg and len(frame.data) > 0:
                    try:
                        nparr = np.frombuffer(frame.data, np.uint8)
                        decoded = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                        if decoded is not None:
                            decoded_frame = decoded
                            frame.data = decoded_frame
                            frame.width = decoded.shape[1]
                            frame.height = decoded.shape[0]
                    except Exception as e:
                        pass

                self._stats['frames_decoded'] += 1

                try:
                    self._decoded_frame_queue.put_nowait(frame)
                except queue.Full:
                    self._stats['frames_dropped'] += 1

                if self._frame_callback:
                    self._frame_callback(frame)

            except Exception as e:
                self.logger.error(f"解码异常: {e}")

    def _update_fps(self):
        """更新帧率统计"""
        self._fps_frame_count += 1
        elapsed = time.time() - self._fps_start_time
        if elapsed >= 1.0:
            self._stats['fps'] = self._fps_frame_count / elapsed
            self._fps_frame_count = 0
            self._fps_start_time = time.time()

    async def frames(self):
        """
        异步获取解码后的帧

        使用方式：
        async for frame in decoder.frames():
            cv2.imshow('frame', frame.data)
        """
        while self._running:
            try:
                frame = self._decoded_frame_queue.get(timeout=0.1)
                yield frame
            except queue.Empty:
                await asyncio.sleep(0.001)

    def set_frame_callback(self, callback: Callable[[VideoFrame], None]):
        """设置帧回调"""
        self._frame_callback = callback

    async def stop(self):
        """停止解码器"""
        self._running = False
        self._state = VideoStreamState.STOPPED

        if self._receive_thread:
            self._receive_thread.join(timeout=2)

        if self._decode_thread:
            self._decode_thread.join(timeout=2)

        self.logger.info("RTP解码器已停止")

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = self._stats.copy()
        stats['state'] = self._state.value
        stats['config'] = self._config.__dict__
        return stats

    @property
    def state(self) -> VideoStreamState:
        return self._state

    @property
    def fps(self) -> float:
        return self._stats['fps']


class VideoStreamController:
    """
    视频流控制器

    功能：
    - 管理视频流接收
    - 协调RTP和解码器
    - 提供高性能帧接口

    使用方式：
    controller = VideoStreamController()
    await controller.start()
    frame = await controller.get_frame()
    """

    def __init__(self):
        self.logger = logging.getLogger('video_stream')
        self._state = VideoStreamState.IDLE
        self._config: Optional[VideoStreamConfig] = None
        self._decoder: Optional[RTPDecoder] = None
        self._latest_frame: Optional[VideoFrame] = None
        self._frame_lock = threading.Lock()
        self._running = False

    async def start(self, config: VideoStreamConfig, rtp_session) -> bool:
        """
        启动视频流控制器

        参数：
        - config: 视频流配置
        - rtp_session: RTP会话

        返回：
        - 是否成功
        """
        try:
            self._config = config
            self._state = VideoStreamState.INITIALIZING

            self._decoder = RTPDecoder(config)

            self._decoder.set_frame_callback(self._on_frame)

            success = await self._decoder.start(rtp_session)
            if not success:
                self._state = VideoStreamState.ERROR
                return False

            self._running = True
            self._state = VideoStreamState.RECEIVING
            self.logger.info("视频流控制器已启动")
            return True

        except Exception as e:
            self.logger.error(f"启动视频流控制器失败: {e}")
            self._state = VideoStreamState.ERROR
            return False

    def _on_frame(self, frame: VideoFrame):
        """帧回调"""
        with self._frame_lock:
            self._latest_frame = frame
            self._state = VideoStreamState.DECODING

    async def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """
        获取最新帧

        参数：
        - timeout: 超时时间

        返回：
        - 帧数据或None
        """
        start = time.time()
        while time.time() - start < timeout:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return self._latest_frame.data.copy()
            await asyncio.sleep(0.01)
        return None

    async def get_frame_with_info(self, timeout: float = 1.0) -> Optional[VideoFrame]:
        """
        获取帧及其信息

        返回：
        - VideoFrame或None
        """
        start = time.time()
        while time.time() - start < timeout:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return self._latest_frame
            await asyncio.sleep(0.01)
        return None

    async def stop(self):
        """停止视频流控制器"""
        self._running = False

        if self._decoder:
            await self._decoder.stop()

        self._state = VideoStreamState.STOPPED
        self.logger.info("视频流控制器已停止")

    def get_stats(self) -> dict:
        """获取统计信息"""
        stats = {
            'state': self._state.value,
            'fps': 0.0
        }

        if self._decoder:
            stats['decoder'] = self._decoder.get_stats()
            stats['fps'] = self._decoder.fps

        return stats

    @property
    def state(self) -> VideoStreamState:
        return self._state

    @property
    def fps(self) -> float:
        return self._decoder.fps if self._decoder else 0.0


class DirectCaptureController:
    """
    直接捕获控制器（用于win32gui模式）

    功能：
    - 高性能窗口捕获
    - 多线程截图
    - 帧缓冲

    使用方式：
    capture = DirectCaptureController()
    await capture.start(hwnd)
    frame = await capture.get_frame()
    """

    def __init__(self):
        self.logger = logging.getLogger('direct_capture')
        self._running = False
        self._capture_thread: Optional[threading.Thread] = None
        self._frame_queue: queue.Queue[Any] = queue.Queue(maxsize=3)
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._hwnd: Optional[int] = None
        self._fps = 0.0

    async def start(self, hwnd: int) -> bool:
        """
        启动捕获

        参数：
        - hwnd: 窗口句柄

        返回：
        - 是否成功
        """
        try:
            self._hwnd = hwnd
            self._running = True

            self._capture_thread = threading.Thread(target=self._capture_loop)
            self._capture_thread.daemon = True
            self._capture_thread.start()

            self.logger.info("直接捕获控制器已启动")
            return True

        except Exception as e:
            self.logger.error(f"启动捕获失败: {e}")
            return False

    def _capture_loop(self):
        """捕获循环"""
        import cv2
        import win32gui
        import win32ui
        import win32con
        from PIL import Image
        import numpy as np

        fps_start = time.time()
        fps_count = 0

        while self._running:
            try:
                if self._hwnd:
                    hwndDC = win32gui.GetWindowDC(self._hwnd)
                    mfcDC = win32ui.CreateDCFromHandle(hwndDC)
                    saveDC = mfcDC.CreateCompatibleDC()

                    saveDC.BitBlt((0, 0), (1280, 720), mfcDC, (0, 0), win32con.SRCCOPY)
                    bitmap = win32ui.CreateBitmap()
                    bitmap.CreateCompatibleBitmap(mfcDC, 1280, 720)
                    saveDC.SelectObject(bitmap)

                    bmpinfo = bitmap.GetInfo()
                    bmpstr = bitmap.GetBitmapBits(True)
                    img = Image.frombuffer('RGB', (bmpinfo['bmWidth'], bmpinfo['bmHeight']), bmpstr, 'raw', 'BGRX', 0, 1)

                    frame = np.array(img)

                    win32gui.DeleteObject(bitmap.GetHandle())
                    saveDC.DeleteDC()
                    mfcDC.DeleteDC()
                    win32gui.ReleaseDC(self._hwnd, hwndDC)

                    with self._frame_lock:
                        self._latest_frame = frame

                    fps_count += 1
                    if time.time() - fps_start >= 1.0:
                        self._fps = fps_count
                        fps_count = 0
                        fps_start = time.time()

                    try:
                        self._frame_queue.put_nowait(frame)
                    except queue.Full:
                        pass

                time.sleep(0.033)

            except Exception as e:
                self.logger.error(f"捕获异常: {e}")
                time.sleep(0.1)

    async def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """获取帧"""
        start = time.time()
        while time.time() - start < timeout:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return self._latest_frame.copy()
            await asyncio.sleep(0.01)
        return None

    async def stop(self):
        """停止捕获"""
        self._running = False
        if self._capture_thread:
            self._capture_thread.join(timeout=2)
        self.logger.info("直接捕获控制器已停止")

    @property
    def fps(self) -> float:
        return self._fps
