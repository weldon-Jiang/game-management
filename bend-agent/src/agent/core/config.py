"""
Agent 集中配置管理
==================

功能说明：
- 统一管理所有配置常量
- 消除魔法值
- 提供配置验证
- 支持配置重载

作者：技术团队
版本：1.0
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List


class Config:
    """
    配置访问器 - 提供字典式访问接口
    """
    def __init__(self, agent_config: 'AgentConfig'):
        self._config = agent_config

    def get(self, key: str, default: Any = None) -> Any:
        """
        获取配置值（字典式访问）

        参数：
        - key: 配置键（支持点号分隔的路径，如 'task.heartbeat_interval'）
        - default: 默认值

        返回：
        - 配置值
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if hasattr(value, k):
                value = getattr(value, k)
            elif isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    @property
    def backend_url(self) -> str:
        return self._config.backend_url

    @property
    def ws_url(self) -> str:
        return self._config.ws_url

    @property
    def log_level(self) -> str:
        return self._config.log_level

    @property
    def log_format(self) -> str:
        return self._config.log_format

    def __getattr__(self, name: str) -> Any:
        return getattr(self._config, name)


@dataclass
class NetworkConfig:
    """
    网络配置
    """
    TCP_PORT: int = 5050
    UDP_PORT: int = 5050
    RTP_PORT: int = 50500
    CONNECTION_TIMEOUT: float = 10.0
    READ_TIMEOUT: float = 5.0
    WRITE_TIMEOUT: float = 5.0
    DRAIN_TIMEOUT: float = 5.0
    MAX_RETRY: int = 3
    RETRY_DELAY: float = 1.0


@dataclass
class StreamConfig:
    """
    串流配置
    """
    FRAMERATE: int = 30
    WIDTH: int = 1280
    HEIGHT: int = 720
    VIDEO_BITRATE: int = 5000000
    RTP_PACKET_SIZE: int = 1400
    BUFFER_SIZE: int = 30
    DROP_THRESHOLD: int = 25


@dataclass
class GamepadConfig:
    """
    手柄配置
    """
    POLL_INTERVAL: float = 0.016
    BUTTON_DEBOUNCE: float = 0.05
    ANALOG_DEADZONE: float = 0.1
    MAX_SIGNAL_RETRY: int = 3
    SIGNAL_INTERVAL: float = 0.05


@dataclass
class SceneConfig:
    """
    场景检测配置
    """
    TEMPLATE_MATCH_THRESHOLD: float = 0.8
    FRAME_INTERVAL: int = 5
    DETECTION_TIMEOUT: float = 60.0
    MAX_DETECTION_FRAME: int = 60
    DIFF_THRESHOLD: float = 0.1
    CACHE_TTL: float = 2.0
    DETECTION_INTERVAL: float = 0.5


@dataclass
class TaskConfig:
    """
    任务配置
    """
    MAX_CONCURRENT_TASKS: int = 3
    TASK_TIMEOUT: float = 3600.0
    HEARTBEAT_INTERVAL: int = 30
    RECONNECT_DELAY: float = 5.0
    MAX_RECONNECT_ATTEMPTS: int = 10


@dataclass
class AuthConfig:
    """
    认证配置
    """
    TOKEN_REFRESH_THRESHOLD: float = 300.0
    DEVICE_CODE_TIMEOUT: float = 300.0
    MSAL_TIMEOUT: float = 60.0


