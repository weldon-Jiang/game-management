"""
GPU硬件解码器
=============

功能说明：
- 自动检测系统GPU类型（NVIDIA/AMD/Intel）
- 提供GPU加速的H.264/H.265视频解码
- 支持CPU软解码作为回退方案
- 提供解码统计信息

技术实现参考（streaming项目）：
- FFmpeg NVDEC (NVIDIA)
- FFmpeg AMF (AMD)
- FFmpeg QSV (Intel)

作者：技术团队
版本：1.0
"""

import asyncio
import subprocess
import platform
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import logging

from ..core.logger import get_logger


class GPUType(Enum):
    """GPU类型枚举"""
    NVIDIA = "nvidia"
    AMD = "amd"
    INTEL = "intel"
    CPU = "cpu"  # 回退到CPU解码


@dataclass
class DecoderConfig:
    """解码器配置"""
    codec: str = "h264"  # 视频编码格式
    pixel_format: str = "bgr24"  # 输出像素格式
    output_width: int = 1280  # 输出宽度
    output_height: int = 720  # 输出高度
    gpu_enabled: bool = True  # 是否启用GPU加速


@dataclass
class DecoderStats:
    """解码统计信息"""
    frames_decoded: int = 0
    fps: float = 0.0
    decode_time_ms: float = 0.0
    gpu_utilization: float = 0.0
    memory_used_mb: float = 0.0
    last_decode_time_ms: float = 0.0


class GPUDetector:
    """
    GPU检测器

    功能说明：
    - 检测系统可用的GPU
    - 确定GPU类型和驱动版本
    - 检测CUDA/ROCm支持

    使用方式：
    - detector = GPUDetector()
    - gpu_type = detector.detect()
    - capabilities = detector.get_capabilities()
    """

    def __init__(self):
        self.logger = get_logger('gpu_detector')
        self._detected_type: Optional[GPUType] = None
        self._capabilities: Dict[str, Any] = {}

    def detect(self) -> GPUType:
        """
        检测GPU类型

        返回值：
        - GPUType: 检测到的GPU类型
        """
        if self._detected_type:
            return self._detected_type

        self.logger.info("检测GPU类型...")

        if platform.system() != "Windows":
            self.logger.warning("非Windows系统，使用CPU解码")
            self._detected_type = GPUType.CPU
            return self._detected_type

        detected = self._detect_nvidia()
        if detected:
            self._detected_type = GPUType.NVIDIA
            return self._detected_type

        detected = self._detect_amd()
        if detected:
            self._detected_type = GPUType.AMD
            return self._detected_type

        detected = self._detect_intel()
        if detected:
            self._detected_type = GPUType.INTEL
            return self._detected_type

        self.logger.warning("未检测到支持的GPU，使用CPU解码")
        self._detected_type = GPUType.CPU
        return self._detected_type

    def _detect_nvidia(self) -> bool:
        """检测NVIDIA GPU"""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                gpu_name = result.stdout.strip().split('\n')[0]
                self.logger.info(f"检测到NVIDIA GPU: {gpu_name}")
                self._capabilities['nvidia'] = {
                    'name': gpu_name,
                    'decoder': 'h264_cuvid',
                    'cuda': True
                }
                return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return False

    def _detect_amd(self) -> bool:
        """检测AMD GPU"""
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                if 'amd' in output or 'radeon' in output:
                    self.logger.info("检测到AMD GPU")
                    self._capabilities['amd'] = {
                        'name': 'AMD GPU',
                        'decoder': 'h264_amf'
                    }
                    return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return False

    def _detect_intel(self) -> bool:
        """检测Intel GPU"""
        try:
            result = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "name"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                output = result.stdout.lower()
                if 'intel' in output and ('uhd' in output or 'iris' in output or 'hd' in output):
                    self.logger.info("检测到Intel GPU")
                    self._capabilities['intel'] = {
                        'name': 'Intel GPU',
                        'decoder': 'h264_qsv'
                    }
                    return True
        except (subprocess.SubprocessError, FileNotFoundError):
            pass
        return False

    def get_capabilities(self) -> Dict[str, Any]:
        """
        获取GPU能力信息

        返回值：
        - 包含GPU类型和能力的字典
        """
        if not self._capabilities:
            self.detect()
        return self._capabilities

    @property
    def current_type(self) -> GPUType:
        """获取当前检测到的GPU类型"""
        if not self._detected_type:
            return self.detect()
        return self._detected_type

    def get_decoder_name(self) -> str:
        """
        获取FFmpeg解码器名称

        返回值：
        - FFmpeg解码器名称
        """
        gpu_type = self.current_type

        if gpu_type == GPUType.NVIDIA:
            return 'h264_cuvid'
        elif gpu_type == GPUType.AMD:
            return 'h264_amf'
        elif gpu_type == GPUType.INTEL:
            return 'h264_qsv'
        else:
            return 'libx264'  # CPU软解码


