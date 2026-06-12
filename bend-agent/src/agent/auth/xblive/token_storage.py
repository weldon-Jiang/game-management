"""
xblive 多级 Token 持久化：平台优先 + 本地 JSON 二级缓存。

一致性策略：
- 成功：先写平台，成功后再写本地 JSON
- 可恢复失败（缓存内容未变）：不写任何一侧
- 不可恢复失败：双端 invalidate（删平台行 + 删本地文件）
"""

from __future__ import annotations

import copy
import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, TYPE_CHECKING

from . import constants as C

if TYPE_CHECKING:
    from ...api.platform_api_client import PlatformApiClient

logger = logging.getLogger("xblive_token_storage")

# 本地 JSON 内嵌同步元数据（xblive hydrate 会忽略未知字段）
META_PLATFORM_VERSION = "_platform_token_version"
META_SYNCED_AT = "_synced_at"


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
    """读取本地 JSON 缓存（按邮箱）。"""
    path = _tokens_dir() / _email_to_filename(email)
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception as exc:
        logger.warning("加载 xblive 本地 token 缓存失败 %s: %s", email, exc)
        return None


def save_token_doc(
    email: str,
    doc: Dict[str, Any],
    *,
    platform_token_version: int = 0,
) -> None:
    """写入本地 JSON 缓存，并附带平台 version 元数据。"""
    path = _tokens_dir() / _email_to_filename(email)
    payload = dict(doc)
    if platform_token_version > 0:
        payload[META_PLATFORM_VERSION] = platform_token_version
        payload[META_SYNCED_AT] = datetime.now(timezone.utc).isoformat()
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        logger.debug("已保存 xblive 本地 token 缓存: %s", email)
    except Exception as exc:
        logger.error("保存 xblive 本地 token 缓存失败 %s: %s", email, exc)


def delete_token_doc(email: str) -> None:
    path = _tokens_dir() / _email_to_filename(email)
    if path.exists():
        path.unlink(missing_ok=True)


def _platform_enabled(streaming_account_id: str, task_id: str) -> bool:
    return bool((streaming_account_id or "").strip() and (task_id or "").strip())


def _refresh_token_from_doc(doc: Optional[Dict[str, Any]]) -> str:
    if not doc:
        return ""
    user = doc.get(C.KEY_USER_TOKEN)
    if isinstance(user, dict):
        return str(user.get(C.KEY_USER_REFRESH) or "")
    return ""


def _cache_fingerprint(doc: Optional[Dict[str, Any]]) -> tuple:
    """比较缓存是否被认证流程实质修改。"""
    if not doc:
        return ()
    user = doc.get(C.KEY_USER_TOKEN) if isinstance(doc.get(C.KEY_USER_TOKEN), dict) else {}
    xhome = doc.get(C.KEY_XHOME_TOKEN) if isinstance(doc.get(C.KEY_XHOME_TOKEN), dict) else {}
    xsts = doc.get(C.KEY_XSTS_TOKEN) if isinstance(doc.get(C.KEY_XSTS_TOKEN), dict) else {}
    return (
        _refresh_token_from_doc(doc),
        (xhome.get("gsToken") or "") if xhome else "",
        (xsts.get("Token") or "") if xsts else "",
        doc.get(C.KEY_SERVER_ID) or "",
        doc.get(C.KEY_GAMER_TAG) or "",
    )


def should_preserve_cache_on_failure(
    snapshot_doc: Optional[Dict[str, Any]],
    result_doc: Dict[str, Any],
) -> bool:
    """
    可恢复失败：进入 Step1 时的缓存与失败后 doc 指纹一致 → 不覆盖任一侧。
    """
    if snapshot_doc is None:
        return False
    return _cache_fingerprint(snapshot_doc) == _cache_fingerprint(result_doc)


def _infer_auth_state(doc: Dict[str, Any], errno: int) -> str:
    from . import errors as E

    if errno != E.ERRXS_OK:
        return "expired"
    now = datetime.now(timezone.utc).timestamp()
    xhome_time = float(doc.get(C.KEY_XHOME_TIME) or 0)
    if xhome_time and abs(now - xhome_time) < C.XHOME_TOKEN_LIFE_SEC:
        return "valid"
    user_time = float(doc.get(C.KEY_USER_TIME) or 0)
    if user_time and abs(now - user_time) < (90 * C.USER_TOKEN_LIFE_SEC):
        return "refresh_needed"
    return "refresh_needed"


def _xhome_expires_at_iso(doc: Dict[str, Any]) -> Optional[str]:
    xhome_time = float(doc.get(C.KEY_XHOME_TIME) or 0)
    if not xhome_time:
        return None
    expires = datetime.fromtimestamp(xhome_time + C.XHOME_TOKEN_LIFE_SEC, tz=timezone.utc)
    return expires.replace(microsecond=0).isoformat()


def _local_doc_preferred_over_platform(
    local_doc: Dict[str, Any],
    platform_version: int,
) -> bool:
    """平台标记 expired 时，若本地 version 更新则优先本地。"""
    local_version = int(local_doc.get(META_PLATFORM_VERSION) or 0)
    return local_version > platform_version and bool(_refresh_token_from_doc(local_doc))


async def _get_platform_client(
    platform_client: Optional["PlatformApiClient"],
) -> tuple[Optional["PlatformApiClient"], bool]:
    if platform_client is not None:
        return platform_client, False
    from ...api.platform_api_client import PlatformApiClient

    return PlatformApiClient(), True


