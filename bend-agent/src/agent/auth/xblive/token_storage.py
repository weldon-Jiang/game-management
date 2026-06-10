"""xblive 多级 Token 本地 JSON 持久化（替代 xblauth MongoDB）。"""

import json
import logging
import re
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("xblive_token_storage")


def _tokens_dir() -> Path:
    import sys

    if getattr(sys, "frozen", False):
        app_dir = Path(sys.executable).resolve().parent
    else:
        app_dir = Path(__file__).resolve().parents[4]
    path = app_dir / "tokens" / "xblive"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _email_to_filename(email: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", (email or "unknown").lower())
    return f"{safe}.json"


def load_token_doc(email: str) -> Optional[Dict[str, Any]]:
    path = _tokens_dir() / _email_to_filename(email)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("加载 xblive token 缓存失败 %s: %s", email, exc)
        return None


def save_token_doc(email: str, doc: Dict[str, Any]) -> None:
    path = _tokens_dir() / _email_to_filename(email)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2, ensure_ascii=False)
        logger.debug("已保存 xblive token 缓存: %s", email)
    except Exception as exc:
        logger.error("保存 xblive token 缓存失败 %s: %s", email, exc)


def delete_token_doc(email: str) -> None:
    path = _tokens_dir() / _email_to_filename(email)
    if path.exists():
        path.unlink(missing_ok=True)