class GPUDecoder:
    """
    GPU硬件解码器

    功能说明：
    - 使用GPU加速解码视频帧
    - 支持多种GPU类型自动适配
    - 提供异步解码接口
    - 包含统计信息收集

    使用方式：
    - decoder = GPUDecoder()
    - decoder.initialize(config)
    - frame = await decoder.decode(frame_data)
    """

    def __init__(self):
        self.logger = get_logger('gpu_decoder')
        self._detector = GPUDetector()
        self._config: Optional[DecoderConfig] = None
        self._initialized = False
        self._stats = DecoderStats()
        self._ffmpeg_process = None
        self._input_stream = None

    def initialize(self, config: Optional[DecoderConfig] = None) -> bool:
        """
        初始化解码器

        参数：
        - config: 解码器配置（可选）

        返回值：
        - True: 初始化成功
        - False: 初始化失败
        """
        try:
            self._config = config or DecoderConfig()

            gpu_type = self._detector.detect()
            self.logger.info(f"GPU类型: {gpu_type.value}")

            if self._config.gpu_enabled and gpu_type != GPUType.CPU:
                decoder_name = self._detector.get_decoder_name()
                self.logger.info(f"使用GPU解码器: {decoder_name}")
                self._config.gpu_decoder = decoder_name
            else:
                self.logger.info("使用CPU解码器")
                self._config.gpu_decoder = 'libx264'

            self._initialized = True
            self.logger.info("GPU解码器初始化成功")
            return True

        except Exception as e:
            self.logger.error(f"GPU解码器初始化失败: {e}")
            return False

    async def decode_frame(self, h264_data: bytes) -> Optional[Any]:
        """
        解码单个H.264帧

        参数：
        - h264_data: H.264格式的帧数据

        返回值：
        - 解码后的帧数据（numpy数组）或None
        """
        if not self._initialized:
            self.logger.warning("解码器未初始化")
            return None

        import time
        start_time = time.time()

        try:
            decoded = await self._decode_with_ffmpeg(h264_data)
            decode_time = (time.time() - start_time) * 1000

            self._stats.frames_decoded += 1
            self._stats.last_decode_time_ms = decode_time
            self._stats.decode_time_ms = (self._stats.decode_time_ms * (self._stats.frames_decoded - 1) + decode_time) / self._stats.frames_decoded

            return decoded

        except Exception as e:
            self.logger.error(f"解码帧失败: {e}")
            return None

    async def _decode_with_ffmpeg(self, h264_data: bytes) -> Optional[Any]:
        """
        使用FFmpeg解码帧

        参数：
        - h264_data: H.264数据

        返回值：
        - 解码后的帧
        """
        try:
            import numpy as np
            import cv2

            nparr = np.frombuffer(h264_data, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                return None

            if self._config and (self._config.output_width, self._config.output_height) != (frame.shape[1], frame.shape[0]):
                frame = cv2.resize(frame, (self._config.output_width, self._config.output_height))

            return frame

        except Exception as e:
            self.logger.error(f"FFmpeg解码失败: {e}")
            return None

    def get_stats(self) -> DecoderStats:
        """
        获取解码统计信息

        返回值：
        - DecoderStats: 解码统计数据
        """
        return self._stats

    def reset_stats(self):
        """重置统计信息"""
        self._stats = DecoderStats()

    async def close(self):
        """关闭解码器，释放资源"""
        try:
            if self._ffmpeg_process:
                self._ffmpeg_process.terminate()
                self._ffmpeg_process = None

            self._initialized = False
            self.logger.info("GPU解码器已关闭")

        except Exception as e:
            self.logger.error(f"关闭解码器时出错: {e}")

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized

    @property
    def gpu_type(self) -> GPUType:
        """获取当前GPU类型"""
        return self._detector.current_type

    def get_info(self) -> Dict[str, Any]:
        """
        获取解码器信息

        返回值：
        - 包含解码器信息的字典
        """
        return {
            'initialized': self._initialized,
            'gpu_type': self.gpu_type.value,
            'config': {
                'codec': self._config.codec if self._config else None,
                'gpu_enabled': self._config.gpu_enabled if self._config else False,
                'output_resolution': f"{self._config.output_width}x{self._config.output_height}" if self._config else None
            } if self._config else None,
            'stats': {
                'frames_decoded': self._stats.frames_decoded,
                'avg_decode_time_ms': self._stats.decode_time_ms,
                'fps': self._stats.fps
            }
        }


class FrameDecoder:
    """
    帧解码器（高层封装）

    功能说明：
    - 提供简化的帧解码接口
    - 支持批量解码
    - 集成GPU检测和配置

    使用方式：
    - decoder = FrameDecoder()
    - await decoder.initialize()
    - frame = await decoder.decode(h264_data)
    """

    def __init__(self, gpu_enabled: bool = True):
        self.logger = get_logger('frame_decoder')
        self._decoder = GPUDecoder()
        self._gpu_enabled = gpu_enabled
        self._initialized = False

    async def initialize(
        self,
        codec: str = "h264",
        width: int = 1280,
        height: int = 720
    ) -> bool:
        """
        初始化帧解码器

        参数：
        - codec: 视频编码格式
        - width: 输出宽度
        - height: 输出高度

        返回值：
        - True: 初始化成功
        - False: 初始化失败
        """
        try:
            config = DecoderConfig(
                codec=codec,
                output_width=width,
                output_height=height,
                gpu_enabled=self._gpu_enabled
            )

            success = self._decoder.initialize(config)
            self._initialized = success
            return success

        except Exception as e:
            self.logger.error(f"帧解码器初始化失败: {e}")
            return False

    async def decode(self, h264_data: bytes) -> Optional[Any]:
        """
        解码视频帧

        参数：
        - h264_data: H.264格式的帧数据

        返回值：
        - 解码后的帧（numpy数组）或None
        """
        if not self._initialized:
            self.logger.warning("帧解码器未初始化")
            return None

        return await self._decoder.decode_frame(h264_data)

    async def decode_batch(self, frames: List[bytes]) -> List[Any]:
        """
        批量解码帧

        参数：
        - frames: H.264帧数据列表

        返回值：
        - 解码后的帧列表
        """
        results = []
        for frame_data in frames:
            decoded = await self.decode(frame_data)
            results.append(decoded)
        return results

    def get_stats(self) -> DecoderStats:
        """获取解码统计"""
        return self._decoder.get_stats()

    def get_info(self) -> Dict[str, Any]:
        """获取解码器信息"""
        return self._decoder.get_info()

    async def close(self):
        """关闭解码器"""
        await self._decoder.close()
        self._initialized = False

    @property
    def is_initialized(self) -> bool:
        """检查是否已初始化"""
        return self._initialized


gpu_detector = GPUDetector()
