"""
Agent 本地卸载：通知平台、清除凭证与注册表安装标记。
"""
from __future__ import annotations

from typing import Optional

from ..api.client import ApiClient
from ..api.registration import RegistrationActivator
from .logger import get_logger
from .machine_identity import machine_identity

logger = get_logger("agent_uninstall")


async def perform_agent_uninstall(
    reason: str = "用户主动卸载",
    notify_platform: bool = True,
) -> None:
    """
    执行完整本地卸载。

    步骤:
    1. （可选）通知平台 uninstall + clearRegistry
    2. 删除本地 credentials
    3. 清除注册表/文件中的 MachineId、InstallPath 等安装标记
    """
    activator = RegistrationActivator()
    credentials = activator.get_credentials()

    if notify_platform and credentials:
        await _notify_platform_uninstall(
            credentials.agent_id,
            credentials.agent_secret,
            reason,
        )

    activator.clear_credentials()
    machine_identity.clear_install_registry()
    logger.info("Agent local uninstall completed")


async def _notify_platform_uninstall(
    agent_id: str,
    agent_secret: str,
    reason: str,
) -> None:
    """尽力通知平台；失败不阻断本地清理。"""
    api = ApiClient(agent_id, agent_secret)
    try:
        await api.connect()
        result = await api.uninstall(reason=reason, clear_registry=True)
        if result.get("code") not in (200, None):
            logger.warning("Platform uninstall returned non-success: %s", result)
        else:
            logger.info("Platform notified of agent uninstall")
    except Exception as exc:
        logger.warning("Failed to notify platform during uninstall: %s", exc)
    finally:
        try:
            await api.close()
        except Exception:
            pass
