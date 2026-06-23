"""
从场景 6 账号选择帧 / Xbox 主页读取档案标识并比对。

- 场景 6：左侧档案列表焦点行 PaddleOCR rec（960×540 坐标）
- 场景 203：主页左上角显示名 + 邮箱 OCR
- 裁剪区常量见 HOME203_* / SCENE6_*；自动化卡点时可人工截图后微调
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, List, Optional, Tuple

import cv2
import numpy as np

from ..core.logger import get_logger
from .ocr_engine import recognize_line, recognize_region, recognize_region_lines

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


def _as_bgr_ndarray(image: Any) -> Optional[np.ndarray]:
    """Frame 或 ndarray 统一为 BGR ndarray（勿对 ndarray 误用 .data）。"""
    if image is None:
        return None
    if isinstance(image, np.ndarray):
        return image
    data = getattr(image, "data", None)
    if isinstance(data, np.ndarray):
        return data
    return None


def normalize_gamertag(name: str) -> str:
    """用于模糊 Gamertag 比对的小写字母数字键。"""
    return re.sub(r"[^a-z0-9]", "", (name or "").lower())


def _levenshtein_distance(left: str, right: str) -> int:
    """两串编辑距离（小串长度通常 < 20，无需外部依赖）。"""
    if left == right:
        return 0
    if not left:
        return len(right)
    if not right:
        return len(left)
    prev = list(range(len(right) + 1))
    for i, ch_left in enumerate(left, 1):
        curr = [i]
        for j, ch_right in enumerate(right, 1):
            cost = 0 if ch_left == ch_right else 1
            curr.append(
                min(
                    prev[j] + 1,
                    curr[j - 1] + 1,
                    prev[j - 1] + cost,
                )
            )
        prev = curr
    return prev[-1]


def _ocr_gamertag_variants(normalized: str) -> List[str]:
    """
    主页 OCR 常见误读变体：头像边缘多 1 字符（如 y weldo1991）、首尾丢字。
    """
    if not normalized:
        return []
    variants = [normalized]
    seen = {normalized}
    if len(normalized) > 4:
        stripped = normalized[1:]
        if stripped not in seen:
            seen.add(stripped)
            variants.append(stripped)
    if len(normalized) > 5:
        trimmed = normalized[:-1]
        if trimmed not in seen:
            seen.add(trimmed)
            variants.append(trimmed)
    return variants


def _fuzzy_gamertag_distance_limit(target_len: int) -> int:
    """按目标长度允许的编辑距离（串流小字 OCR 常 1 字误差）。"""
    if target_len < 6:
        return 0
    if target_len < 10:
        return 1
    return 2


def gamertag_matches(detected: Optional[str], target: str) -> bool:
    """OCR 文本很可能匹配目标 Gamertag 时返回 True（含子串与轻度模糊）。"""
    if not detected or not target:
        return False
    det = normalize_gamertag(detected)
    tgt = normalize_gamertag(target)
    if not det or not tgt:
        return False
    if det == tgt or tgt in det or det in tgt:
        return True

    max_dist = _fuzzy_gamertag_distance_limit(len(tgt))
    if max_dist == 0:
        return False

    for variant in _ocr_gamertag_variants(det):
        if variant == tgt or tgt in variant or variant in tgt:
            return True
        if _levenshtein_distance(variant, tgt) <= max_dist:
            return True
    return False


def email_local_part(email: Optional[str]) -> str:
    """邮箱 @ 前本地段，用于与主页 OCR 文本比对。"""
    if not email or "@" not in email:
        return (email or "").strip()
    return email.split("@", 1)[0].strip()


def _home_ocr_match_candidates(
    detected_name: Optional[str],
    detected_email: Optional[str],
    combined_text: Optional[str],
) -> List[str]:
    """
    主页轮播 OCR 可能一次读出多档案片段，拆成行/词后再参与比对。

    保留整段 combined 以支持子串匹配（gamertag_matches）。
    """
    candidates: List[str] = []
    seen: set = set()

    def _add(text: Optional[str]) -> None:
        if not text:
            return
        cleaned = str(text).strip()
        if not cleaned:
            return
        key = cleaned.lower()
        if key not in seen:
            seen.add(key)
            candidates.append(cleaned)

    for raw in (detected_name, detected_email, combined_text):
        _add(raw)
        if not raw:
            continue
        for line in re.split(r"[\n\r]+", str(raw)):
            line = line.strip()
            if not line:
                continue
            _add(line)
            for token in re.split(r"\s+", line):
                token = token.strip().strip(",;")
                if token:
                    _add(token)

    return candidates


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
    ocr_texts = _home_ocr_match_candidates(
        detected_name, detected_email, combined_text
    )
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


def _normalize_row_label(text: Optional[str]) -> str:
    """场景6 列表行 OCR 文本归一化（去空白、小写）。"""
    return re.sub(r"\s+", "", (text or "").lower())


def is_scene6_add_guest_row(text: Optional[str]) -> bool:
    """焦点行是否为「添加访客」（列表倒数第二项，非触底）。"""
    norm = _normalize_row_label(text)
    if not norm:
        return False
    markers = (
        "添加访客",
        "addguest",
        "addaguest",
    )
    return any(marker in norm for marker in markers) and "新用户" not in norm and "newuser" not in norm


def is_scene6_add_new_user_row(text: Optional[str]) -> bool:
    """焦点行是否为「添加新用户」（列表最后一项）。"""
    norm = _normalize_row_label(text)
    if not norm:
        return False
    markers = (
        "添加新用户",
        "addnewuser",
        "addnew",
        "newuser",
    )
    return any(marker in norm for marker in markers)


def get_scene6_focus_row_y(image: Any) -> Optional[int]:
    """场景6 档案列表当前绿框焦点行的 Y 中心（960×540）。"""
    bgr = _as_bgr_ndarray(image)
    if bgr is None:
        return None
    return detect_focused_row_y(bgr)


def _green_ratio(hsv_crop: np.ndarray) -> float:
    mask = cv2.inRange(hsv_crop, (35, 80, 80), (85, 255, 255))
    return float(mask.mean()) / 255.0


def detect_focused_row_y(image: np.ndarray) -> Optional[int]:
    """检测场景 6 档案列表中绿色焦点条的 Y 轴中心。"""
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


def _ocr_text_line(crop: Optional[np.ndarray]) -> str:
    """单行 gamertag / 显示名：Paddle rec-only。"""
    if crop is None or crop.size == 0:
        return ""
    try:
        text, _ = recognize_line(crop)
        return text
    except Exception as exc:
        _logger.warning("Profile OCR line failed: %s", exc)
        return ""


def _ocr_text_email(crop: Optional[np.ndarray]) -> str:
    """邮箱行：优先 det+rec（保留 @），失败再 rec-only。"""
    if crop is None or crop.size == 0:
        return ""
    try:
        text, _ = recognize_region(crop)
        if text:
            return text
        text, _ = recognize_line(crop)
        return text
    except Exception as exc:
        _logger.warning("Profile OCR email failed: %s", exc)
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


# 场景 203 Xbox 主页左上角（960×540）：显示名 + 邮箱分两行
# NAME_LEFT 略右移，避免裁进头像蓝圈（易误读为 y 等噪声）
HOME203_NAME_LEFT = 95
HOME203_NAME_TOP = 42
HOME203_NAME_RIGHT = 215
HOME203_NAME_BOTTOM = 57
HOME203_EMAIL_LEFT = 86
HOME203_EMAIL_TOP = 57
HOME203_EMAIL_RIGHT = 244
HOME203_EMAIL_BOTTOM = 69
HOME203_PROFILE_LEFT = HOME203_NAME_LEFT
HOME203_PROFILE_TOP = HOME203_NAME_TOP
HOME203_PROFILE_RIGHT = HOME203_NAME_RIGHT
HOME203_PROFILE_BOTTOM = HOME203_NAME_BOTTOM

# Xbox 主页绿框焦点探针（960×540）：档案头像 / FC 磁贴 / 顶栏设置
HOME203_AVATAR_FOCUS_LEFT = 45
HOME203_AVATAR_FOCUS_TOP = 37
HOME203_AVATAR_FOCUS_RIGHT = 85
HOME203_AVATAR_FOCUS_BOTTOM = 76
HOME203_FC_FOCUS_LEFT = 52
HOME203_FC_FOCUS_TOP = 264
HOME203_FC_FOCUS_RIGHT = 184
HOME203_FC_FOCUS_BOTTOM = 399
HOME203_SETTINGS_FOCUS_LEFT = 535
HOME203_SETTINGS_FOCUS_TOP = 36
HOME203_SETTINGS_FOCUS_RIGHT = 574
HOME203_SETTINGS_FOCUS_BOTTOM = 75
# 主页滚到底时「返回顶部」按钮（按 A 后页面回顶且焦点落在 FC 磁贴）
HOME203_BACK_TO_TOP_FOCUS_LEFT = 47
HOME203_BACK_TO_TOP_FOCUS_TOP = 439
HOME203_BACK_TO_TOP_FOCUS_RIGHT = 203
HOME203_BACK_TO_TOP_FOCUS_BOTTOM = 499


def _focus_green_ratio(
    image: np.ndarray,
    left: int,
    top: int,
    right: int,
    bottom: int,
) -> float:
    """Xbox 系统 UI 绿框焦点在区域内的像素占比。"""
    crop = _crop_region(image, left, top, right, bottom)
    if crop.size == 0:
        return 0.0
    hsv = cv2.cvtColor(crop, cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, (35, 80, 80), (85, 255, 255))
    return float(mask.mean()) / 255.0


def read_home_focus_state(image: Any) -> dict:
    """
    读取 Xbox 主页当前焦点探针（档案头像 / FC 磁贴 / 设置 / 返回顶部）。

    用于主页门禁与 FC 磁贴导航；绿框仅在预标定矩形内检测，非全屏识别。
    """
    empty = {
        "profile_focused": False,
        "fc_focused": False,
        "settings_focused": False,
        "back_to_top_focused": False,
        "profile_ratio": 0.0,
        "fc_ratio": 0.0,
        "settings_ratio": 0.0,
        "back_to_top_ratio": 0.0,
    }
    if image is None:
        return empty
    image = _as_bgr_ndarray(image)
    if image is None:
        return empty

    profile_ratio = _focus_green_ratio(
        image,
        HOME203_AVATAR_FOCUS_LEFT,
        HOME203_AVATAR_FOCUS_TOP,
        HOME203_AVATAR_FOCUS_RIGHT,
        HOME203_AVATAR_FOCUS_BOTTOM,
    )
    fc_ratio = _focus_green_ratio(
        image,
        HOME203_FC_FOCUS_LEFT,
        HOME203_FC_FOCUS_TOP,
        HOME203_FC_FOCUS_RIGHT,
        HOME203_FC_FOCUS_BOTTOM,
    )
    settings_ratio = _focus_green_ratio(
        image,
        HOME203_SETTINGS_FOCUS_LEFT,
        HOME203_SETTINGS_FOCUS_TOP,
        HOME203_SETTINGS_FOCUS_RIGHT,
        HOME203_SETTINGS_FOCUS_BOTTOM,
    )
    back_to_top_ratio = _focus_green_ratio(
        image,
        HOME203_BACK_TO_TOP_FOCUS_LEFT,
        HOME203_BACK_TO_TOP_FOCUS_TOP,
        HOME203_BACK_TO_TOP_FOCUS_RIGHT,
        HOME203_BACK_TO_TOP_FOCUS_BOTTOM,
    )
    profile_focused = profile_ratio >= 0.05 and profile_ratio > fc_ratio
    fc_focused = fc_ratio >= 0.05 and fc_ratio >= profile_ratio
    settings_focused = settings_ratio >= 0.08
    back_to_top_focused = (
        back_to_top_ratio >= 0.05
        and back_to_top_ratio > fc_ratio
        and back_to_top_ratio > profile_ratio
    )
    return {
        "profile_focused": profile_focused,
        "fc_focused": fc_focused,
        "settings_focused": settings_focused,
        "back_to_top_focused": back_to_top_focused,
        "profile_ratio": profile_ratio,
        "fc_ratio": fc_ratio,
        "settings_ratio": settings_ratio,
        "back_to_top_ratio": back_to_top_ratio,
    }


def is_home_profile_avatar_focused(image: Any, *, min_ratio: float = 0.05) -> bool:
    """主页左上角档案头像是否获焦（绿框探针，且优于 FC 磁贴）。"""
    state = read_home_focus_state(image)
    return bool(state["profile_focused"])


def is_home_fc_tile_focused(image: Any, *, min_ratio: float = 0.05) -> bool:
    """主页 FC 磁贴是否获焦（绿框探针）。"""
    state = read_home_focus_state(image)
    return bool(state["fc_focused"])


def is_home_back_to_top_focused(image: Any) -> bool:
    """主页底部「返回顶部」是否获焦（绿框探针）。"""
    state = read_home_focus_state(image)
    return bool(state["back_to_top_focused"])


def read_home_profile_identity(image: Any) -> HomeProfileIdentity:
    """OCR Xbox 主页左上角显示名与邮箱。"""
    if image is None:
        return HomeProfileIdentity("", "")
    image = _as_bgr_ndarray(image)
    if image is None:
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
    display_name = _ocr_text_line(name_crop)
    email_text = _ocr_text_email(email_crop)

    if not display_name and not email_text:
        combined_crop = _crop_region(
            image,
            HOME203_NAME_LEFT,
            HOME203_NAME_TOP,
            HOME203_EMAIL_RIGHT,
            HOME203_EMAIL_BOTTOM,
        )
        combined = _ocr_text_email(combined_crop)
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
    image = _as_bgr_ndarray(image)
    if image is None:
        return ""

    row_y = detect_focused_row_y(image)
    crop = _crop_focused_text(image, row_y)
    return _ocr_text_line(crop)


def read_list_gamertags(image: Any) -> List[str]:
    """OCR 左侧列表全部可见 Gamertag（det+rec 兜底）。"""
    if image is None:
        return []
    image = _as_bgr_ndarray(image)
    if image is None:
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
        lines, _ = recognize_region_lines(crop)
        return lines
    except Exception as exc:
        _logger.warning("Profile list OCR failed: %s", exc)
        return []


def scene6_list_layout_present(image: Any) -> bool:
    """当前帧是否具备场景 6 档案列表布局（绿框焦点或列表 OCR 有内容）。"""
    if image is None:
        return False
    image = _as_bgr_ndarray(image)
    if image is None:
        return False
    if detect_focused_row_y(image) is not None:
        return True
    return bool(read_list_gamertags(image))
