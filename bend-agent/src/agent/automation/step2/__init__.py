"""
Step2 串流握手包
==============
- router: 平台分发（Xbox xsrp / PlayStation）
- xsrp_streaming: GSSV 发现 + play/WebRTC 串流握手
- playstation_streaming: PlayStation 串流实现
"""
from .router import step2_execute_streaming
from .xsrp_streaming import step2_execute_xsrp_streaming

__all__ = ["step2_execute_streaming", "step2_execute_xsrp_streaming"]
