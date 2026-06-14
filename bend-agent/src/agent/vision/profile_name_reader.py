"""
从场景 6 账号选择帧 / Xbox 主页读取档案标识并比对。

- 场景 6：左侧档案列表焦点行 EasyOCR（960×540 坐标）
- 场景 203：主页左上角显示名 + 邮箱两行 OCR
"""

from __future__ import annotations

import re
from dataclasses import dataclass
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


@dataclass(frozen=True)
class HomeProfileIdentity:
    """Xbox 主页左上角 OCR 结果（显示名 + 邮箱）。"""

    display_name: str
    email_text: str

    @property
    def combined(self) -> str:
        parts = [self.display_name.strip(), self.email_text.strip()]
        return " ".join(part for part in parts if part)


@lru_cache(maxsize=1)
def _get_ocr_reader():
    import easyocr

    _logger.info("初始化 EasyOCR Reader (en, CPU)...")
    reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    _logger.info("EasyOCR Reader 就绪")
    return reader


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


def email_local_part(email: Optional[str]) -> str:
    """邮箱 @ 前本地段，用于与主页 OCR 文本比对。"""
    if not email or "@" not in email:
        return (email or "").strip()
    return email.split("@", 1)[0].strip()


def profile_matches_game_account(
    detected_name: Optional[str],
    gamertag: str,
    email: Optional[str] = None,
    *,
    detected_email: Optional[str] = None,
    host_display_name: Optional[str] = None,
    combined_text: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    主页 / 列表 OCR 文本是否与目标游戏账号一致。

    依次尝试：平台 gamertag、主机显示名 host_display_name、邮箱本地段、完整邮箱。
    返回 (是否匹配, 匹配依据说明)。
    """
    ocr_texts = [
        text.strip()
        for text in (detected_name, detected_email, combined_text)
        if text and str(text).strip()
    ]
    if not ocr_texts:
        return False, ""

    targets: List[Tuple[str, str]] = []
    if gamertag:
        targets.append(("gamertag", gamertag))
    if host_display_name:
        targets.append(("host_display_name", host_display_name))
    local = email_local_part(email)
    if local:
        targets.append(("email_local", local))
    if email and "@" in email:
        targets.append(("email", email.strip()))

    for text in ocr_texts:
        for reason, target in targets:
            if gamertag_matches(text, target):
                return True, reason
    return False, ""


def account_identity_matches(
    detected: Optional[str],
    *,
    gamertag: str,
    email: Optional[str] = None,
    host_display_name: Optional[str] = None,
) -> bool:
    """场景 6 单行 OCR 是否与目标账号任一标识匹配。"""
    matched, _ = profile_matches_game_account(
        detected,
        gamertag,
        email,
        host_display_name=host_display_name,
    )
    return matched


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


def _prepare_ocr_variants(crop: np.ndarray) -> List[np.ndarray]:
    """
    串流小字 OCR 预处理：放大 + CLAHE + Otsu 二值化，提升白字 UI 识别率。
    """
    if crop.ndim == 3:
        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
    else:
        gray = crop.copy()

    h, w = gray.shape[:2]
    if h < 4 or w < 4:
        return []

    scale = 3.0 if max(h, w) < 80 else (2.0 if max(h, w) < 140 else 1.0)
    if scale > 1.0:
        base = cv2.resize(
            gray,
            None,
            fx=scale,
            fy=scale,
            interpolation=cv2.INTER_CUBIC,
        )
    else:
        base = gray

    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(base)
    _, otsu = cv2.threshold(enhanced, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    variants: List[np.ndarray] = [enhanced, otsu, base]
    if scale > 1.0:
        variants.append(gray)
    return variants


def _ocr_read_best(reader: Any, crop: np.ndarray, *, paragraph: bool = True) -> str:
    """对多种预处理图跑 EasyOCR，取置信度最高的非空文本。"""
    best_text = ""
    best_conf = 0.0
    for variant in _prepare_ocr_variants(crop):
        try:
            results = reader.readtext(variant, detail=1, paragraph=paragraph)
        except Exception:
            continue
        for item in results:
            if len(item) < 3:
                continue
            text = str(item[1]).strip()
            conf = float(item[2])
            if text and conf >= best_conf:
                best_conf = conf
                best_text = text
    if best_text and best_conf >= 0.15:
        return best_text
    if best_text:
        _logger.debug("Profile OCR low confidence %.2f: %r", best_conf, best_text)
        return best_text
    return ""


def _ocr_text(crop: np.ndarray) -> str:
    if crop is None or crop.size == 0:
        return ""

    try:
        reader = _get_ocr_reader()
        text = _ocr_read_best(reader, crop, paragraph=True)
        if text:
            return text
        return _ocr_read_best(reader, crop, paragraph=False)
    except Exception as exc:
        _logger.warning("Profile OCR failed: %s", exc)
        return ""


def _scale_region(
    image: np.ndarray,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> Tuple[int, int, int, int]:
    h, w = image.shape[:2]
    scale_x = w / 960.0
    scale_y = h / 540.0
    x1 = int(left * scale_x)
    x2 = min(w, int(right * scale_x))
    y1 = int(top * scale_y)
    y2 = min(h, int(bottom * scale_y))
    return x1, y1, x2, y2


def _crop_region(image: np.ndarray, left: int, top: int, right: int, bottom: int) -> np.ndarray:
    x1, y1, x2, y2 = _scale_region(image, left, top, right, bottom)
    if x2 <= x1 or y2 <= y1:
        return np.empty((0, 0, 3), dtype=image.dtype)
    return image[y1:y2, x1:x2]


# 场景 203 Xbox 主页左上角（960×540）：显示名 + 邮箱分两行（略放大裁剪区）
HOME203_NAME_LEFT = 32
HOME203_NAME_TOP = 14
HOME203_NAME_RIGHT = 280
HOME203_NAME_BOTTOM = 52
HOME203_EMAIL_LEFT = 32
HOME203_EMAIL_TOP = 44
HOME203_EMAIL_RIGHT = 400
HOME203_EMAIL_BOTTOM = 82
# 兼容旧逻辑的单行区域
HOME203_PROFILE_LEFT = HOME203_NAME_LEFT
HOME203_PROFILE_TOP = HOME203_NAME_TOP
HOME203_PROFILE_RIGHT = HOME203_NAME_RIGHT
HOME203_PROFILE_BOTTOM = HOME203_NAME_BOTTOM


def read_home_profile_identity(image: Any) -> HomeProfileIdentity:
    """OCR Xbox 主页左上角显示名与邮箱。"""
    if image is None:
        return HomeProfileIdentity("", "")
    if hasattr(image, "data"):
        image = image.data
    if not isinstance(image, np.ndarray):
        return HomeProfileIdentity("", "")

    name_crop = _crop_region(
        image,
        HOME203_NAME_LEFT,
        HOME203_NAME_TOP,
        HOME203_NAME_RIGHT,
        HOME203_NAME_BOTTOM,
    )
    email_crop = _crop_region(
        image,
        HOME203_EMAIL_LEFT,
        HOME203_EMAIL_TOP,
        HOME203_EMAIL_RIGHT,
        HOME203_EMAIL_BOTTOM,
    )
    display_name = _ocr_text(name_crop)
    email_text = _ocr_text(email_crop)

    if not display_name and not email_text:
        combined_crop = _crop_region(
            image,
            HOME203_NAME_LEFT,
            HOME203_NAME_TOP,
            HOME203_EMAIL_RIGHT,
            HOME203_EMAIL_BOTTOM,
        )
        combined = _ocr_text(combined_crop)
        if "@" in combined:
            local, _, domain = combined.partition("@")
            display_name = local.strip()
            email_text = f"{local.strip()}@{domain.strip()}".strip()
        elif combined:
            display_name = combined

    if not display_name and email_text and "@" in email_text:
        display_name = email_local_part(email_text)

    return HomeProfileIdentity(display_name=display_name, email_text=email_text)


def read_home_profile_gamertag(image: Any) -> str:
    """OCR Xbox 主页（scene203）左上角当前登录档案名（兼容旧接口）。"""
    identity = read_home_profile_identity(image)
    if identity.display_name:
        return identity.display_name
    return identity.email_text


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

    crop = _crop_region(
        image,
        SCENE6_LIST_LEFT,
        SCENE6_LIST_TOP,
        SCENE6_LIST_RIGHT,
        SCENE6_LIST_BOTTOM,
    )
    if crop.size == 0:
        return []

    try:
        reader = _get_ocr_reader()
        lines: List[str] = []
        for variant in _prepare_ocr_variants(crop):
            try:
                results = reader.readtext(variant, detail=1, paragraph=False)
            except Exception:
                continue
            for item in results:
                if len(item) < 3:
                    continue
                text = str(item[1]).strip()
                conf = float(item[2])
                if text and conf >= 0.12 and text not in lines:
                    lines.append(text)
        return lines
    except Exception as exc:
        _logger.warning("Profile list OCR failed: %s", exc)
        return []


def scene6_list_layout_present(image: Any) -> bool:
    """当前帧是否具备场景 6 档案列表布局（绿框焦点或列表 OCR 有内容）。"""
    if image is None:
        return False
    if hasattr(image, "data"):
        image = image.data
    if not isinstance(image, np.ndarray):
        return False
    if detect_focused_row_y(image) is not None:
        return True
    return bool(read_list_gamertags(image))
