"""
视频帧 → BGR uint8 ndarray 统一转换。

常见陷阱：对 np.ndarray 使用 `.data` 会得到 memoryview，而非图像数组本身。
"""

from __future__ import annotations

from typing import Any, Optional

import numpy as np


def frame_to_bgr_ndarray(
    frame: Any,
    *,
    width: Optional[int] = None,
    height: Optional[int] = None,
) -> Optional[np.ndarray]:
    """
    从 Frame 对象、ndarray 或 buffer 提取可用的 BGR/RGB uint8 图像。

    参数 width/height 仅在 frame 为裸 buffer/memoryview 时使用。
    """
    if frame is None:
        return None

    if isinstance(frame, np.ndarray):
        return _coerce_ndarray(frame)

    if hasattr(frame, "data") and not isinstance(frame, np.ndarray):
        inner = getattr(frame, "data")
        w = width or getattr(frame, "width", None) or 0
        h = height or getattr(frame, "height", None) or 0
        if isinstance(inner, np.ndarray):
            return _coerce_ndarray(inner)
        buf = _coerce_buffer(inner, width=int(w), height=int(h))
        if buf is not None:
            return buf

    w = width or getattr(frame, "width", None) or 0
    h = height or getattr(frame, "height", None) or 0
    return _coerce_buffer(frame, width=int(w), height=int(h))


def _coerce_ndarray(arr: np.ndarray) -> Optional[np.ndarray]:
    if arr.size == 0:
        return None
    if arr.dtype != np.uint8:
        if arr.max() <= 1.0:
            arr = (arr * 255.0).clip(0, 255).astype(np.uint8)
        else:
            arr = arr.clip(0, 255).astype(np.uint8)
    return np.ascontiguousarray(arr)


def _coerce_buffer(raw: Any, *, width: int, height: int) -> Optional[np.ndarray]:
    if isinstance(raw, np.ndarray):
        return _coerce_ndarray(raw)
    if isinstance(raw, memoryview):
        if width <= 0 or height <= 0:
            return None
        channels = 3
        need = width * height * channels
        if raw.nbytes < need:
            return None
        arr = np.frombuffer(raw, dtype=np.uint8, count=need)
        try:
            return _coerce_ndarray(arr.reshape((height, width, channels)))
        except ValueError:
            return None
    if isinstance(raw, (bytes, bytearray)):
        mv = memoryview(raw)
        return _coerce_buffer(mv, width=width, height=height)
    return None
