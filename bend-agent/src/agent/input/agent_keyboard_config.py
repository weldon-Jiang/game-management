"""
Agent 键盘映射：平台下发 → 按任务缓存；任务结束清缓存；无缓存时用本地默认模板。

一个 Agent 仅一套映射（存于平台 Agent 表）；运行期按 task_id 挂载，避免跨任务泄漏。
"""

from __future__ import annotations

from typing import Dict, Optional, TYPE_CHECKING

from ..core.logger import get_logger
from .keyboard_mapping_defaults import DEFAULT_KEYBOARD_BINDINGS

if TYPE_CHECKING:
    from ..task.task_context import AgentTaskContext

_logger = get_logger("agent_keyboard_config")

_task_bindings: Dict[str, Dict[str, str]] = {}


def _normalize_bindings(raw: Dict[str, str]) -> Dict[str, str]:
    return {str(k).lower(): str(v).upper() for k, v in raw.items()}


def resolve_keyboard_bindings(raw: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """平台映射与本地默认合并；缺键时保留 Agent 默认扩展键（T/F/G/H 等）。"""
    merged = dict(DEFAULT_KEYBOARD_BINDINGS)
    if raw:
        merged.update(_normalize_bindings(raw))
    return merged


def get_effective_keyboard_bindings(context: Optional["AgentTaskContext"] = None) -> Dict[str, str]:
    """
    返回当前任务应使用的映射。

    优先级：context._keyboard_bindings → 任务缓存 → 本地默认（与改前行为一致）。
    """
    if context is not None:
        cached = getattr(context, "_keyboard_bindings", None)
        if cached:
            return dict(cached)
        task_id = getattr(context, "task_id", None)
        if task_id and task_id in _task_bindings:
            return dict(_task_bindings[task_id])
    return dict(DEFAULT_KEYBOARD_BINDINGS)


def apply_task_keyboard_mapping(
    task_id: str,
    context: Optional["AgentTaskContext"],
    bindings: Optional[Dict[str, str]],
) -> Dict[str, str]:
    """
    任务启动时绑定平台映射；返回合并后的生效映射并写入 context。
    """
    effective = resolve_keyboard_bindings(bindings if isinstance(bindings, dict) else None)
    _task_bindings[task_id] = effective
    if context is not None:
        context._keyboard_bindings = effective
    _logger.info(
        "任务 %s 键盘映射已绑定（%d 项，来源=%s）",
        task_id[:8],
        len(effective),
        "platform" if bindings else "default",
    )
    return effective


def clear_task_keyboard_mapping(task_id: str, context: Optional["AgentTaskContext"] = None) -> None:
    """任务结束/清理时移除缓存。"""
    removed = _task_bindings.pop(task_id, None) is not None
    if context is not None:
        context._keyboard_bindings = None
    if removed:
        _logger.info("任务 %s 键盘映射缓存已清除", task_id[:8])


def apply_platform_keyboard_mapping(bindings: Optional[Dict[str, str]]) -> None:
    """
    心跳/WS 热更新：仅更新仍在运行的任务，不写进程级全局缓存。
    """
    if not bindings:
        return
    effective = resolve_keyboard_bindings(bindings)
    try:
        from ..runtime.task_registry import TaskRuntimeRegistry

        registry = TaskRuntimeRegistry.get_instance()
        active_ids = registry.list_active_task_ids()
        if not active_ids:
            return
        for task_id in active_ids:
            _task_bindings[task_id] = effective
            runtime = registry.get(task_id)
            if runtime is not None and runtime.context is not None:
                runtime.context._keyboard_bindings = effective
        _logger.info("键盘映射已热更新至 %d 个运行中任务（%d 项）", len(active_ids), len(effective))
        _reload_running_keyboard_mappers(effective)
    except Exception as exc:
        _logger.warning("热更新键盘映射失败: %s", exc)


def _reload_running_keyboard_mappers(bindings: Dict[str, str]) -> None:
    try:
        from ..runtime.task_registry import TaskRuntimeRegistry

        registry = TaskRuntimeRegistry.get_instance()
        for task_id in registry.list_active_task_ids():
            runtime = registry.get(task_id)
            if runtime is None:
                continue
            mapper = getattr(runtime.context, "_keyboard_mapper", None)
            if mapper is not None and hasattr(mapper, "apply_bindings"):
                mapper.apply_bindings(bindings)
                _logger.info("已热更新任务 %s KeyboardMapper", task_id[:8])
    except Exception as exc:
        _logger.warning("热更新 KeyboardMapper 失败: %s", exc)
