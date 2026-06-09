"""PlayStation 主机串流租约（平台 xbox_host 表 platform=playstation，逻辑独立于 xbox/）。"""

from ..task.task_context import AgentTaskContext


def lease_blocks_task(status: dict, task_id: str) -> bool:
    """True 表示租约/锁存在且非本 task 重入。"""
    if status.get("leaseActive") or status.get("locked"):
        holder_task = status.get("leaseHolderTaskId") or status.get("lockedByTaskId")
        if holder_task and holder_task == task_id:
            return False
        return True
    return False


async def is_host_occupied_by_device_id(
    device_id: str,
    context: AgentTaskContext,
    task_logger,
) -> bool:
    """PS 主机占用检测（复用平台 device 级租约 API）。"""
    if not device_id:
        return False
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            status = await api_client.get_xbox_status_by_device_id(device_id)
        finally:
            await api_client.close()
    except Exception as exc:
        task_logger.warning("PS 占用检测：无法连接平台（%s）: %s", device_id, exc)
        return False

    if not status or not lease_blocks_task(status, context.task_id):
        return False

    task_logger.info(
        "PS 主机 %s 已被占用 holderAgent=%s holderTask=%s",
        device_id,
        status.get("leaseHolderAgentId") or status.get("lockedByAgentId"),
        status.get("leaseHolderTaskId") or status.get("lockedByTaskId"),
    )
    return True


async def _release_local_host(device_id: str, task_id: str, task_logger) -> None:
    try:
        from ..task.automation_scheduler import get_active_scheduler

        scheduler = get_active_scheduler()
        if scheduler:
            await scheduler.release_xbox_host(device_id, task_id)
    except Exception as exc:
        task_logger.debug("PS 释放本地调度器占用失败: %s", exc)


async def try_acquire_device_id(
    context: AgentTaskContext,
    device_id: str,
    task_logger,
) -> bool:
    """PS 主机租约申请。"""
    if not device_id:
        return False

    try:
        from ..task.automation_scheduler import get_active_scheduler

        scheduler = get_active_scheduler()
        if scheduler:
            local_ok = await scheduler.acquire_xbox_host(device_id, context.task_id)
            if not local_ok:
                task_logger.warning("PS 本地调度器：主机 %s 已被占用", device_id)
                return False
    except Exception as exc:
        task_logger.debug("PS 本地调度器占用检查失败: %s", exc)

    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            platform_locked = await api_client.lock_xbox_by_device_id(
                device_id, context.task_id
            )
        finally:
            await api_client.close()
        if not platform_locked:
            task_logger.warning("PS 平台租约申请失败 deviceId=%s", device_id)
            await _release_local_host(device_id, context.task_id, task_logger)
            return False
        task_logger.info("PS 平台租约已持有 deviceId=%s task=%s", device_id, context.task_id)
        context._stream_lease_server_id = device_id  # type: ignore[attr-defined]
        return True
    except Exception as exc:
        task_logger.warning("PS 平台锁定 deviceId=%s 异常: %s", device_id, exc)
        await _release_local_host(device_id, context.task_id, task_logger)
        return False


async def release_device_id(
    context: AgentTaskContext,
    device_id: str,
    task_logger,
) -> None:
    """释放 PS 主机租约。"""
    if not device_id:
        return
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            unlocked = await api_client.unlock_xbox_by_device_id(device_id, context.task_id)
        finally:
            await api_client.close()
        if unlocked:
            task_logger.info("已释放 PS 平台租约 deviceId=%s", device_id)
    except Exception as exc:
        task_logger.warning("释放 PS 平台租约失败 deviceId=%s: %s", device_id, exc)
    await _release_local_host(device_id, context.task_id, task_logger)
    if getattr(context, "_stream_lease_server_id", None) == device_id:
        context._stream_lease_server_id = None  # type: ignore[attr-defined]
