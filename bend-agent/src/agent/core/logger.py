"""
Bend Agent 日志配置

功能说明：
- 提供统一的日志记录接口
- 支持控制台和文件双输出
- JSON格式日志便于收集和分析
- 日志文件自动轮转（防止单个文件过大）

日志特性：
- 日志级别：DEBUG、INFO、WARNING、ERROR
- 日志轮转：单个文件最大10MB，保留5个备份
- JSON格式：包含时间戳、名称、级别、消息
- 多Logger支持：每个模块可使用独立Logger
"""
import os
import logging
import sys
import json
from logging.handlers import RotatingFileHandler

from .paths import get_logs_dir_fallback


class WindowsSafeRotatingFileHandler(RotatingFileHandler):
    """
    Windows 兼容的日志轮转处理器。

    标准 RotatingFileHandler 在 Windows 上轮转时使用 os.rename，若日志文件仍被
    其他 Handler 或外部进程（IDE、tail）占用会抛出 PermissionError，导致
    「Logging error」刷屏。此处捕获后跳过本轮轮转并重新打开文件继续写入。
    """

    def doRollover(self) -> None:
        try:
            super().doRollover()
        except (OSError, PermissionError):
            if self.stream is None:
                self.stream = self._open()


class CustomJsonFormatter(logging.Formatter):
    """
    自定义JSON日志格式化器

    功能说明：
    - 将日志记录格式化为JSON格式
    - 不转义Unicode字符（保持中文可读）
    - 支持自定义日期格式
    """

    def __init__(self, datefmt: str = '%Y-%m-%d %H:%M:%S'):
        super().__init__()
        self.datefmt = datefmt

    def format(self, record: logging.LogRecord) -> str:
        """
        格式化日志记录为JSON字符串

        参数说明：
        - record: 日志记录对象

        返回值：
        - JSON格式的日志字符串
        """
        log_entry = {
            'asctime': self.formatTime(record, self.datefmt),
            'name': record.name,
            'levelname': record.levelname,
            'message': record.getMessage()
        }
        return json.dumps(log_entry, ensure_ascii=False, separators=(', ', ': '))


class AgentLogger:
    """
    Logger工厂类

    功能说明：
    - 为不同模块创建独立的Logger实例
    - 维护Logger缓存，避免重复创建
    - 配置统一的日志格式和处理器

    使用方式：
    - AgentLogger.get_logger('module_name')
    - 或通过 get_logger('module_name') 快捷函数
    """

    _loggers = {}  # Logger缓存字典
    _shared_file_handler: logging.Handler = None  # agent.log 全局唯一文件 Handler

    @classmethod
    def _get_shared_file_handler(cls, formatter: logging.Formatter) -> logging.Handler:
        """所有模块 Logger 共享同一 agent.log Handler，避免多 Handler 争抢轮转。"""
        if cls._shared_file_handler is None:
            log_dir = get_logs_dir_fallback()
            os.makedirs(log_dir, exist_ok=True)
            log_file = os.path.join(log_dir, 'agent.log')
            handler = WindowsSafeRotatingFileHandler(
                log_file,
                maxBytes=10 * 1024 * 1024,
                backupCount=5,
                encoding='utf-8',
            )
            handler.setFormatter(formatter)
            cls._shared_file_handler = handler
        return cls._shared_file_handler

    @classmethod
    def get_logger(cls, name: str, level: str = "INFO") -> logging.Logger:
        """
        获取或创建Logger实例

        参数说明：
        - name: Logger名称，通常使用模块名
        - level: 日志级别，默认INFO

        返回值：
        - 配置好的logging.Logger实例

        实现逻辑：
        1. 检查缓存是否已有该名称的Logger
        2. 如有则直接返回
        3. 如无则创建并配置
        4. 设置JSON格式和双输出（控制台+文件）
        """
        # 缓存命中，直接返回
        if name in cls._loggers:
            return cls._loggers[name]

        # 创建新Logger
        logger = logging.getLogger(name)
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))
        logger.handlers.clear()  # 清除默认处理器

        # 配置JSON格式（使用自定义格式化器，不转义Unicode）
        formatter = CustomJsonFormatter(datefmt='%Y-%m-%d %H:%M:%S')

        # 控制台处理器 - 输出到stdout
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 文件处理器 - 所有模块共享同一 agent.log Handler（Windows 轮转安全）
        logger.addHandler(cls._get_shared_file_handler(formatter))

        # 缓存Logger实例
        cls._loggers[name] = logger
        return logger


def get_logger(name: str = "agent") -> logging.Logger:
    """
    快捷获取Logger函数

    参数说明：
    - name: Logger名称，默认 'agent'

    返回值：
    - logging.Logger实例

    使用示例：
    - logger = get_logger('api')
    - logger.info('API请求成功')
    """
    return AgentLogger.get_logger(name)
