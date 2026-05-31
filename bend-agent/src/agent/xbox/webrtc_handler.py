"""
Xbox WebRTC SDP 握手管理器
===========================

功能说明：
- 创建和管理WebRTC Offer/Answer SDP
- 处理ICE候选交换
- 建立Xbox流媒体WebRTC连接

技术实现参考（streaming项目）：
- WebRTC SDP (Session Description Protocol)
- ICE (Interactive Connectivity Establishment)

作者：技术团队
版本：1.0
"""

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from enum import Enum

from ..core.logger import get_logger


class WebRTCState(Enum):
    """WebRTC状态枚举"""
    IDLE = "idle"
    CREATING_OFFER = "creating_offer"
    WAITING_ANSWER = "waiting_answer"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    FAILED = "failed"


@dataclass
class IceCandidate:
    """ICE候选信息"""
    candidate: str
    sdp_mid: Optional[str] = None
    sdp_mline_index: Optional[int] = None


@dataclass
class RTCSessionDescription:
    """RTC会话描述"""
    type: str  # offer / answer / pranswer / rollback
    sdp: str


@dataclass
class WebRTCConfig:
    """WebRTC配置"""
    audio_enabled: bool = True
    video_enabled: bool = True
    video_width: int = 1280
    video_height: int = 720
    video_framerate: int = 30
    audio_codec: str = "opus"
    video_codec: str = "H264"


class SDPBuilder:
    """
    SDP消息构建器

    功能说明：
    - 构建符合Xbox Live要求的WebRTC SDP
    - 支持音视频轨配置

    参考streaming项目的SDP格式
    """

    @staticmethod
    def build_offer_sdp(config: WebRTCConfig) -> str:
        """
        构建WebRTC Offer SDP

        参数：
        - config: WebRTC配置

        返回：
        - SDP字符串
        """
        session_id = str(uuid.uuid4()).replace('-', '')[:18]
        session_version = 2

        sdp_lines = [
            f"v=0",
            f"o=- {session_id} {session_version} IN IP4 127.0.0.1",
            f"s=-",
            f"t=0 0",
        ]

        if config.audio_enabled:
            sdp_lines.extend(SDPBuilder._build_audio_mline(config.audio_codec))

        if config.video_enabled:
            sdp_lines.extend(SDPBuilder._build_video_mline(config.video_codec, config))

        return "\r\n".join(sdp_lines)

    @staticmethod
    def _build_audio_mline(codec: str) -> List[str]:
        """构建音频媒体行"""
        return [
            "m=audio 9 UDP/TLS/RTP/SAVPF 111",
            "c=IN IP4 0.0.0.0",
            "a=rtcp:9 IN IP4 0.0.0.0",
            f"a=fmtp:111 minptime=10;useinbandfec=1",
            "a=ice-ufrag:audio_ufrag",
            "a=ice-pwd:audio_pwd",
            "a=ice-options:trickle",
            "a=candidate:1 1 udp 2130706431 127.0.0.1 9 typ host",
            f"a=rtpmap:111 {codec}/48000/2",
            "a=setup:actpass",
            "a=connection:new",
            "a=mid:audio",
        ]

    @staticmethod
    def _build_video_mline(codec: str, config: WebRTCConfig) -> List[str]:
        """构建视频媒体行"""
        return [
            f"m=video 9 UDP/TLS/RTP/SAVPF 96",
            "c=IN IP4 0.0.0.0",
            "a=rtcp:9 IN IP4 0.0.0.0",
            f"a=rtcp-fb:96 ccm fir",
            f"a=rtcp-fb:96 nack",
            f"a=rtcp-fb:96 nack pli",
            f"a=fmtp:96 level-asymmetry-allowed=1;packetization-mode=1;profile-level-id=42e01f",
            "a=ice-ufrag:video_ufrag",
            "a=ice-pwd:video_pwd",
            "a=ice-options:trickle",
            "a=candidate:1 1 udp 2130706431 127.0.0.1 9 typ host",
            f"a=rtpmap:96 {codec}/90000",
            "a=setup:actpass",
            "a=connection:new",
            "a=mid:video",
            f"a=ssrc-group:FID {uuid.uuid4().hex[:8]} {uuid.uuid4().hex[:8]}",
        ]

    @staticmethod
    def parse_answer_sdp(sdp: str) -> bool:
        """
        解析Answer SDP

        参数：
        - sdp: SDP字符串

        返回：
        - 是否有效
        """
        if not sdp:
            return False
        return "v=0" in sdp


