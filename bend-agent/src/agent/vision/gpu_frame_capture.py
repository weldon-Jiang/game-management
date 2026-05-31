"""
GPU加速帧捕获器
===============

功能说明：
- 结合GPU解码和帧捕获
- 支持从视频流获取原始H.264数据并进行GPU解码
- 异步捕获和解码
- 提供性能统计

技术实现参考（streaming项目）：
- FFmpeg GPU解码 (NVDEC/AMF/QSV)
- 帧缓冲管理

作者：技术团队
版本：1.0
"""

import asyncio
import time
import queue
from typing import Optional, Callable, Any
from dataclasses import dataclass
import numpy as np

from ..core.logger import get_logger
from .gpu_decoder import GPUDecoder, GPUType, DecoderConfig, gpu_detector


@dataclass
class CaptureStats:
    """捕获统计信息"""
    frames_captured: int = 0
    frames_decoded: int = 0
    capture_fps: float = 0.0
    decode_fps: float = 0.0
    avg_capture_time_ms: float = 0.0
    avg_decode_time_ms: float = 0.0
    buffer_size: int = 0
    dropped_frames: int = 0


class GPUFrameCapture:
    """
    GPU加速帧捕获器

    功能说明：
    - 从视频流获取H.264数据
    - 使用GPU进行硬件解码
    - 提供异步帧捕获接口
    - 支持帧缓冲管理

    使用方式：
    - capture = GPUFrameCapture()
    - await capture.initialize(stream_url)
    - frame = await capture.capture_frame()

    架构说明：
    ┌─────────────────────────────────────────────────────────┐
    │              GPUFrameCapture                            │
    │                                                         │
    │  ┌─────────────┐    ┌─────────────┐    ┌────────────┐ │
    │  │ 视频流数据   │───▶│ GPU解码器   │───▶│  帧输出    │ │
    │  │ (H.264)   │    │ (NVDEC)    │    │            │ │
    │  └─────────────┘    └─────────────┘    └────────────┘ │
    │         │                                        │    │
    │         │ 回调/队列                               │    │
    │         ▼                                        │    │
    │  ┌─────────────────────────────────────────────────┐ │
    │  │              帧缓冲管理                          │ │
    │  └─────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────┘
    """

    def __init__(self, use_gpu: bool = True):
        self.logger = get_logger('gpu_capture')
        self._use_gpu = use_gpu
        self._decoder = GPUDecoder()
        self._initialized = False
        self._running = False
        self._capture_task: Optional[asyncio.Task] = None
        self._frame_buffer: queue.Queue = queue.Queue(maxsize=10)
        self._stats = CaptureStats()
        self._stream_url: Optional[str] = None
        self._capture_callback: Optional[Callable] = None
        self._last_capture_time = 0
        self._last_decode_time = 0

    async def initialize(
        self,
        stream_url: Optional[str] = None,
        codec: str = "h264",
        width: int = 1280,
        height: int = 720,
        gpu_enabled: Optional[bool] = None
    ) -> bool:
        """
        初始化帧捕获器

        参数：
        - stream_url: 视频流URL（可选，用于WebRTC/RTMP等）
        - codec: 视频编码格式
        - width: 输出宽度
        - height: 输出高度
        - gpu_enabled: 是否启用GPU加速（None=自动检测）

        返回值：
        - True: 初始化成功
        - False: 初始化失败
        """
        try:
            self._stream_url = stream_url

            gpu_to_use = gpu_enabled if gpu_enabled is not None else self._use_gpu
            gpu_type = gpu_detector.detect()

            self.logger.info(f"GPU类型检测: {gpu_type.value}")
            self.logger.info(f"GPU加速: {'启用' if gpu_to_use and gpu_type != GPUType.CPU else '禁用'}")

            config = DecoderConfig(
                codec=codec,
                output_width=width,
                output_height=height,
                gpu_enabled=gpu_to_use
            )

            success = self._decoder.initialize(config)
            if not success:
                self.logger.error("GPU解码器初始化失败")
                return False

            self._initialized = True
            self._stats = CaptureStats()

            self.logger.info(f"GPU帧捕获器初始化成功: {width}x{height} @ {codec}")
            return True

        except Exception as e:
            self.logger.error(f"GPU帧捕获器初始化失败: {e}")
            return False

    async def start_capture(
        self,
        frame_provider: Callable,
        on_frame: Optional[Callable] = None
    ):
        """
        开始持续帧捕获

        参数：
        - frame_provider: 帧数据提供者（返回H.264数据的协程）
        - on_frame: 帧回调函数（可选）

        使用方式：
        async def get_h264_frame():
            # 从WebRTC或其他来源获取H.264数据
            return h264_data

        async def on_frame_received(frame):
            # 处理解码后的帧
            pass

        await capture.start_capture(get_h264_frame, on_frame)
        """
        if not self._initialized:
            self.logger.warning("帧捕获器未初始化")
            return

        self._running = True
        self._capture_callback = on_frame
        self._capture_task = asyncio.create_task(
            self._capture_loop(frame_provider)
        )
        self.logger.info("帧捕获已启动")

    async def _capture_loop(self, frame_provider: Callable):
        """
        帧捕获循环

        参数：
        - frame_provider: 帧数据提供者
        """
        while self._running:
            try:
                h264_data = await frame_provider()

                if h264_data is None:
                    await asyncio.sleep(0.01)
                    continue

                capture_start = time.time()

                decoded_frame = await self._decoder.decode_frame(h264_data)

                capture_time = (time.time() - capture_start) * 1000

                self._update_stats(capture_time)

                if decoded_frame is not None:
                    self._put_frame(decoded_frame)

                    if self._capture_callback:
                        self._capture_callback(decoded_frame)

                await asyncio.sleep(0.001)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"捕获循环错误: {e}")
                await asyncio.sleep(0.1)

    def _put_frame(self, frame: np.ndarray):
        """将帧放入缓冲区"""
        try:
            if self._frame_buffer.full():
                try:
                    self._frame_buffer.get_nowait()
                    self._stats.dropped_frames += 1
                except queue.Empty:
                    pass

            self._frame_buffer.put_nowait(frame)
            self._stats.buffer_size = self._frame_buffer.qsize()

        except queue.Full:
            self._stats.dropped_frames += 1

    def _update_stats(self, capture_time_ms: float):
        """更新统计信息"""
        self._stats.frames_captured += 1

        decode_time_ms = self._decoder.get_stats().last_decode_time_ms
        total_time_ms = capture_time_ms + decode_time_ms

        n = self._stats.frames_captured
        self._stats.avg_capture_time_ms = (
            self._stats.avg_capture_time_ms * (n - 1) + capture_time_ms
        ) / n
        self._stats.avg_decode_time_ms = (
            self._stats.avg_decode_time_ms * (n - 1) + decode_time_ms
        ) / n

        if self._stats.avg_capture_time_ms > 0:
            self._stats.capture_fps = 1000.0 / self._stats.avg_capture_time_ms
        if self._stats.avg_decode_time_ms > 0:
            self._stats.decode_fps = 1000.0 / self._stats.avg_decode_time_ms

    async def capture_frame(self) -> Optional[np.ndarray]:
        """
        捕获单帧

        返回值：
        - 解码后的帧（numpy数组）或None
        """
        try:
            if self._frame_buffer.empty():
                return None

            frame = self._frame_buffer.get_nowait()
            self._stats.buffer_size = self._frame_buffer.qsize()
            return frame

        except queue.Empty:
            return None

    async def get_frame_with_timeout(
        self,
        timeout: float = 1.0
    ) -> Optional[np.ndarray]:
        """
        获取帧（带超时）

        参数：
        - timeout: 超时时间（秒）

        返回值：
        - 帧数据或None
        """
        try:
            frame = self._frame_buffer.get(timeout=timeout)
            self._stats.buffer_size = self._frame_buffer.qsize()
            return frame
        except queue.Empty:
            return None

    def stop_capture(self):
        """停止帧捕获"""
        self._running = False

        if self._capture_task:
            self._capture_task.cancel()
            self._capture_task = None

        self.logger.info("帧捕获已停止")

    def get_stats(self) -> CaptureStats:
        """
        获取捕获统计

        返回值：
        - CaptureStats: 捕获统计数据
        """
        return self._stats

    def clear_buffer(self):
        """清空帧缓冲区"""
        while not self._frame_buffer.empty():
            try:
                self._frame_buffer.get_nowait()
            except queue.Empty:
                break
        self._stats.buffer_size = 0

    async def close(self):
        """关闭捕获器"""
        self.stop_capture()
        await self._decoder.close()
        self._initialized = False
        self.clear_buffer()
        self.logger.info("GPU帧捕获器已关闭")

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    @property
    def is_capturing(self) -> bool:
        """检查是否正在捕获"""
        return self._running

    def get_decoder_info(self) -> dict:
        """获取解码器信息"""
        return self._decoder.get_info()

    def get_buffer_size(self) -> int:
        """获取缓冲区大小"""
        return self._frame_buffer.qsize()

    def is_buffer_full(self) -> bool:
        """检查缓冲区是否已满"""
        return self._frame_buffer.full()


