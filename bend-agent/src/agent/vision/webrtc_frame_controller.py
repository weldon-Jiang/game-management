"""
WebRTC 视频帧控制器
==================

从 CloudStreamSession 的 WebRTC video track 提供帧给 VideoFrameCapture。
"""

import asyncio
import threading
import time
from typing import Any, Optional

import numpy as np

from ..core.logger import get_logger


class WebRTCFrameController:
    """CloudStreamSession 与 VideoFrameCapture 之间的帧桥接；重连后通过 update_session 切换数据源。"""

    def __init__(self, cloud_session: Any):
        self.logger = get_logger("webrtc_frame_controller")
        self._session = cloud_session
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._fps = 0.0
        self._fps_count = 0
        self._fps_start = time.time()

    def update_session(self, cloud_session: Any) -> None:
        """重连后将帧桥接指向新的 CloudStreamSession。"""
        self._session = cloud_session
        self._latest_frame = None
        self.logger.info("WebRTC frame controller session updated")

    async def get_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        """从 CloudStreamSession 拉取最新 BGR 帧并更新 fps 统计（场景检测/模板匹配入口）。"""
        if not self._session:
            return None

        frame = await self._session.get_frame(timeout=timeout)
        if frame is not None:
            with self._frame_lock:
                self._latest_frame = frame
            self._update_fps()
        return frame

    def _update_fps(self) -> None:
        self._fps_count += 1
        elapsed = time.time() - self._fps_start
        if elapsed >= 1.0:
            self._fps = self._fps_count / elapsed
            self._fps_count = 0
            self._fps_start = time.time()

    @property
    def fps(self) -> float:
        return self._fps
