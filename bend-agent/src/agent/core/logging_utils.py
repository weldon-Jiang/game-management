"""
日志格式化工具
==============

功能说明：
- 提供统一的日志格式
- 支持请求ID追踪
- JSON格式日志输出

作者：技术团队
版本：1.0
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from contextvars import ContextVar


_request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)


def set_request_id(request_id: Optional[str]) -> None:
    """
    设置当前请求ID（线程安全）

    参数：
    - request_id: 请求ID
    """
    _request_id_var.set(request_id)


def get_request_id() -> Optional[str]:
    """
    获取当前请求ID

    返回：
    - 当前请求ID，如果没有则返回None
    """
    return _request_id_var.get()


class RequestIdFormatter(logging.Formatter):
    """
    带请求ID的日志格式化器
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录

        参数：
        - record: 日志记录

        返回：
        - 格式化的日志字符串
        """
        request_id = get_request_id()

        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }

        if request_id:
            log_data['request_id'] = request_id

        if hasattr(record, 'task_id'):
            log_data['task_id'] = record.task_id

        if hasattr(record, 'step'):
            log_data['step'] = record.step

        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


class StandardFormatter(logging.Formatter):
    """
    标准日志格式化器（人类可读）
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录

        参数：
        - record: 日志记录

        返回：
        - 格式化的日志字符串
        """
        request_id = get_request_id()

        timestamp = datetime.fromtimestamp(record.created).strftime('%Y-%m-%d %H:%M:%S')
        level = record.levelname
        logger = record.name
        message = record.getMessage()

        parts = [f'[{timestamp}]', f'[{level}]', f'[{logger}]']

        if request_id:
            parts.append(f'[req:{request_id}]')

        if hasattr(record, 'task_id'):
            parts.append(f'[task:{record.task_id}]')

        if hasattr(record, 'step'):
            parts.append(f'[{record.step}]')

        parts.append(message)

        return ' '.join(parts)


def setup_json_logger(
    name: str,
    level: int = logging.INFO
) -> logging.Logger:
    """
    设置JSON格式日志记录器

    参数：
    - name: 日志记录器名称
    - level: 日志级别

    返回：
    - 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(RequestIdFormatter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger


def setup_standard_logger(
    name: str,
    level: int = logging.INFO
) -> logging.Logger:
    """
    设置标准格式日志记录器

    参数：
    - name: 日志记录器名称
    - level: 日志级别

    返回：
    - 配置好的日志记录器
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)
    logger.handlers.clear()

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(StandardFormatter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger


def get_logger_with_context(
    name: str,
    task_id: Optional[str] = None,
    step: Optional[str] = None
) -> logging.LoggerAdapter:
    """
    获取带上下文的日志记录器

    参数：
    - name: 日志记录器名称
    - task_id: 任务ID
    - step: 当前步骤

    返回：
    - 配置好的日志记录器适配器
    """
    logger = logging.getLogger(name)

    extra = {}
    if task_id:
        extra['task_id'] = task_id
    if step:
        extra['step'] = step

    return logging.LoggerAdapter(logger, extra)