class XboxWebRTCHandler:
    """
    Xbox WebRTC 握手处理器

    功能说明：
    - 管理完整的WebRTC握手流程
    - 支持Offer/Answer模式
    - 处理ICE候选

    使用方式：
    - 创建实例后调用 create_offer() 创建Offer
    - 调用 handle_answer() 处理Answer
    - 使用 on_ice_candidate() 设置ICE回调
    """

    def __init__(self, config: Optional[WebRTCConfig] = None):
        self.logger = get_logger('xbox_webrtc')
        self.config = config or WebRTCConfig()
        self._state = WebRTCState.IDLE
        self._local_description: Optional[RTCSessionDescription] = None
        self._remote_description: Optional[RTCSessionDescription] = None
        self._ice_candidates: List[IceCandidate] = []
        self._ice_callback: Optional[Callable[[IceCandidate], None]] = None
        self._pending_ice: List[IceCandidate] = []

    @property
    def state(self) -> WebRTCState:
        """获取WebRTC状态"""
        return self._state

    @property
    def local_sdp(self) -> Optional[str]:
        """获取本地SDP"""
        if self._local_description:
            return self._local_description.sdp
        return None

    @property
    def remote_sdp(self) -> Optional[str]:
        """获取远程SDP"""
        if self._remote_description:
            return self._remote_description.sdp
        return None

    def set_ice_callback(self, callback: Callable[[IceCandidate], None]):
        """
        设置ICE候选回调

        参数：
        - callback: ICE候选回调函数
        """
        self._ice_callback = callback

    def create_offer(self) -> Optional[str]:
        """
        创建WebRTC Offer

        返回：
        - Offer SDP字符串或None
        """
        try:
            self._state = WebRTCState.CREATING_OFFER

            sdp = SDPBuilder.build_offer_sdp(self.config)
            self._local_description = RTCSessionDescription(
                type="offer",
                sdp=sdp
            )

            self.logger.info("WebRTC Offer created")
            self._state = WebRTCState.WAITING_ANSWER

            return sdp

        except Exception as e:
            self.logger.error(f"Failed to create offer: {e}")
            self._state = WebRTCState.FAILED
            return None

    def handle_answer(self, answer_sdp: str) -> bool:
        """
        处理WebRTC Answer

        参数：
        - answer_sdp: Answer SDP字符串

        返回：
        - 是否成功
        """
        try:
            if self._state != WebRTCState.WAITING_ANSWER:
                self.logger.warning(f"Unexpected state for answer: {self._state}")

            if not SDPBuilder.parse_answer_sdp(answer_sdp):
                self.logger.error("Invalid Answer SDP")
                self._state = WebRTCState.FAILED
                return False

            self._remote_description = RTCSessionDescription(
                type="answer",
                sdp=answer_sdp
            )

            self.logger.info("WebRTC Answer processed")
            self._state = WebRTCState.CONNECTED

            for candidate in self._pending_ice:
                self._add_ice_candidate(candidate)
            self._pending_ice.clear()

            return True

        except Exception as e:
            self.logger.error(f"Failed to handle answer: {e}")
            self._state = WebRTCState.FAILED
            return False

    def add_ice_candidate(self, candidate: str, sdp_mid: str = None, sdp_mline_index: int = None):
        """
        添加ICE候选

        参数：
        - candidate: ICE候选字符串
        - sdp_mid: SDP媒体ID
        - sdp_mline_index: SDP媒体行索引
        """
        ice = IceCandidate(
            candidate=candidate,
            sdp_mid=sdp_mid,
            sdp_mline_index=sdp_mline_index
        )

        if self._state == WebRTCState.CONNECTED:
            self._add_ice_candidate(ice)
        else:
            self._pending_ice.append(ice)

    def _add_ice_candidate(self, candidate: IceCandidate):
        """处理ICE候选"""
        if self._ice_callback:
            try:
                self._ice_callback(candidate)
                self._ice_candidates.append(candidate)
                self.logger.debug(f"ICE candidate added: {candidate.candidate[:50]}...")
            except Exception as e:
                self.logger.error(f"ICE callback error: {e}")

    def reset(self):
        """重置WebRTC状态"""
        self._state = WebRTCState.IDLE
        self._local_description = None
        self._remote_description = None
        self._ice_candidates.clear()
        self._pending_ice.clear()
        self.logger.info("WebRTC handler reset")

    def get_connection_info(self) -> Dict[str, Any]:
        """
        获取连接信息

        返回：
        - 连接信息字典
        """
        return {
            "state": self._state.value,
            "has_local_sdp": self._local_description is not None,
            "has_remote_sdp": self._remote_description is not None,
            "ice_candidates_count": len(self._ice_candidates),
            "config": {
                "audio_enabled": self.config.audio_enabled,
                "video_enabled": self.config.video_enabled,
                "video_width": self.config.video_width,
                "video_height": self.config.video_height,
            }
        }


xbox_webrtc_handler = XboxWebRTCHandler()
