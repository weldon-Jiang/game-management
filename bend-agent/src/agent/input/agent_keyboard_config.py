"""
Agent 级键盘映射缓存：平台下发 / 心跳同步，未配置时使用默认模板。
"""

from __future__ import annotations

from typing import Dict, Optional

from ..core.logger import get_logger
from .keyboard_mapping_defaults import DEFAULT_KEYBOARD_BINDINGS

_logger = get_logger("agent_keyboard_config")

_cached_bindings: Optional[Dict[str, str]] = None


def get_effective_keyboard_bindings() -> Dict[str, str]:
    """返回当前生效映射（平台自定义或默认副本）。"""
    if _cached_bindings:
        return dict(_cached_bindings)
    return dict(DEFAULT_KEYBOARD_BINDINGS)


def apply_platform_keyboard_mapping(bindings: Optional[Dict[str, str]]) -> None:
    """
    应用平台下发的映射；None 或空表示恢复默认模板。
    并尝试热更新已运行任务上的 KeyboardMapper。
    """
    global _cached_bindings
    if not bindings:
        effective = dict(DEFAULT_KEYBOARD_BINDINGS)
        if _cached_bindings is None:
            return
        _cached_bindings = None
        _logger.info("键盘映射已恢复为默认模板")
    else:
        normalized = {str(k).lower(): str(v).upper() for k, v in bindings.items()}
        if _cached_bindings == normalized:
            return
        _cached_bindings = normalized
        effective = dict(normalized)
        _logger.info("键盘映射已更新（%d 项）", len(effective))

    _reload_running_keyboard_mappers(effective)


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
                _logger.info("已热更新任务 %s 键盘映射", task_id[:8])
    except Exception as exc:
        _logger.warning("热更新键盘映射失败: %s", exc)
