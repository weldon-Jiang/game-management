"""
从场景 6 账号选择帧读取 Xbox 档案 Gamertag。

在左侧档案列表焦点行使用 EasyOCR（960×540 坐标）。
"""

from __future__ import annotations

import re
from functools import lru_cache
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np

from ..core.logger import get_logger

# 场景 6 档案列表在归一化 960×540 串流帧上的区域
SCENE6_LIST_LEFT = 78
SCENE6_LIST_TOP = 95
SCENE6_LIST_RIGHT = 320
SCENE6_LIST_BOTTOM = 500
SCENE6_ROW_HEIGHT = 42
SCENE6_TEXT_LEFT = 118
SCENE6_TEXT_RIGHT = 300

_logger = get_logger("profile_name_reader")


@lru_cache(maxsize=1)
def _get_ocr_reader():
    import easyocr

    return easyocr.Reader(["en"], gpu=False, verbose=False)


def normalize_gamertag(name: str) -> str:
    """用于模糊 Gamertag 比对的小写字母数字键。"""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def gamertag_matches(detected: Optional[str], target: str) -> bool:
    """OCR 文本很可能匹配目标 Gamertag 时返回 True。"""
    if not detected or not target:
        return False
    det = normalize_gamertag(detected)
    tgt = normalize_gamertag(target)
    if not det or not tgt:
        return False
    return det == tgt or tgt in det or det in tgt


def _green_ratio(hsv_crop: np.ndarray) -> float:
    mask = cv2.inRange(hsv_crop, (35, 80, 80), (85, 255, 255))
    return float(mask.mean()) / 255.0


def detect_focused_row_y(image: np.ndarray) -> Optional[int]:
    """
    检测场景 6 档案列表中绿色焦点条的 Y 轴中心。
    """
    h, w = image.shape[:2]
    scale_x = w / 960.0
    scale_y = h / 540.0

    left = int(SCENE6_LIST_LEFT * scale_x)
    right = int(SCENE6_LIST_RIGHT * scale_x)
    top = int(SCENE6_LIST_TOP * scale_y)
    bottom = int(SCENE6_LIST_BOTTOM * scale_y)
    row_h = max(8, int(SCENE6_ROW_HEIGHT * scale_y))

    crop = image[top:bottom, left:right]
    if crop.size == 0:
        return None

    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    bar_width = max(4, int(8 * scale_x))

    best_y: Optional[int] = None
    best_ratio = 0.04
    for y in range(0, crop.shape[0] - row_h, max(4, row_h // 3)):
        band = hsv[y : y + row_h, :bar_width]
        ratio = _green_ratio(band)
        if ratio > best_ratio:
            best_ratio = ratio
            best_y = top + y + row_h // 2

    return best_y


def _crop_focused_text(image: np.ndarray, row_y: Optional[int]) -> Optional[np.ndarray]:
    h, w = image.shape[:2]
    scale_x = w / 960.0
    scale_y = h / 540.0

    text_left = int(SCENE6_TEXT_LEFT * scale_x)
    text_right = min(w, int(SCENE6_TEXT_RIGHT * scale_x))
    row_h = max(12, int(SCENE6_ROW_HEIGHT * scale_y))

    if row_y is None:
        row_y = int(130 * scale_y)

    y1 = max(0, row_y - row_h // 2)
    y2 = min(h, row_y + row_h // 2)
    if y2 <= y1 or text_right <= text_left:
        return None

    return image[y1:y2, text_left:text_right]


def _ocr_text(crop: np.ndarray) -> str:
    if crop is None or crop.size == 0:
        return ""

    try:
        reader = _get_ocr_reader()
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        results = reader.readtext(gray, detail=0, paragraph=True)
        if not results:
            return ""
        return " ".join(str(line) for line in results).strip()
    except Exception as exc:
        _logger.warning("Profile OCR failed: %s", exc)
        return ""


def read_focused_gamertag(image: Any) -> str:
    """对当前焦点档案行 OCR Gamertag。"""
    if image is None:
        return ""
    if hasattr(image, "data"):
        image = image.data
    if not isinstance(image, np.ndarray):
        return ""

    row_y = detect_focused_row_y(image)
    crop = _crop_focused_text(image, row_y)
    return _ocr_text(crop)


def read_list_gamertags(image: Any) -> List[str]:
    """OCR 左侧列表全部可见 Gamertag（兜底）。"""
    if image is None:
        return []
    if hasattr(image, "data"):
        image = image.data
    if not isinstance(image, np.ndarray):
        return []

    h, w = image.shape[:2]
    scale_x = w / 960.0
    scale_y = h / 540.0
    left = int(SCENE6_LIST_LEFT * scale_x)
    right = int(SCENE6_LIST_RIGHT * scale_x)
    top = int(SCENE6_LIST_TOP * scale_y)
    bottom = int(SCENE6_LIST_BOTTOM * scale_y)
    crop = image[top:bottom, left:right]
    if crop.size == 0:
        return []

    try:
        reader = _get_ocr_reader()
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        results = reader.readtext(gray, detail=0, paragraph=False)
        return [str(line).strip() for line in results if str(line).strip()]
    except Exception as exc:
        _logger.warning("Profile list OCR failed: %s", exc)
        return []
