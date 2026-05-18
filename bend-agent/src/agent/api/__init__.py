"""
Bend Agent API模块
==================

功能说明：
- 与平台的通信接口
- WebSocket实时通信
- HTTP API调用

模块结构：
- client: 通用API客户端
- websocket: WebSocket客户端
- registration: Agent注册
- platform_api_client: 平台API客户端

作者：技术团队
版本：1.0
"""

from .client import ApiClient
from .websocket import WSClient, WSMessageType
from .registration import RegistrationActivator, AgentCredentials
from .platform_api_client import PlatformApiClient

__all__ = [
    'ApiClient',
    'WSClient',
    'WSMessageType',
    'RegistrationActivator',
    'AgentCredentials',
    'PlatformApiClient',
]