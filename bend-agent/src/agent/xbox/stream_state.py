"""串流会话状态枚举（CloudStreamController 等共用）。"""

from enum import Enum


class StreamState(Enum):
    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    DISCONNECTING = "disconnecting"
    ERROR = "error"
