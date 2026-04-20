"""
Configuration loader for Bend Agent

功能说明：
- 从YAML配置文件加载所有Agent配置参数
- 支持点号分隔的键名访问（如 'backend.base_url'）
- 单例模式确保全局配置一致
- 配置文件缺失时自动使用默认配置

默认配置项：
- backend: 后端服务器地址
- agent: Agent基本设置（心跳间隔、重连策略等）
- video: 视频捕获参数
- template: 模板匹配配置
- scene: 场景检测配置
- input: 输入控制参数
- automation: 自动化任务配置
- logging: 日志配置
- window: 窗口配置
"""
import os
import yaml
from typing import Any, Dict, Optional


class Config:
    """
    配置管理器

    功能说明：
    - 加载并管理YAML配置文件
    - 提供配置项的读取接口
    - 支持默认值和配置热重载

    使用方式：
    - 通过 config.get('key.subkey') 获取配置值
    - 配置值类型由YAML文件决定
    """

    _instance: Optional['Config'] = None    # 单例实例
    _config: Dict[str, Any] = {}            # 配置缓存

    def __new__(cls):
        """单例模式实现，确保全局只有一个Config实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """初始化时自动加载配置文件"""
        if not self._config:
            self.load()

    def load(self, config_path: str = None):
        """
        从YAML文件加载配置

        参数说明：
        - config_path: 配置文件路径（可选）
          - 如果为None，默认路径为 {项目根目录}/configs/agent.yaml

        加载逻辑：
        1. 如果指定路径文件存在，读取并解析YAML
        2. 如果文件不存在，使用默认配置
        """
        if config_path is None:
            # 默认配置文件路径：项目根目录/configs/agent.yaml
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                'configs',
                'agent.yaml'
            )

        if os.path.exists(config_path):
            # 读取YAML配置文件
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
        else:
            # 文件不存在，使用默认配置
            self._config = self._get_default_config()

    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置

        当配置文件不存在或解析失败时使用此默认配置

        默认配置内容：
        - backend: 后端服务地址（localhost:8080）
        - agent: Agent基本参数（心跳间隔30秒等）
        - video: 视频捕获参数（fps=10）
        - template: 模板匹配参数（阈值0.8）
        - scene: 场景检测参数
        - input: 输入控制参数
        - automation: 自动化任务参数
        - logging: 日志参数
        - window: 窗口尺寸参数
        """
        return {
            'backend': {
                'base_url': 'http://localhost:8080',       # 后端HTTP地址
                'ws_url': 'ws://localhost:8080/ws/agents',  # WebSocket地址
                'api_prefix': '/api'                        # API路由前缀
            },
            'agent': {
                'heartbeat_interval': 30,                 # 心跳间隔（秒）
                'reconnect_delay': 5,                      # 重连延迟（秒）
                'max_reconnect_attempts': 10,              # 最大重连次数
                'ws_heartbeat_interval': 30                # WebSocket心跳间隔
            },
            'video': {
                'fps': 10,                                  # 每秒帧数
                'capture_interval': 0.1,                   # 捕获间隔（秒）
                'max_frame_buffer': 5                      # 帧缓冲区大小
            },
            'template': {
                'threshold': 0.8,                          # 匹配阈值（0-1）
                'template_dir': './templates',             # 模板目录
                'cache_enabled': True                      # 是否启用缓存
            },
            'scene': {
                'detection_interval': 0.5,                # 检测间隔（秒）
                'confidence_threshold': 0.7              # 置信度阈值
            },
            'input': {
                'click_delay': 0.1,                        # 点击延迟（秒）
                'key_press_delay': 0.05,                  # 按键延迟（秒）
                'move_duration': 0.2                       # 鼠标移动时长（秒）
            },
            'automation': {
                'max_retries': 3,                          # 最大重试次数
                'retry_delay': 2,                         # 重试延迟（秒）
                'action_cooldown': 1                       # 操作冷却时间（秒）
            },
            'logging': {
                'level': 'INFO',                           # 日志级别
                'file': './logs/agent.log',                # 日志文件路径
                'max_size': 10,                            # 单个日志文件最大大小（MB）
                'backup_count': 5                          # 保留的备份文件数量
            },
            'window': {
                'default_width': 1280,                      # 默认窗口宽度
                'default_height': 720,                     # 默认窗口高度
                'min_width': 800,                          # 最小窗口宽度
                'min_height': 600                          # 最小窗口高度
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        参数说明：
        - key: 配置键名，支持点号分隔的嵌套访问
               例如：'backend.base_url' 会访问 _config['backend']['base_url']
        - default: 默认值，当键不存在时返回此值

        返回值：
        - 配置值（类型由YAML文件决定）
        - 键不存在时返回default参数值

        使用示例：
        - config.get('backend.base_url')
        - config.get('task.max_concurrent', 100)
        """
        # 将键名按点号分割
        keys = key.split('.')
        value = self._config

        # 逐层访问嵌套字典
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                # 如果当前值不是字典，说明路径错误
                return default
            if value is None:
                # 键不存在，返回默认值
                return default
        return value

    @property
    def backend_url(self) -> str:
        """
        获取后端服务器HTTP地址

        返回值：后端服务器URL，默认 'http://localhost:8080'
        """
        return self.get('backend.base_url', 'http://localhost:8080')

    @property
    def ws_url(self) -> str:
        """
        获取WebSocket服务器地址

        返回值：WebSocket服务器URL，默认 'ws://localhost:8080'
        """
        return self.get('backend.ws_url', 'ws://localhost:8080')

    @property
    def heartbeat_interval(self) -> int:
        """
        获取心跳发送间隔

        返回值：心跳间隔秒数，默认30秒
        """
        return self.get('agent.heartbeat_interval', 30)

    @property
    def template_dir(self) -> str:
        """
        获取模板图片目录

        返回值：模板目录路径，默认 './templates'
        """
        return self.get('template.template_dir', './templates')


# 全局配置实例
# 通过 from ..core.config import config 导入使用
config = Config()