class StreamFrameCapture(GPUFrameCapture):
    """
    流式帧捕获器

    功能说明：
    - 专门用于从Xbox流获取帧
    - 集成视频流连接管理
    - 支持RTP/RTMP/WebRTC

    使用方式：
    - capture = StreamFrameCapture()
    - await capture.connect(xbox_ip)
    - frame = await capture.capture_frame()
    """

    def __init__(self, use_gpu: bool = True):
        super().__init__(use_gpu)
        self.logger = get_logger('stream_capture')
        self._xbox_ip: Optional[str] = None
        self._xbox_port: int = 5050
        self._stream_connected = False

    async def connect(
        self,
        xbox_ip: str,
        port: int = 5050,
        codec: str = "h264",
        width: int = 1280,
        height: int = 720
    ) -> bool:
        """
        连接到Xbox流

        参数：
        - xbox_ip: Xbox IP地址
        - port: 端口
        - codec: 编码格式
        - width: 宽度
        - height: 高度

        返回值：
        - True: 连接成功
        - False: 连接失败
        """
        self._xbox_ip = xbox_ip
        self._xbox_port = port

        self.logger.info(f"连接到Xbox流: {xbox_ip}:{port}")

        success = await self.initialize(
            stream_url=f"xbox://{xbox_ip}:{port}",
            codec=codec,
            width=width,
            height=height
        )

        if success:
            self._stream_connected = True

        return success

    async def disconnect(self):
        """断开Xbox流连接"""
        self._stream_connected = False
        await self.close()
        self.logger.info(f"已断开Xbox流连接: {self._xbox_ip}")

    @property
    def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._stream_connected and self._initialized


gpu_frame_capture = GPUFrameCapture()
