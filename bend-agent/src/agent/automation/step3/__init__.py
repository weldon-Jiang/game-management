"""
Step3 串流环境初始化包
===================
- xsrp_init: WebRTC 帧捕获 + SDL 显示 + 输入通道就绪
- display_helpers: SDL 窗口 / InputPump / 画面帧泵
"""
from .xsrp_init import step3_execute_xsrp_init, is_xsrp_stream_media_ready

__all__ = ["step3_execute_xsrp_init", "is_xsrp_stream_media_ready"]
