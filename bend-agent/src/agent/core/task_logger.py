"""
Bend Agent 按任务分文件日志

功能说明：
- 为每个自动化/串流任务创建独立日志文件
- 记录 Step1-4 及任务编排完整链路，避免写入主日志 agent.log
- 与 stream_log / game_log 互补：task_log 按任务维度，后两者按账号维度

日志目录结构：
- logs/
  - agent.log                    # 主日志（Agent 生命周期、连接、全局异常）
  - task_log/
    - task_{task_id}.log         # 每个任务独立日志
"""
import logging
import os
import re
from logging.handlers import RotatingFileHandler

from .paths import get_logs_dir_fallback


class TaskLogger:
    """任务专用日志记录器工厂类。"""

    _task_loggers: dict = {}

    @classmethod
    def _sanitize_task_id(cls, task_id: str) -> str:
        if not task_id:
            return "unknown"
        safe = re.sub(r'[^\w\-]', '_', str(task_id))
        return safe[:64] or "unknown"

    @classmethod
    def _create_formatter(cls) -> logging.Formatter:
        return logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S',
        )

    @classmethod
    def _create_file_handler(cls, log_file: str) -> RotatingFileHandler:
        return RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8',
        )

    @classmethod
    def get_task_logger(cls, task_id: str) -> logging.Logger:
        """
        获取任务专用日志记录器。

        日志文件路径：logs/task_log/task_{task_id}.log
        """
        safe_id = cls._sanitize_task_id(task_id)
        if safe_id in cls._task_loggers:
            return cls._task_loggers[safe_id]

        logs_dir = get_logs_dir_fallback()
        task_log_dir = os.path.join(logs_dir, 'task_log')
        os.makedirs(task_log_dir, exist_ok=True)

        logger_name = f"task.{safe_id}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()
        logger.propagate = False

        log_file = os.path.join(task_log_dir, f'task_{safe_id}.log')
        file_handler = cls._create_file_handler(log_file)
        file_handler.setFormatter(cls._create_formatter())
        logger.addHandler(file_handler)

        cls._task_loggers[safe_id] = logger
        return logger


def get_task_logger(task_id: str) -> logging.Logger:
    """快捷获取任务日志记录器。"""
    return TaskLogger.get_task_logger(task_id)
