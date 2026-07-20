"""
商户权限校验模块
================

根据配置开关 require_license_check:
- false(默认): 信任分控平台已做校验,无需重复检查
- true:       自动化执行前主动调分控 API 确认授权有效

分控接口: GET /api/license-status/agent
鉴权方式: X-Agent-Id + X-Agent-Secret (AgentAuthFilter)

如果授权失效,Agent 拒绝执行自动化并上报错误。
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class LicenseCheckResult:
    """授权校验结果"""

    def __init__(self, valid: bool, reason: str = ""):
        self.valid = valid
        self.reason = reason


async def check_license(
    platform_api_url: str,
    agent_id: str,
    agent_secret: str,
) -> LicenseCheckResult:
    """
    调分控接口校验商户授权是否有效。

    Args:
        platform_api_url: 分控 API 地址 (如 http://192.168.1.10:8060/api)
        agent_id:         Agent ID
        agent_secret:     Agent Secret

    Returns:
        LicenseCheckResult
    """
    import base64
    import aiohttp

    url = f"{platform_api_url.rstrip('/')}/license-status/agent"
    headers = {
        "X-Agent-Id": agent_id,
        "X-Agent-Secret": base64.b64encode(agent_secret.encode()).decode(),
        "Content-Type": "application/json",
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    body = await resp.json()
                    data = body.get("data", {}) if isinstance(body, dict) else {}
                    valid = data.get("valid", True)
                    # valid=false 时才会填充 invalidReason
                    reason = data.get("invalidReason", "")
                    if valid:
                        logger.debug("License校验通过")
                    else:
                        logger.warning("License校验失败: %s", reason)
                    return LicenseCheckResult(valid=valid, reason=reason)
                else:
                    logger.warning("License校验请求失败 HTTP %s", resp.status)
                    return LicenseCheckResult(valid=False, reason=f"HTTP {resp.status}")
    except Exception as e:
        logger.error("License校验异常: %s", e)
        # 网络异常时保守处理：拒绝执行（宁可误拒不能放行）
        return LicenseCheckResult(valid=False, reason=f"网络异常: {e}")


def should_check_license() -> bool:
    """读取配置,判断是否需要 Agent 侧主动校验"""
    try:
        from agent.core.config import get_config
        cfg = get_config()
        return getattr(cfg, 'require_license_check', False)
    except Exception:
        return False
