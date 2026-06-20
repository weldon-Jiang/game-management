"""xblive 认证结果模型。"""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class XbliveAuthResult:
    """对齐 xblive handle_return 产出，供 xsrp 后续使用。"""

    gs_token: str
    server_id: str
    play_path: str
    gamer_tag: str
    gssv_base_uri: str
    xhome_token: Dict[str, Any] = field(default_factory=dict)
    token_life_sec: int = 0
    errno: int = 0
    token_bundle: Dict[str, Any] = field(default_factory=dict)


@dataclass
class XbliveCompatXboxTokens:
    """兼容现有 Step2 读取 context.xbox_tokens.gs_token 等字段。"""

    gs_token: str
    gssv_base_uri: str
    server_id: str = ""
    play_path: str = ""
    gamer_tag: str = ""
    user_hash: str = ""
    xhome_token_response: Optional[Dict[str, Any]] = None
    user_token: str = ""
    xsts_token: str = ""