async def _put_platform_with_retry(
    client: "PlatformApiClient",
    streaming_account_id: str,
    task_id: str,
    doc: Dict[str, Any],
    *,
    expected_token_version: int,
    auth_state: str,
    xhome_expires_at: Optional[str],
    max_attempts: int = 3,
) -> Optional[Dict[str, Any]]:
    expected = expected_token_version
    for attempt in range(max_attempts):
        saved = await client.put_auth_cache(
            streaming_account_id,
            task_id,
            doc,
            expected_token_version=expected,
            auth_state=auth_state,
            xhome_expires_at=xhome_expires_at,
        )
        if saved:
            return saved
        if attempt + 1 >= max_attempts:
            break
        cache = await client.get_auth_cache(streaming_account_id, task_id)
        if cache and cache.get("found"):
            expected = int(cache.get("tokenVersion") or 0)
        else:
            expected = 0
    return None


async def resolve_token_doc(
    email: str,
    *,
    streaming_account_id: str = "",
    task_id: str = "",
    platform_client: Optional["PlatformApiClient"] = None,
    force_full: bool = False,
) -> tuple[Optional[Dict[str, Any]], int]:
    """
    加载 token_doc：有效平台缓存优先；平台 expired 时尝试较新的本地；再 fallback 本地。
    """
    if force_full:
        return None, 0

    local_doc = load_token_doc(email)
    own_client = False
    client = platform_client

    if client is None and _platform_enabled(streaming_account_id, task_id):
        client, own_client = await _get_platform_client(None)

    platform_version = 0
    try:
        if client and _platform_enabled(streaming_account_id, task_id):
            cache = await client.get_auth_cache(streaming_account_id, task_id)
            if cache and cache.get("found") and isinstance(cache.get("tokenDoc"), dict):
                platform_version = int(cache.get("tokenVersion") or 0)
                auth_state = str(cache.get("authState") or "valid").lower()
                platform_doc = cache["tokenDoc"]

                if auth_state != "expired":
                    save_token_doc(email, platform_doc, platform_token_version=platform_version)
                    logger.info(
                        "已从平台加载 xblive token 缓存 account=%s version=%s",
                        streaming_account_id,
                        platform_version,
                    )
                    return copy.deepcopy(platform_doc), platform_version

                if local_doc and _local_doc_preferred_over_platform(local_doc, platform_version):
                    logger.info(
                        "平台缓存 expired，使用较新的本地 token account=%s local_v=%s platform_v=%s",
                        streaming_account_id,
                        local_doc.get(META_PLATFORM_VERSION),
                        platform_version,
                    )
                    return copy.deepcopy(local_doc), int(local_doc.get(META_PLATFORM_VERSION) or 0)

                logger.info(
                    "平台 token 缓存已 expired account=%s，跳过 hydrate",
                    streaming_account_id,
                )
                return None, 0
    except Exception as exc:
        logger.warning(
            "读取平台 xblive token 缓存失败 account=%s: %s",
            streaming_account_id,
            exc,
        )
    finally:
        if own_client and client is not None:
            await client.close()

    if local_doc:
        logger.debug("使用本地 xblive token 缓存: %s", email)
        return copy.deepcopy(local_doc), int(local_doc.get(META_PLATFORM_VERSION) or 0)
    return None, 0


async def persist_token_doc(
    email: str,
    doc: Dict[str, Any],
    *,
    streaming_account_id: str = "",
    task_id: str = "",
    platform_client: Optional["PlatformApiClient"] = None,
    platform_token_version: int = 0,
    errno: int = 0,
) -> bool:
    """
    认证成功后的双写：先平台，成功后再本地。

    返回 True 表示两侧（或仅本地模式）均已一致更新。
    """
    if not _platform_enabled(streaming_account_id, task_id):
        save_token_doc(email, doc)
        return True

    own_client = False
    client = platform_client
    if client is None:
        client, own_client = await _get_platform_client(None)

    auth_state = _infer_auth_state(doc, errno)
    xhome_expires_at = _xhome_expires_at_iso(doc)
    clean_doc = {k: v for k, v in doc.items() if not str(k).startswith("_")}

    try:
        saved = await _put_platform_with_retry(
            client,
            streaming_account_id,
            task_id,
            clean_doc,
            expected_token_version=platform_token_version,
            auth_state=auth_state,
            xhome_expires_at=xhome_expires_at,
        )
        if not saved:
            logger.error(
                "平台 token 写入失败，跳过本地更新以保持与平台一致 account=%s",
                streaming_account_id,
            )
            return False

        new_version = int(saved.get("tokenVersion") or (platform_token_version + 1))
        save_token_doc(email, clean_doc, platform_token_version=new_version)
        logger.info(
            "token 双写完成 account=%s version=%s state=%s",
            streaming_account_id,
            new_version,
            auth_state,
        )
        return True
    except Exception as exc:
        logger.error(
            "token 双写异常 account=%s: %s",
            streaming_account_id,
            exc,
        )
        return False
    finally:
        if own_client and client is not None:
            await client.close()


async def invalidate_token_cache(
    email: str,
    *,
    streaming_account_id: str = "",
    task_id: str = "",
    platform_client: Optional["PlatformApiClient"] = None,
) -> None:
    """不可恢复失败：删除平台行 + 本地 JSON，避免一侧过期一侧仍 valid。"""
    delete_token_doc(email)

    if not _platform_enabled(streaming_account_id, task_id):
        return

    own_client = False
    client = platform_client
    if client is None:
        client, own_client = await _get_platform_client(None)

    try:
        deleted = await client.delete_auth_cache(streaming_account_id, task_id)
        if deleted:
            logger.info("已清除平台 xblive token 缓存 account=%s", streaming_account_id)
        else:
            logger.warning("清除平台 xblive token 缓存失败 account=%s", streaming_account_id)
    except Exception as exc:
        logger.warning(
            "清除平台 xblive token 缓存异常 account=%s: %s",
            streaming_account_id,
            exc,
        )
    finally:
        if own_client and client is not None:
            await client.close()
