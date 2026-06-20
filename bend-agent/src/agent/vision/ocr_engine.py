"""
Step4 档案 OCR 引擎（PaddleOCR PP-OCRv6_tiny + ONNX Runtime）。

- 单行固定裁剪：TextRecognition（rec-only）
- 列表 / 邮箱等较大区域：PaddleOCR det+rec
"""

from __future__ import annotations

import os
import tempfile
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np

from ..core.config import config as agent_config
from ..core.logger import get_logger

_logger = get_logger("ocr_engine")

_INFER_LOCK = threading.Lock()
_TEMP_DIR = Path(tempfile.gettempdir()) / "bend_agent_ocr"
_TEMP_DIR.mkdir(parents=True, exist_ok=True)


def _ocr_cfg(key: str, default: Any) -> Any:
    return agent_config.get(f"ocr.{key}", default)


def _cpu_threads() -> int:
    configured = int(_ocr_cfg("cpu_threads", 0) or 0)
    if configured > 0:
        return configured
    try:
        import psutil

        return max(10, psutil.cpu_count(logical=True) or 4)
    except Exception:
        return 10


def _to_bgr(image: np.ndarray) -> np.ndarray:
    if image is None or image.size == 0:
        return image
    if image.ndim == 2:
        return cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    return image


def crop_mean_brightness(crop: np.ndarray) -> float:
    """裁剪区灰度均值；过低表示裁到空白/错场景。"""
    if crop is None or crop.size == 0:
        return 0.0
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    return float(gray.mean())


def _min_brightness() -> float:
    return float(_ocr_cfg("min_crop_brightness", 25.0))


def _enhance_for_rec(crop: np.ndarray) -> np.ndarray:
    """串流小字：轻度 CLAHE + 放大，供 rec 失败时二次尝试。"""
    bgr = _to_bgr(crop)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape[:2]
    if max(h, w) < 140:
        gray = cv2.resize(gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2BGR)


def _parse_rec_item(res: Any) -> Tuple[str, float]:
    if res is None:
        return "", 0.0
    if isinstance(res, dict):
        texts = res.get("rec_texts") or []
        scores = res.get("rec_scores") or []
        if texts:
            text = str(texts[0] if isinstance(texts, list) else texts).strip()
            conf = float(scores[0]) if scores else 0.0
            return text, conf
        text = str(res.get("rec_text") or res.get("text") or "").strip()
        conf = float(res.get("rec_score") or res.get("score") or 0.0)
        return text, conf
    text = ""
    conf = 0.0
    for attr in ("rec_text", "text"):
        if hasattr(res, attr):
            val = getattr(res, attr)
            if val:
                text = str(val[0] if isinstance(val, list) else val).strip()
                break
    for attr in ("rec_score", "score", "confidence"):
        if hasattr(res, attr):
            val = getattr(res, attr)
            if val is not None:
                conf = float(val[0] if isinstance(val, list) else val)
                break
    return text, conf


def _parse_det_rec_result(result: Any) -> Tuple[List[str], float]:
    if not result:
        return [], 0.0
    item = result[0] if isinstance(result, list) else result
    if not isinstance(item, dict):
        return [], 0.0
    texts = [str(t).strip() for t in (item.get("rec_texts") or []) if str(t).strip()]
    scores = item.get("rec_scores") or []
    conf = float(sum(scores) / len(scores)) if scores else 0.0
    return texts, conf


@lru_cache(maxsize=1)
def _get_rec_engine():
    from paddleocr import TextRecognition

    rec_model = str(_ocr_cfg("rec_model", "PP-OCRv6_tiny_rec"))
    engine = str(_ocr_cfg("engine", "onnxruntime"))
    _logger.info(
        "初始化 PaddleOCR TextRecognition (%s, %s, cpu_threads=%s)...",
        rec_model,
        engine,
        _cpu_threads(),
    )
    model = TextRecognition(
        device="cpu",
        model_name=rec_model,
        engine=engine,
        cpu_threads=_cpu_threads(),
    )
    _logger.info("PaddleOCR TextRecognition 就绪")
    return model


