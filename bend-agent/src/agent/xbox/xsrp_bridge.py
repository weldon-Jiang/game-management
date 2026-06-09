"""
可选 libxsrp（xsrpwrapper）加载桥。

streaming/xsrp 的核心 DTLS-SRTP 在 C++ libxsrp.dll 内完成（OpenStreaming），
Python 层无法单独导出 SRTP 密钥。本模块仅用于探测 xsrpwrapper 是否可用，
供诊断与后续全量 libxsrp 串流路径扩展。
"""

from __future__ import annotations

import os
import sys
from typing import Any, Optional

from ..core.config import config
from ..core.logger import get_logger

logger = get_logger("xsrp_bridge")

_xsrp_module: Any = None
_load_attempted = False


def is_xsrp_available() -> bool:
    """检测 xsrpwrapper 是否可加载（Windows + 配置路径）。"""
    return _try_load_xsrp() is not None


def _try_load_xsrp() -> Optional[Any]:
    global _xsrp_module, _load_attempted
    if _load_attempted:
        return _xsrp_module
    _load_attempted = True

    configured = str(config.get("lan_stream.xsrp_module_path", "") or "").strip()
    candidates = []
    if configured:
        candidates.append(configured)
    # 常见开发路径（相对 team-management 旁路 streaming 仓库）
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..", "..", "..")
    )
    candidates.extend([
        os.path.join(repo_root, "..", "streaming", "xsrp"),
        os.path.join(repo_root, "streaming", "xsrp"),
        r"D:\auto-xbox\streaming\xsrp",
    ])

    if os.name != "nt":
        logger.debug("xsrpwrapper 仅 Windows 可用，跳过加载")
        return None

    for path in candidates:
        if not path or not os.path.isdir(path):
            continue
        if path not in sys.path:
            sys.path.append(path)
        try:
            import xsrpwrapper as xsrp  # type: ignore

            _xsrp_module = xsrp
            logger.info("xsrpwrapper 已加载: %s", path)
            return _xsrp_module
        except Exception as exc:
            logger.debug("加载 xsrpwrapper 失败 (%s): %s", path, exc)

    logger.debug("未找到可用 xsrpwrapper，LAN 媒体走 Python DTLS-PSK")
    return None
