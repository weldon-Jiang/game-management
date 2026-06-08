"""
Bend Agent 心跳专用日志

功能说明：
- HTTP / WebSocket 心跳成功与失败单独落盘
- 避免高频心跳刷掉主日志 agent.log 中的业务记录
"""
import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Optional

from .paths import get_logs_dir_fallback


class HeartbeatLogger:
    """心跳日志单例工厂。"""

    _logger: Optional[logging.Logger] = None

    @classmethod
    def get_heartbeat_logger(cls) -> logging.Logger:
        if cls._logger is not None:
            return cls._logger

        logs_dir = get_logs_dir_fallback()
        heartbeat_dir = os.path.join(logs_dir, 'heartbeat_log')
        os.makedirs(heartbeat_dir, exist_ok=True)

        logger = logging.getLogger('agent.heartbeat')
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.propagate = False

        log_file = os.path.join(heartbeat_dir, 'heartbeat.log')
        handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8',
        )
        handler.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        ))
        logger.addHandler(handler)

        cls._logger = logger
        return logger


def get_heartbeat_logger() -> logging.Logger:
    """快捷获取心跳日志记录器。"""
    return HeartbeatLogger.get_heartbeat_logger()
