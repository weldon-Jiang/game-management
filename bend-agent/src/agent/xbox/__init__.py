"""
Xbox module for Bend Agent
"""
from .xbox_discovery import XboxDiscovery, xbox_discovery, XboxInfo
from .stream_controller import XboxStreamController, xbox_stream_controller, StreamState, StreamConfig
from .play_session import XboxPlaySessionManager, xbox_play_session_manager, PlaySession, PlaySessionConfig, SessionState, SDPConfiguration
from .webrtc_handler import XboxWebRTCHandler, xbox_webrtc_handler, WebRTCState, WebRTCConfig, SDPBuilder, IceCandidate

# RTP 相关模块（方案3：混合模式）
from .rtp_session import RTPSession, H264RTPPacketAssemble, RTPState, RTPHeader, RTPPacket
from .h264_parser import H264Parser, H264FrameAssembler, NALU, NALUType, SPSInfo
from .srtp_handler import SRTPHandler, SRTPKeys, SRTPError
from .dtls_handler import DTLSHandler, SimpleDTLSHandler, SRTPKeyMaterial, DTLSState

__all__ = [
    # 核心模块
    'XboxDiscovery', 'xbox_discovery', 'XboxInfo',
    'XboxStreamController', 'xbox_stream_controller', 'StreamState', 'StreamConfig',
    'XboxPlaySessionManager', 'xbox_play_session_manager', 'PlaySession', 'PlaySessionConfig', 'SessionState', 'SDPConfiguration',
    'XboxWebRTCHandler', 'xbox_webrtc_handler', 'WebRTCState', 'WebRTCConfig', 'SDPBuilder', 'IceCandidate',
    # RTP 模块（方案3）
    'RTPSession', 'H264RTPPacketAssemble', 'RTPState', 'RTPHeader', 'RTPPacket',
    'H264Parser', 'H264FrameAssembler', 'NALU', 'NALUType', 'SPSInfo',
    'SRTPHandler', 'SRTPKeys', 'SRTPError',
    'DTLSHandler', 'SimpleDTLSHandler', 'SRTPKeyMaterial', 'DTLSState'
]
