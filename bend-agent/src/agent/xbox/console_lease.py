"""Xbox 主机串流租约：本地调度器 + 平台 Redis/DB（仅 Xbox 模块使用）。"""

from typing import Optional

from ..task.task_context import AgentTaskContext


def lease_blocks_task(status: dict, task_id: str) -> bool:
    """True 表示租约/锁存在且非本 task 重入。"""
    if status.get("leaseActive") or status.get("locked"):
        holder_task = status.get("leaseHolderTaskId") or status.get("lockedByTaskId")
        if holder_task and holder_task == task_id:
            return False
        return True
    return False


async def is_host_occupied_by_server_id(
    server_id: str,
    context: AgentTaskContext,
    task_logger,
) -> bool:
    """只读占用检测：Redis 租约 + DB 锁；本 task 重入不算占用。"""
    if not server_id:
        return False
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            status = await api_client.get_xbox_status_by_device_id(server_id)
        finally:
            await api_client.close()
    except Exception as exc:
        task_logger.warning("占用检测：无法连接平台（%s）: %s", server_id, exc)
        return False

    if not status:
        return False

    if not lease_blocks_task(status, context.task_id):
        return False

    holder_agent = status.get("leaseHolderAgentId") or status.get("lockedByAgentId")
    holder_task = status.get("leaseHolderTaskId") or status.get("lockedByTaskId")
    task_logger.info(
        "主机 %s 已被占用 holderAgent=%s holderTask=%s",
        server_id,
        holder_agent,
        holder_task,
    )
    return True


async def _release_local_host(server_id: str, task_id: str, task_logger) -> None:
    try:
        from ..task.automation_scheduler import get_active_scheduler

        scheduler = get_active_scheduler()
        if scheduler:
            await scheduler.release_xbox_host(server_id, task_id)
    except Exception as exc:
        task_logger.debug("释放本地调度器占用失败: %s", exc)


async def try_acquire_server_id(
    context: AgentTaskContext,
    server_id: str,
    task_logger,
) -> bool:
    """握手前申请跨 Agent 串流租约（Redis + 平台 CAS）。"""
    if not server_id:
        return False

    try:
        from ..task.automation_scheduler import get_active_scheduler

        scheduler = get_active_scheduler()
        if scheduler:
            local_ok = await scheduler.acquire_xbox_host(server_id, context.task_id)
            if not local_ok:
                task_logger.warning("本地调度器：主机 %s 已被占用", server_id)
                return False
    except Exception as exc:
        task_logger.debug("本地调度器占用检查失败: %s", exc)

    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            platform_locked = await api_client.lock_xbox_by_device_id(
                server_id, context.task_id
            )
        finally:
            await api_client.close()
        if not platform_locked:
            task_logger.warning("平台串流租约申请失败 serverId=%s", server_id)
            await _release_local_host(server_id, context.task_id, task_logger)
            return False
        task_logger.info("平台串流租约已持有 serverId=%s task=%s", server_id, context.task_id)
        context._stream_lease_server_id = server_id  # type: ignore[attr-defined]
        return True
    except Exception as exc:
        task_logger.warning("平台锁定 serverId=%s 异常: %s", server_id, exc)
        await _release_local_host(server_id, context.task_id, task_logger)
        return False


async def release_server_id(
    context: AgentTaskContext,
    server_id: str,
    task_logger,
) -> None:
    """释放平台 Redis 租约与本地调度器占用。"""
    if not server_id:
        return
    try:
        from ..api.platform_api_client import PlatformApiClient

        api_client = PlatformApiClient()
        try:
            unlocked = await api_client.unlock_xbox_by_device_id(server_id, context.task_id)
        finally:
            await api_client.close()
        if unlocked:
            task_logger.info("已释放平台串流租约 serverId=%s", server_id)
    except Exception as exc:
        task_logger.warning("释放平台租约失败 serverId=%s: %s", server_id, exc)
    await _release_local_host(server_id, context.task_id, task_logger)
    if getattr(context, "_stream_lease_server_id", None) == server_id:
        context._stream_lease_server_id = None  # type: ignore[attr-defined]


async def release_xbox_host(context: AgentTaskContext, task_logger=None) -> None:
    """释放 Xbox 串流租约（跨 Agent）。"""
    if task_logger is None:
        from ..core.task_logger import get_task_logger

        task_logger = get_task_logger(context.task_id)
    server_id = getattr(context, "_stream_lease_server_id", None)
    if not server_id and context.current_xbox:
        server_id = context.current_xbox.id
    if server_id:
        await release_server_id(context, server_id, task_logger)
