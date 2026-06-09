"""
PlayStation 串流控制器（占位）。

后续实现：
- 视频解码管线对接 vision/
- 输入通道（DualSense / 虚拟手柄）
- 与 step3_streaming_init 的 PS 分流入口衔接

当前串流路径未启用；Xbox 仍走 xbox/lan_connect.py + step3。
"""

from typing import Any, Optional


class PsStreamController:
    """PS LAN 串流会话控制器（占位）。"""

    def __init__(self) -> None:
        self._connected = False
        self._session: Optional[Any] = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self, ip_address: str, port: int = 9295) -> bool:
        """连接 PS 主机（未实现）。"""
        _ = (ip_address, port)
        return False

    async def disconnect(self) -> None:
        """断开连接（占位）。"""
        self._connected = False
        self._session = None

    async def start_video_receiver(self, **kwargs) -> bool:
        """启动视频接收（未实现）。"""
        _ = kwargs
        return False
