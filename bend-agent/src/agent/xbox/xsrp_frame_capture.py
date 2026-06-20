"""xsrp 栈画面捕获：对齐 streaming WorkerCapture + CaptureStreaming 轮询语义。"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

import numpy as np

from ..core.config import config
from ..core.logger import get_logger
from ..vision.frame_capture import Frame
from ..vision.frame_utils import frame_to_bgr_ndarray


class XsrpFrameCapture:
    """
    从 WebRTC direct 控制器拉取 BGR 帧，供 Step3/Step4 场景识别使用。

    等价于 xsrp.CaptureStreaming(username) 的 Python 实现（无 FFmpeg DLL）。
    """

    def __init__(self, direct_capture: Any, *, capture_fps: Optional[float] = None):
        self.logger = get_logger("xsrp_frame_capture")
        self._direct = direct_capture
        self._capture_fps = capture_fps or float(
            config.get("gssv.xsrp_capture_fps", config.get("window.display_fps_max", 30))
        )
        self._min_interval = 1.0 / max(1.0, self._capture_fps)
        self._last_capture_ts = 0.0
        self._frame_counter = 0

    async def capture_frame(self) -> Optional[Frame]:
        now = time.monotonic()
        if now - self._last_capture_ts < self._min_interval:
            await self._sleep_short(self._min_interval - (now - self._last_capture_ts))

        raw = await self._direct.get_frame(timeout=1.0)
        if raw is None:
            return None
        img = frame_to_bgr_ndarray(raw)
        if img is None or img.size == 0:
            return None

        h, w = img.shape[:2]
        self._frame_counter += 1
        self._last_capture_ts = time.monotonic()
        return Frame(
            data=img,
            frame_id=f"xsrp-{self._frame_counter}-{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            width=w,
            height=h,
            fps=self._capture_fps,
        )

    async def close(self) -> None:
        return

    @staticmethod
    async def _sleep_short(seconds: float) -> None:
        import asyncio

        if seconds > 0:
            await asyncio.sleep(seconds)