@dataclass
class AgentConfig:
    """
    Agent 主配置

    功能说明：
    - 整合所有子配置
    - 提供统一访问接口
    - 支持配置验证
    """
    network: NetworkConfig = field(default_factory=NetworkConfig)
    stream: StreamConfig = field(default_factory=StreamConfig)
    gamepad: GamepadConfig = field(default_factory=GamepadConfig)
    scene: SceneConfig = field(default_factory=SceneConfig)
    task: TaskConfig = field(default_factory=TaskConfig)
    auth: AuthConfig = field(default_factory=AuthConfig)
    aes: Dict[str, Any] = field(default_factory=dict)

    backend_url: str = 'http://localhost:8060'
    ws_url: str = 'ws://localhost:8060/ws/agent'

    log_level: str = 'INFO'
    log_format: str = 'standard'

    @classmethod
    def from_dict(cls, config: Dict[str, Any]) -> 'AgentConfig':
        """
        从字典创建配置

        参数：
        - config: 配置字典

        返回：
        - AgentConfig 实例
        """
        def to_config_dict(source: Dict[str, Any], fields: List[str]) -> Dict[str, Any]:
            """将源字典转换为配置字典（处理键的大小写）"""
            result = {}
            for field in fields:
                # 尝试小写、大写和原始格式
                for key in [field.lower(), field.upper(), field]:
                    if key in source:
                        result[field] = source[key]
                        break
            return result

        network_fields = ['TCP_PORT', 'UDP_PORT', 'RTP_PORT', 'CONNECTION_TIMEOUT', 'READ_TIMEOUT',
                         'WRITE_TIMEOUT', 'DRAIN_TIMEOUT', 'MAX_RETRY', 'RETRY_DELAY']
        stream_fields = ['FRAMERATE', 'WIDTH', 'HEIGHT', 'VIDEO_BITRATE', 'RTP_PACKET_SIZE',
                        'BUFFER_SIZE', 'DROP_THRESHOLD']
        gamepad_fields = ['POLL_INTERVAL', 'BUTTON_DEBOUNCE', 'ANALOG_DEADZONE',
                         'MAX_SIGNAL_RETRY', 'SIGNAL_INTERVAL']
        scene_fields = ['TEMPLATE_MATCH_THRESHOLD', 'FRAME_INTERVAL', 'DETECTION_TIMEOUT',
                       'MAX_DETECTION_FRAME', 'DIFF_THRESHOLD', 'CACHE_TTL', 'DETECTION_INTERVAL']
        task_fields = ['MAX_CONCURRENT_TASKS', 'TASK_TIMEOUT', 'HEARTBEAT_INTERVAL',
                      'RECONNECT_DELAY', 'MAX_RECONNECT_ATTEMPTS']
        auth_fields = ['TOKEN_REFRESH_THRESHOLD', 'DEVICE_CODE_TIMEOUT', 'MSAL_TIMEOUT']

        network_config = NetworkConfig(**to_config_dict(config.get('network', {}), network_fields))
        stream_config = StreamConfig(**to_config_dict(config.get('stream', {}), stream_fields))
        gamepad_config = GamepadConfig(**to_config_dict(config.get('gamepad', {}), gamepad_fields))
        scene_config = SceneConfig(**to_config_dict(config.get('scene', {}), scene_fields))
        task_config = TaskConfig(**to_config_dict(config.get('task', {}), task_fields))
        auth_config = AuthConfig(**to_config_dict(config.get('auth', {}), auth_fields))

        return cls(
            network=network_config,
            stream=stream_config,
            gamepad=gamepad_config,
            scene=scene_config,
            task=task_config,
            auth=auth_config,
            aes=config.get('aes', {}),
            backend_url=config.get('backend_url', config.get('backend', {}).get('base_url', 'http://localhost:8060')),
            ws_url=config.get('ws_url', config.get('backend', {}).get('ws_url', 'ws://localhost:8060/ws/agent')),
            log_level=config.get('log_level', 'INFO'),
            log_format=config.get('log_format', 'standard'),
        )

    def validate(self) -> List[str]:
        """
        验证配置

        返回：
        - 验证错误列表，如果为空则验证通过
        """
        errors = []

        if self.network.TCP_PORT <= 0 or self.network.TCP_PORT > 65535:
            errors.append(f"Invalid TCP_PORT: {self.network.TCP_PORT}")

        if self.network.UDP_PORT <= 0 or self.network.UDP_PORT > 65535:
            errors.append(f"Invalid UDP_PORT: {self.network.UDP_PORT}")

        if self.network.CONNECTION_TIMEOUT <= 0:
            errors.append(f"Invalid CONNECTION_TIMEOUT: {self.network.CONNECTION_TIMEOUT}")

        if self.stream.FRAMERATE <= 0 or self.stream.FRAMERATE > 120:
            errors.append(f"Invalid FRAMERATE: {self.stream.FRAMERATE}")

        if self.scene.TEMPLATE_MATCH_THRESHOLD < 0 or self.scene.TEMPLATE_MATCH_THRESHOLD > 1:
            errors.append(f"Invalid TEMPLATE_MATCH_THRESHOLD: {self.scene.TEMPLATE_MATCH_THRESHOLD}")

        if self.task.MAX_CONCURRENT_TASKS <= 0:
            errors.append(f"Invalid MAX_CONCURRENT_TASKS: {self.task.MAX_CONCURRENT_TASKS}")

        return errors

    def to_dict(self) -> Dict[str, Any]:
        """
        转换为字典

        返回：
        - 配置字典
        """
        return {
            'network': {
                'TCP_PORT': self.network.TCP_PORT,
                'UDP_PORT': self.network.UDP_PORT,
                'RTP_PORT': self.network.RTP_PORT,
                'CONNECTION_TIMEOUT': self.network.CONNECTION_TIMEOUT,
                'READ_TIMEOUT': self.network.READ_TIMEOUT,
                'WRITE_TIMEOUT': self.network.WRITE_TIMEOUT,
                'MAX_RETRY': self.network.MAX_RETRY,
                'RETRY_DELAY': self.network.RETRY_DELAY,
            },
            'stream': {
                'FRAMERATE': self.stream.FRAMERATE,
                'WIDTH': self.stream.WIDTH,
                'HEIGHT': self.stream.HEIGHT,
                'VIDEO_BITRATE': self.stream.VIDEO_BITRATE,
                'BUFFER_SIZE': self.stream.BUFFER_SIZE,
            },
            'gamepad': {
                'POLL_INTERVAL': self.gamepad.POLL_INTERVAL,
                'BUTTON_DEBOUNCE': self.gamepad.BUTTON_DEBOUNCE,
                'ANALOG_DEADZONE': self.gamepad.ANALOG_DEADZONE,
                'MAX_SIGNAL_RETRY': self.gamepad.MAX_SIGNAL_RETRY,
            },
            'scene': {
                'TEMPLATE_MATCH_THRESHOLD': self.scene.TEMPLATE_MATCH_THRESHOLD,
                'FRAME_INTERVAL': self.scene.FRAME_INTERVAL,
                'DETECTION_TIMEOUT': self.scene.DETECTION_TIMEOUT,
                'DIFF_THRESHOLD': self.scene.DIFF_THRESHOLD,
            },
            'task': {
                'MAX_CONCURRENT_TASKS': self.task.MAX_CONCURRENT_TASKS,
                'TASK_TIMEOUT': self.task.TASK_TIMEOUT,
                'HEARTBEAT_INTERVAL': self.task.HEARTBEAT_INTERVAL,
            },
            'auth': {
                'TOKEN_REFRESH_THRESHOLD': self.auth.TOKEN_REFRESH_THRESHOLD,
                'DEVICE_CODE_TIMEOUT': self.auth.DEVICE_CODE_TIMEOUT,
            },
            'aes': self.aes,
            'backend_url': self.backend_url,
            'ws_url': self.ws_url,
            'log_level': self.log_level,
            'log_format': self.log_format,
        }


