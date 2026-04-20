"""
Logging configuration for Bend Agent

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
from logging.handlers import RotatingFileHandler
from pythonjsonlogger import jsonlogger


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

        # 配置JSON格式
        formatter = jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # 控制台处理器 - 输出到stdout
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # 文件处理器 - 日志轮转
        log_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'logs'
        )
        os.makedirs(log_dir, exist_ok=True)  # 确保日志目录存在
        log_file = os.path.join(log_dir, 'agent.log')

        # RotatingFileHandler实现日志轮转
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 单文件最大10MB
            backupCount=5,               # 保留5个备份
            encoding='utf-8'
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

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
