"""
自动化调试追踪：按顺序保存场景截图 + 打印手柄输入。

输出目录（相对 bend-agent 根）：logs/scene_capture/{task_id}/
- 000_entry_initial.png  进入 Step4 首帧（固定 ASCII 文件名）
- 001_scene203_*.png     后续场景按序号
- index.txt              场景截图索引
- input_trace.log        手柄按键流水
- entry_survey.json      首帧各模板场景置信度
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any, Dict, Optional

import cv2
import numpy as np

from ..core.config import config
from ..core.logger import get_logger
from ..core.paths import get_logs_dir_fallback

_logger = get_logger("automation_trace")

_sessions: Dict[str, "SceneCaptureSession"] = {}


def scene_capture_enabled() -> bool:
    return bool(config.get("debug.scene_capture_enabled", True))


def input_trace_enabled() -> bool:
    return bool(config.get("debug.input_trace_enabled", True))


def _ascii_slug(text: str, max_len: int = 32) -> str:
    """文件名仅保留 ASCII，避免 Windows 下 cv2.imwrite 因中文路径失败。"""
    slug = re.sub(r"[^0-9A-Za-z_-]+", "_", (text or "").strip())
    slug = slug.strip("_") or "unknown"
    return slug[:max_len]


def _normalize_bgr_frame(image: np.ndarray) -> np.ndarray:
    """统一为 960×540 BGR uint8，供 OpenCV 写 PNG。"""
    frame = np.ascontiguousarray(image)
    if frame.dtype != np.uint8:
        if frame.max() <= 1.0:
            frame = (frame * 255.0).clip(0, 255).astype(np.uint8)
        else:
            frame = frame.clip(0, 255).astype(np.uint8)
    if frame.ndim == 2:
        frame = cv2.cvtColor(frame, cv2.COLOR_GRAY2BGR)
    elif frame.shape[2] == 4:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
    elif frame.shape[2] == 3:
        # 串流帧多为 RGB，OpenCV 写盘用 BGR
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
    if frame.shape[1] != 960 or frame.shape[0] != 540:
        frame = cv2.resize(frame, (960, 540), interpolation=cv2.INTER_AREA)
    return frame


def _write_png(path: str, frame: np.ndarray) -> bool:
    """写 PNG；imwrite 失败时用 imencode + 二进制写入兜底。"""
    ok = cv2.imwrite(path, frame)
    if ok:
        return True
    try:
        success, encoded = cv2.imencode(".png", frame)
        if success:
            encoded.tofile(path)
            return os.path.isfile(path) and os.path.getsize(path) > 0
    except Exception as exc:
        _logger.warning("场景截图 imencode 失败: %s (%s)", path, exc)
    return False


class SceneCaptureSession:
    """单任务场景截图会话（按序号命名）。"""

    def __init__(self, task_id: str):
        self.task_id = task_id or "no_task"
        self.seq = 0
        self.base_dir = os.path.join(
            get_logs_dir_fallback(), "scene_capture", self.task_id
        )
        os.makedirs(self.base_dir, exist_ok=True)
        self.index_path = os.path.join(self.base_dir, "index.txt")
        self.input_path = os.path.join(self.base_dir, "input_trace.log")
        self._last_capture_at: Dict[int, float] = {}

    def _append_index(self, line: str) -> None:
        with open(self.index_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _append_input(self, line: str) -> None:
        with open(self.input_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def capture_frame(
        self,
        image: Any,
        *,
        scene_id: int,
        scene_label: str = "",
        confidence: Optional[float] = None,
        note: str = "",
        min_interval_sec: float = 2.5,
        fixed_filename: Optional[str] = None,
    ) -> Optional[str]:
        """保存一帧截图；同场景短时间去重。"""
        if not scene_capture_enabled():
            return None
        if image is None:
            _logger.warning("[场景截图] 跳过：image 为空 scene=%s", scene_id)
            return None

        now = time.time()
        last = self._last_capture_at.get(scene_id, 0.0)
        if scene_id > 0 and now - last < min_interval_sec:
            return None
        self._last_capture_at[scene_id] = now

        if hasattr(image, "data"):
            image = image.data
        if not isinstance(image, np.ndarray) or image.size == 0:
            _logger.warning(
                "[场景截图] 跳过：无效 ndarray scene=%s type=%s",
                scene_id,
                type(image).__name__,
            )
            return None

        try:
            frame = _normalize_bgr_frame(image)
        except Exception as exc:
            _logger.warning("[场景截图] 帧归一化失败 scene=%s: %s", scene_id, exc)
            return None

        if fixed_filename:
            filename = fixed_filename
        else:
            self.seq += 1
            label = _ascii_slug(scene_label or f"scene{scene_id}")
            conf_part = f"_conf{confidence:.2f}" if confidence is not None else ""
            note_part = f"_{_ascii_slug(note, 16)}" if note else ""
            filename = f"{self.seq:03d}_scene{scene_id}_{label}{conf_part}{note_part}.png"

        path = os.path.join(self.base_dir, filename)
        if not _write_png(path, frame):
            _logger.warning("[场景截图] 写入失败: %s", os.path.abspath(path))
            return None

        abs_path = os.path.abspath(path)
        index_line = (
            f"{filename}\tscene={scene_id}\tlabel={scene_label}\t"
            f"conf={confidence if confidence is not None else ''}\t"
            f"note={note}\tfile={filename}"
        )
        self._append_index(index_line)
        _logger.debug("[场景截图] %s -> %s", index_line, abs_path)
        return abs_path

    def log_input(
        self,
        button: str,
        *,
        duration: float = 0.0,
        source: str = "",
        raw_buttons: Optional[int] = None,
    ) -> None:
        if not input_trace_enabled():
            return
        parts = [f"[手柄输入] button={button}", f"duration={duration:.3f}s"]
        if source:
            parts.append(f"source={source}")
        if raw_buttons is not None:
            parts.append(f"raw=0x{int(raw_buttons):X}")
        msg = " ".join(parts)
        stamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self._append_input(f"{stamp}\t{msg}")


def get_scene_capture_session(task_id: Optional[str]) -> SceneCaptureSession:
    key = task_id or "no_task"
    session = _sessions.get(key)
    if session is None:
        session = SceneCaptureSession(key)
        _sessions[key] = session
    return session


def reset_scene_capture_session(task_id: Optional[str]) -> None:
    key = task_id or "no_task"
    _sessions.pop(key, None)


def log_gamepad_input(
    button: str,
    *,
    duration: float = 0.0,
    source: str = "",
    raw_buttons: Optional[int] = None,
    task_id: Optional[str] = None,
) -> None:
    if not input_trace_enabled():
        return
    session = get_scene_capture_session(task_id)
    session.log_input(
        button,
        duration=duration,
        source=source,
        raw_buttons=raw_buttons,
    )


async def capture_entry_scene_survey(
    *,
    task_id: Optional[str],
    frame_getter,
    scene_detector,
    scene_ids: list,
) -> None:
    """
    Step4/切换开始前：保存进入 Xbox 后的首帧，并扫描模板场景置信度。
    """
    if not scene_capture_enabled() or not frame_getter or not scene_detector:
        return

    session = get_scene_capture_session(task_id)
    frame = await frame_getter()
    if frame is None:
        _logger.warning("[场景截图] entry 截帧为空，跳过 entry_survey")
        return

    image = frame.data if hasattr(frame, "data") else frame
    entry_path = session.capture_frame(
        image,
        scene_id=0,
        scene_label="entry_initial",
        note="entry",
        min_interval_sec=0.0,
        fixed_filename="000_entry_initial.png",
    )
    if not entry_path:
        _logger.warning("[场景截图] entry 首帧保存失败，请检查 logs/scene_capture 目录权限")

    survey: Dict[str, Any] = {
        "task_id": task_id,
        "captured_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "entry_image": entry_path or "",
        "scenes": {},
    }
    try:
        from configs.scene_schemas import SCENE_NAMES
    except ImportError:
        SCENE_NAMES = {}

    for scene_id in scene_ids:
        try:
            result = scene_detector.recognize_scene(image, scene_id=int(scene_id))
            survey["scenes"][str(scene_id)] = {
                "name": SCENE_NAMES.get(int(scene_id), f"scene{scene_id}"),
                "matched": bool(getattr(result, "matched", False)),
                "confidence": float(getattr(result, "confidence", 0.0) or 0.0),
            }
        except Exception as exc:
            survey["scenes"][str(scene_id)] = {"error": str(exc)}

    survey_path = os.path.join(session.base_dir, "entry_survey.json")
    with open(survey_path, "w", encoding="utf-8") as fh:
        json.dump(survey, fh, ensure_ascii=False, indent=2)

    ranked = sorted(
        survey["scenes"].items(),
        key=lambda item: float(item[1].get("confidence", 0.0) if isinstance(item[1], dict) else 0.0),
        reverse=True,
    )
    top = ", ".join(
        f"{sid}={info.get('confidence', 0):.3f}"
        for sid, info in ranked[:8]
        if isinstance(info, dict) and "confidence" in info
    )
    _logger.info(
        "[场景探测] entry_survey 已保存 %s | entry_png=%s | Top: %s",
        survey_path,
        entry_path or "(missing)",
        top,
    )
