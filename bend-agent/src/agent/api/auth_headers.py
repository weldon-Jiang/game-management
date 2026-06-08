"""Agent API 客户端共用的 HTTP 认证头辅助函数。"""

import base64
from typing import Dict, Optional


def build_agent_auth_headers(
    agent_id: Optional[str],
    agent_secret: Optional[str],
    extra: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    """构建标准 Agent HTTP 请求头（Secret 经 Base64 编码）。"""
    headers: Dict[str, str] = {"Content-Type": "application/json"}
    if extra:
        headers.update(extra)
    if agent_id and agent_secret:
        headers["X-Agent-Id"] = agent_id
        encoded_secret = base64.b64encode(agent_secret.encode("utf-8")).decode("utf-8")
        headers["X-Agent-Secret"] = encoded_secret
    return headers