@lru_cache(maxsize=1)
def _get_det_rec_engine():
    from paddleocr import PaddleOCR

    det_model = str(_ocr_cfg("det_model", "PP-OCRv6_tiny_det"))
    rec_model = str(_ocr_cfg("rec_model", "PP-OCRv6_tiny_rec"))
    engine = str(_ocr_cfg("engine", "onnxruntime"))
    enable_mkldnn = bool(_ocr_cfg("enable_mkldnn", True))
    _logger.info(
        "初始化 PaddleOCR det+rec (%s + %s, %s)...",
        det_model,
        rec_model,
        engine,
    )
    model = PaddleOCR(
        text_detection_model_name=det_model,
        text_recognition_model_name=rec_model,
        use_doc_orientation_classify=False,
        use_doc_unwarping=False,
        use_textline_orientation=False,
        enable_mkldnn=enable_mkldnn,
        engine=engine,
    )
    _logger.info("PaddleOCR det+rec 就绪")
    return model


def _write_temp_png(bgr: np.ndarray) -> str:
    fd, path = tempfile.mkstemp(suffix=".png", dir=str(_TEMP_DIR))
    os.close(fd)
    cv2.imwrite(path, bgr)
    return path


def recognize_line(crop: np.ndarray, *, skip_dark: bool = True) -> Tuple[str, float]:
    """
    单行文本识别（rec-only；失败时用 CLAHE 增强图再试一次）。
    """
    if crop is None or crop.size == 0:
        return "", 0.0
    if skip_dark and crop_mean_brightness(crop) < _min_brightness():
        _logger.debug(
            "OCR rec 跳过：裁剪区过暗 (mean=%.1f)",
            crop_mean_brightness(crop),
        )
        return "", 0.0

    rec = _get_rec_engine()
    best_text, best_conf = "", 0.0
    candidates = [_to_bgr(crop), _enhance_for_rec(crop)]

    try:
        with _INFER_LOCK:
            for img in candidates:
                try:
                    batch = rec.predict(input=[img], batch_size=1)
                except Exception as exc:
                    _logger.debug("Paddle rec predict failed: %s", exc)
                    continue
                if not batch:
                    continue
                text, conf = _parse_rec_item(batch[0])
                if text and conf >= best_conf:
                    best_text, best_conf = text, conf
                if best_text and best_conf >= 0.5:
                    break
    except Exception as exc:
        _logger.warning("PaddleOCR rec 失败: %s", exc)
        return "", 0.0

    min_conf = float(_ocr_cfg("min_rec_confidence", 0.12))
    if best_text and best_conf < min_conf:
        _logger.debug("OCR rec 低置信度 %.2f: %r", best_conf, best_text)
    return best_text, best_conf


def recognize_region(crop: np.ndarray, *, skip_dark: bool = True) -> Tuple[str, float]:
    """
    区域 det+rec：返回空格拼接的全文（适合邮箱 / 合并区）。
    """
    lines, conf = recognize_region_lines(crop, skip_dark=skip_dark)
    return " ".join(lines).strip(), conf


def recognize_region_lines(
    crop: np.ndarray,
    *,
    skip_dark: bool = True,
    min_line_confidence: Optional[float] = None,
) -> Tuple[List[str], float]:
    """区域 det+rec：返回各行文本列表。"""
    if crop is None or crop.size == 0:
        return [], 0.0
    if skip_dark and crop_mean_brightness(crop) < _min_brightness():
        _logger.debug(
            "OCR det+rec 跳过：裁剪区过暗 (mean=%.1f)",
            crop_mean_brightness(crop),
        )
        return [], 0.0

    bgr = _to_bgr(crop)
    tmp_path = _write_temp_png(bgr)
    line_conf = (
        float(min_line_confidence)
        if min_line_confidence is not None
        else float(_ocr_cfg("min_line_confidence", 0.12))
    )
    try:
        with _INFER_LOCK:
            result = _get_det_rec_engine().predict(tmp_path)
        texts, avg_conf = _parse_det_rec_result(result)
        lines: List[str] = []
        if isinstance(result, list) and result and isinstance(result[0], dict):
            item = result[0]
            for text, score in zip(item.get("rec_texts") or [], item.get("rec_scores") or []):
                t = str(text).strip()
                if t and float(score) >= line_conf and t not in lines:
                    lines.append(t)
        if not lines:
            lines = [t for t in texts if t]
        return lines, avg_conf
    except Exception as exc:
        _logger.warning("PaddleOCR det+rec 失败: %s", exc)
        return [], 0.0
    finally:
        try:
            os.remove(tmp_path)
        except OSError:
            pass
