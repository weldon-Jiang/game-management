"""
Account-specific logging for Bend Agent

功能说明：
- 为流媒体账号创建独立的登录/串流日志
- 为游戏账号创建独立的操作日志（按天轮转）
- 日志按账号名称命名，便于问题定位

日志目录结构：
- log/
  - agent.log                              # 主日志文件
  - stream_log/                            # 流媒体账号日志目录
    - stream_账号名.log                    # 每个流媒体账号独立日志
  - game_log/                              # 游戏账号日志目录
    - game_账号名_YYYY-MM-DD.log           # 每个游戏账号按天轮转日志
"""
import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from pythonjsonlogger import jsonlogger

from .paths import get_logs_dir_fallback


class AccountLogger:
    """
    账号专用日志记录器工厂类
    
    功能说明：
    - 为流媒体账号创建独立日志文件
    - 为游戏账号创建独立日志文件
    - 日志文件按账号名称命名
    - 支持日志轮转，防止文件过大
    """

    _stream_loggers = {}  # 流媒体日志缓存
    _game_loggers = {}    # 游戏日志缓存

    @classmethod
    def _create_file_handler(cls, log_file: str) -> RotatingFileHandler:
        """
        创建文件处理器（带轮转）
        
        参数说明：
        - log_file: 日志文件路径
        
        返回值：
        - RotatingFileHandler实例
        """
        return RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,   # 单文件最大5MB
            backupCount=3,              # 保留3个备份
            encoding='utf-8'
        )

    @classmethod
    def _create_formatter(cls) -> jsonlogger.JsonFormatter:
        """
        创建JSON格式器
        
        返回值：
        - JsonFormatter实例
        """
        return jsonlogger.JsonFormatter(
            '%(asctime)s %(name)s %(levelname)s %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    @classmethod
    def get_stream_logger(cls, streaming_account_name: str) -> logging.Logger:
        """
        获取流媒体账号专用日志记录器
        
        参数说明：
        - streaming_account_name: 流媒体账号名称
        
        返回值：
        - 配置好的logging.Logger实例
        
        日志文件路径：
        - log/stream_log/stream_账号名.log
        """
        # 清理账号名称中的非法字符
        safe_name = cls._sanitize_filename(streaming_account_name)
        
        # 检查缓存
        if safe_name in cls._stream_loggers:
            return cls._stream_loggers[safe_name]

        # 创建日志目录
        logs_dir = get_logs_dir_fallback()
        stream_log_dir = os.path.join(logs_dir, 'stream_log')
        os.makedirs(stream_log_dir, exist_ok=True)

        # 创建Logger
        logger_name = f"stream.{safe_name}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        # 文件处理器
        log_file = os.path.join(stream_log_dir, f'stream_{safe_name}.log')
        file_handler = cls._create_file_handler(log_file)
        file_handler.setFormatter(cls._create_formatter())
        logger.addHandler(file_handler)

        # 缓存并返回
        cls._stream_loggers[safe_name] = logger
        return logger

    @classmethod
    def _create_daily_file_handler(cls, log_file: str) -> TimedRotatingFileHandler:
        """
        创建按天轮转的文件处理器
        
        参数说明：
        - log_file: 日志文件路径（不含日期后缀）
        
        返回值：
        - TimedRotatingFileHandler实例
        
        轮转规则：
        - 每天凌晨0点轮转
        - 保留30天的日志文件
        - 文件名格式：game_账号名_YYYY-MM-DD.log
        """
        return TimedRotatingFileHandler(
            log_file,
            when='midnight',       # 每天凌晨轮转
            interval=1,            # 间隔1天
            backupCount=30,        # 保留30天
            encoding='utf-8',
            utc=False              # 使用本地时间
        )

    @classmethod
    def get_game_logger(cls, game_account_name: str) -> logging.Logger:
        """
        获取游戏账号专用日志记录器（按天轮转）
        
        参数说明：
        - game_account_name: 游戏账号名称（xboxGameName）
        
        返回值：
        - 配置好的logging.Logger实例
        
        日志文件路径：
        - log/game_log/game_账号名_YYYY-MM-DD.log
        
        轮转规则：
        - 每天凌晨0点自动轮转
        - 保留最近30天的日志
        - 单文件大小不受限制（按天分割）
        """
        # 清理账号名称中的非法字符
        safe_name = cls._sanitize_filename(game_account_name)
        
        # 检查缓存
        if safe_name in cls._game_loggers:
            return cls._game_loggers[safe_name]

        # 创建日志目录
        logs_dir = get_logs_dir_fallback()
        game_log_dir = os.path.join(logs_dir, 'game_log')
        os.makedirs(game_log_dir, exist_ok=True)

        # 创建Logger
        logger_name = f"game.{safe_name}"
        logger = logging.getLogger(logger_name)
        logger.setLevel(logging.DEBUG)
        logger.handlers.clear()

        # 文件处理器（按天轮转）
        log_file = os.path.join(game_log_dir, f'game_{safe_name}')
        file_handler = cls._create_daily_file_handler(log_file)
        file_handler.suffix = "%Y-%m-%d.log"  # 设置文件名后缀格式
        file_handler.setFormatter(cls._create_formatter())
        logger.addHandler(file_handler)

        # 缓存并返回
        cls._game_loggers[safe_name] = logger
        return logger

    @staticmethod
    def _sanitize_filename(filename: str) -> str:
        """
        清理文件名中的非法字符
        
        参数说明：
        - filename: 原始文件名
        
        返回值：
        - 安全的文件名
        
        处理逻辑：
        - 移除或替换非法字符
        - 限制长度
        """
        if not filename:
            return "unknown"
        
        # 定义非法字符映射
        illegal_chars = {
            '\\': '_', '/': '_', ':': '_', '*': '_',
            '?': '_', '"': '_', '<': '_', '>': '_', '|': '_',
            ' ': '_', '@': '_', '#': '_', '$': '_', '%': '_'
        }
        
        # 替换非法字符
        safe_name = filename
        for old_char, new_char in illegal_chars.items():
            safe_name = safe_name.replace(old_char, new_char)
        
        # 限制长度（最多50个字符）
        max_length = 50
        if len(safe_name) > max_length:
            safe_name = safe_name[:max_length]
        
        # 确保不为空
        if not safe_name or safe_name.isspace():
            return "unknown"
        
        return safe_name


# 快捷函数
def get_stream_logger(account_name: str) -> logging.Logger:
    """
    快捷获取流媒体账号日志记录器
    
    参数说明：
    - account_name: 流媒体账号名称
    
    返回值：
    - logging.Logger实例
    """
    return AccountLogger.get_stream_logger(account_name)


def get_game_logger(account_name: str) -> logging.Logger:
    """
    快捷获取游戏账号日志记录器
    
    参数说明：
    - account_name: 游戏账号名称
    
    返回值：
    - logging.Logger实例
    """
    return AccountLogger.get_game_logger(account_name)