GLOBAL_CONFIG: Optional[AgentConfig] = None
GLOBAL_CONFIG_ACCESSOR: Optional['Config'] = None


def get_config() -> AgentConfig:
    """
    获取全局配置

    返回：
    - 全局配置实例
    """
    global GLOBAL_CONFIG
    if GLOBAL_CONFIG is None:
        GLOBAL_CONFIG = AgentConfig()
    return GLOBAL_CONFIG


def set_config(config_obj: AgentConfig) -> None:
    """
    设置全局配置

    参数：
    - config_obj: 配置实例
    """
    global GLOBAL_CONFIG, GLOBAL_CONFIG_ACCESSOR
    GLOBAL_CONFIG = config_obj
    GLOBAL_CONFIG_ACCESSOR = Config(config_obj)


def load_config(config_path: Optional[str] = None) -> AgentConfig:
    """
    加载配置

    参数：
    - config_path: 配置文件路径，如果为None则使用默认配置

    返回：
    - 加载的配置实例
    """
    import yaml

    if config_path:
        with open(config_path, 'r', encoding='utf-8') as f:
            config_dict = yaml.safe_load(f)
        config_obj = AgentConfig.from_dict(config_dict)
    else:
        config_obj = AgentConfig()

    errors = config_obj.validate()
    if errors:
        raise ValueError(f"Configuration validation failed: {errors}")

    set_config(config_obj)
    return config_obj


def get_config_accessor() -> 'Config':
    """
    获取配置访问器

    返回：
    - Config 访问器实例
    """
    global GLOBAL_CONFIG_ACCESSOR
    if GLOBAL_CONFIG_ACCESSOR is None:
        get_config()
        global GLOBAL_CONFIG
        GLOBAL_CONFIG_ACCESSOR = Config(GLOBAL_CONFIG)
    return GLOBAL_CONFIG_ACCESSOR


class _ConfigProxy:
    """
    配置访问器代理 - 延迟获取最新的配置访问器
    """
    def __getattr__(self, name):
        if GLOBAL_CONFIG_ACCESSOR is None:
            return getattr(get_config_accessor(), name)
        return getattr(GLOBAL_CONFIG_ACCESSOR, name)

    def get(self, key, default=None):
        if GLOBAL_CONFIG_ACCESSOR is None:
            return get_config_accessor().get(key, default)
        return GLOBAL_CONFIG_ACCESSOR.get(key, default)


config = _ConfigProxy()
