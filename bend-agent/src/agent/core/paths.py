"""
路径工具模块 - 获取正确的基准路径

PyInstaller 打包后，__file__ 会指向临时目录，需要特殊处理
"""
import os
import sys
import inspect


def get_base_dir() -> str:
    """
    获取应用程序基准目录

    打包前：返回源代码目录
    打包后：返回 exe 所在目录

    返回值：基准目录路径
    """
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后
        return os.path.dirname(sys.executable)
    else:
        # 开发环境 - 返回 src 目录的父目录
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def get_config_path() -> str:
    """
    获取配置文件路径

    返回值：agent.yaml 配置文件完整路径
    """
    base_dir = get_base_dir()
    return os.path.join(base_dir, 'agent.yaml')


def get_templates_dir() -> str:
    """
    获取模板目录路径

    返回值：templates 目录完整路径
    """
    base_dir = get_base_dir()
    return os.path.join(base_dir, 'templates')


def get_logs_dir() -> str:
    """
    获取日志目录路径

    返回值：logs 目录完整路径
    """
    base_dir = get_base_dir()
    return os.path.join(base_dir, 'logs')


def get_logs_dir_fallback() -> str:
    """
    获取日志目录路径（兼容旧代码）

    用于兼容使用 __file__ 构建路径的代码

    返回值：logs 目录完整路径
    """
    if getattr(sys, 'frozen', False):
        return get_logs_dir()
    else:
        return os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
            'logs'
        )
