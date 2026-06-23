"""
人工调试截图：F9 快捷键保存 960×540 整帧到 logs/manual_capture/{task_id}/。

供模板坐标测量与小 PNG 裁剪使用。
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Optional, Tuple

import cv2
import numpy as np

from ..core.logger import get_logger
from ..core.paths import get_logs_dir_fallback

_logger = get_logger("manual_capture")

NORM_W, NORM_H = 960, 540


def _normalize_bgr(image: np.ndarray) -> np.ndarray:
    frame = np.ascontiguousarray(image)
    if frame.dtype != np.uint8:
        frame = frame.clip(0, 255).astype(np.uint8)
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    elif frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    elif frame.shape[2] == 3:
        # 串流帧多为 RGB
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    if frame.shape[1] != NORM_W or frame.shape[0] != NORM_H:
        frame = cv2.resize(frame, (NORM_W, NORM_H), interpolation=cv2.INTER_AREA)
    return frame


def _resolve_task_id(context: Any) -> str:
    task_id = getattr(context, "task_id", None) or getattr(context, "taskId", None)
    return str(task_id or "no_task")


def _grab_frame(context: Any) -> Optional[np.ndarray]:
    runtime = getattr(context, "_stream_runtime", None)
    if runtime is not None:
        img = runtime.get_latest_image()
        if img is not None and getattr(img, "size", 0) > 0:
            return img

    sdl = getattr(context, "sdl_window", None)
    if sdl is not None:
        if hasattr(sdl, "get_game_mat"):
            mat = sdl.get_game_mat()
            if mat is not None and mat.size > 0:
                return mat
        inner = getattr(sdl, "_window", None)
        if inner is not None and hasattr(inner, "get_game_mat"):
            mat = inner.get_game_mat()
            if mat is not None and mat.size > 0:
                return mat

    capture = getattr(context, "frame_capture", None)
    if capture is not None and hasattr(capture, "get_latest_frame"):
        frame = capture.get_latest_frame()
        if frame is not None:
            data = getattr(frame, "data", frame)
            if isinstance(data, np.ndarray) and data.size > 0:
                return data

    return None


def save_manual_capture(
    context: Any,
    *,
    note: str = "manual",
) -> Tuple[Optional[str], str]:
    """
    保存当前串流帧为 960×540 PNG。

    返回 (绝对路径, 用户可读说明)；失败时 path 为 None。
    """
    raw = _grab_frame(context)
    if raw is None:
        msg = "截图失败：无可用帧（串流是否就绪？）"
        _logger.warning("[人工截图] %s", msg)
        return None, msg

    try:
        frame = _normalize_bgr(raw)
    except Exception as exc:
        msg = f"截图失败：帧归一化异常 {exc}"
        _logger.warning("[人工截图] %s", msg)
        return None, msg

    task_id = _resolve_task_id(context)
    base_dir = os.path.join(get_logs_dir_fallback(), "manual_capture", task_id)
    os.makedirs(base_dir, exist_ok=True)

    seq = getattr(context, "_manual_capture_seq", 0) + 1
    context._manual_capture_seq = seq
    safe_note = "".join(c if c.isalnum() or c in "-_" else "_" for c in (note or "manual"))[:24]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{seq:03d}_{safe_note}_{timestamp}.png"
    path = os.path.join(base_dir, filename)

    if not cv2.imwrite(path, frame):
        try:
            ok, encoded = cv2.imencode(".png", frame)
            if ok:
                encoded.tofile(path)
        except Exception:
            pass

    if not os.path.isfile(path):
        msg = "截图失败：写入 PNG 失败"
        _logger.warning("[人工截图] %s", msg)
        return None, msg

    abs_path = os.path.abspath(path)
    index_path = os.path.join(base_dir, "index.txt")
    with open(index_path, "a", encoding="utf-8") as fh:
        fh.write(
            f"{filename}\t960x540\tnote={note}\tpath={abs_path}\n"
        )

    msg = (
        f"截图已保存: {abs_path}\n"
        f"  目录: {base_dir}\n"
        f"  尺寸: 960×540（可直接量 template/search 坐标）"
    )
    _logger.info("[人工截图] %s", msg.replace("\n", " | "))
    return abs_path, msg
