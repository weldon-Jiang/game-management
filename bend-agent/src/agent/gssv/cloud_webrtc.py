"""GSSV 云端 WebRTC 会话：aiortc + SDP/ICE 交换 + DataChannel 握手（对照 libxsrp）。"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any, Dict, List, Optional, Set

import numpy as np

from ..core.config import config
from ..core.logger import get_logger
from .client import GssvClient
from .cloud_input import CloudInputSender
from .cloud_play_session import CloudPlayContext
from .endpoints import GssvEndpoints

try:
    from aiortc import RTCIceCandidate, RTCPeerConnection, RTCSessionDescription
    from aiortc import RTCConfiguration, RTCIceServer
    from aiortc.sdp import candidate_from_sdp

    AIORTC_AVAILABLE = True
except ImportError:
    AIORTC_AVAILABLE = False
    RTCIceCandidate = None  # type: ignore
    RTCPeerConnection = None  # type: ignore
    RTCSessionDescription = None  # type: ignore
    RTCConfiguration = None  # type: ignore
    RTCIceServer = None  # type: ignore
    candidate_from_sdp = None  # type: ignore


def _sdp_configuration() -> Dict[str, Any]:
    """POST /sdp 附带的 channel configuration（对照 xsplayer / libxsrp）。"""
    return {
        "chatConfiguration": {
            "bytesPerSample": 2,
            "expectedClipDurationMs": 20,
            "format": {"codec": "opus", "container": "webm"},
            "numChannels": 1,
            "sampleFrequencyHz": 24000,
        },
        "chat": {"minVersion": 1, "maxVersion": 1},
        "control": {"minVersion": 1, "maxVersion": 3},
        "input": {"minVersion": 1, "maxVersion": 8},
        "message": {"minVersion": 1, "maxVersion": 1},
    }


def _message_handshake() -> str:
    return json.dumps(
        {
            "type": "Handshake",
            "version": "messageV1",
            "id": "f9c5f412-0e69-4ede-8e62-92c7f5358c56",
            "cv": "",
        }
    )


def _authorization_request() -> str:
    return json.dumps(
        {
            "message": "authorizationRequest",
            "accessKey": "4BDB3609-C1F1-4195-9B37-FEFF45DA8B8E",
        }
    )


def _gamepad_changed(index: int = 0) -> str:
    return json.dumps(
        {
            "message": "gamepadChanged",
            "gamepadIndex": index,
            "wasAdded": True,
        }
    )


def _message_negotiation(target: str, content: str) -> str:
    return json.dumps(
        {
            "type": "Message",
            "content": content,
            "id": "41f93d5a-900f-4d33-b7a1-2d4ca6747072",
            "target": target,
            "cv": "",
        }
    )


def _normalize_candidate_line(raw: str) -> str:
    line = (raw or "").strip()
    if line.startswith("a="):
        line = line[2:]
    if line.startswith("candidate:"):
        return line
    if line.startswith("candidate "):
        return "candidate:" + line[len("candidate ") :]
    return f"candidate:{line}"


def _parse_exchange_response(payload: Dict[str, Any]) -> Any:
    """解析 GSSV exchangeResponse（可能是 JSON 字符串）。"""
    exchange = payload.get("exchangeResponse")
    if exchange is None:
        return payload
    if isinstance(exchange, str):
        try:
            return json.loads(exchange)
        except json.JSONDecodeError:
            return exchange
    return exchange


class GssvWebRtcSession:
    """
    GSSV 云端 WebRTC 串流会话。

    流程：Provisioned → 2s 延迟 → createOffer → POST/GET SDP → POST/GET ICE
    → message Handshake → control 授权 → input ClientMetadata → 收 video track。
    """

    def __init__(self, client: GssvClient, play_ctx: CloudPlayContext):
        if not AIORTC_AVAILABLE:
            raise RuntimeError("aiortc 未安装，请 pip install aiortc av")
        self.logger = get_logger("gssv_cloud_webrtc")
        self._client = client
        self._endpoints = GssvEndpoints(client.endpoints.base_uri)
        self._play_ctx = play_ctx
        self._pc: Optional[RTCPeerConnection] = None
        self._input_sender = CloudInputSender()
        self._channels: Dict[str, Any] = {}
        self._input_channel = None
        self._control_channel = None
        self._message_channel = None
        self._gathered_local_candidates: List[str] = []
        self._remote_ice_seen: Set[str] = set()
        self._remote_ice_complete = False
        self._ready = False
        self._input_ready = False
        self._video_task: Optional[asyncio.Task] = None
        self._latest_frame: Optional[np.ndarray] = None
        self._frame_lock = threading.Lock()
        self._frame_event = asyncio.Event()
        self._connect_time = 0.0
        self._input_close_callbacks: list = []

    def on_input_channel_close(self, callback) -> None:
        """注册 input DataChannel 关闭回调。"""
        if callable(callback):
            self._input_close_callbacks.append(callback)

    def _notify_input_closed(self) -> None:
        self._input_ready = False
        for cb in list(self._input_close_callbacks):
            try:
                cb()
            except Exception as exc:
                self.logger.debug("input close callback: %s", exc)

    @property
    def is_ready(self) -> bool:
        return self._ready

    @property
    def is_input_ready(self) -> bool:
        return self._input_ready

    @property
    def session_path(self) -> str:
        return self._play_ctx.session_path

    async def connect(self) -> None:
        """完整 WebRTC 连接：SDP/ICE + message 握手。"""
        webrtc_timeout = float(config.get("gssv.cloud_webrtc_timeout_sec", 90))
        await asyncio.wait_for(self._connect_impl(), timeout=webrtc_timeout)

    async def _connect_impl(self) -> None:
        delay_sec = float(config.get("gssv.cloud_post_provision_delay_sec", 2.0))
        if delay_sec > 0:
            await asyncio.sleep(delay_sec)

        ice_servers = [
            RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
            RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
        ]
        self._pc = RTCPeerConnection(RTCConfiguration(iceServers=ice_servers))

        self._channels["chat"] = self._pc.createDataChannel(
            "chat", ordered=False, protocol="chatV1"
        )
        self._control_channel = self._pc.createDataChannel(
            "control", ordered=False, protocol="controlV1"
        )
        self._input_channel = self._pc.createDataChannel(
            "input", ordered=True, protocol="1.0"
        )
        self._message_channel = self._pc.createDataChannel(
            "message", ordered=False, protocol="messageV1"
        )
        self._channels["control"] = self._control_channel
        self._channels["input"] = self._input_channel
        self._channels["message"] = self._message_channel

        self._pc.addTransceiver("video", direction="recvonly")

        @self._pc.on("track")
        def on_track(track):
            if track.kind == "video":
                self.logger.info("WebRTC video track 已建立")
                loop = asyncio.get_event_loop()
                self._video_task = loop.create_task(self._consume_video(track))

        self._gathered_local_candidates = []
        self._remote_ice_seen = set()
        self._remote_ice_complete = False

        @self._pc.on("icecandidate")
        def on_ice_candidate(event):
            if not event.candidate:
                return
            sdp_line = event.candidate.to_sdp()
            if sdp_line not in self._gathered_local_candidates:
                self._gathered_local_candidates.append(sdp_line)

        self._bind_message_channel()
        self._bind_input_channel()

        offer = await self._pc.createOffer()
        await self._pc.setLocalDescription(offer)
        await self._wait_ice_gathering(timeout=8.0)

        answer_sdp = await self._exchange_sdp(self._pc.localDescription.sdp)
        await self._pc.setRemoteDescription(
            RTCSessionDescription(sdp=answer_sdp, type="answer")
        )

        if self._pc.connectionState not in ("connected", "completed"):
            local_candidates = self._collect_local_candidates()
            self.logger.info(
                "ICE gathering 完成，本地 candidate 数量=%d",
                len(local_candidates),
            )
            if local_candidates:
                try:
                    await asyncio.wait_for(
                        self._run_ice_exchange(local_candidates),
                        timeout=float(
                            config.get("gssv.cloud_ice_exchange_timeout_sec", 30)
                        ),
                    )
                except (asyncio.TimeoutError, RuntimeError) as exc:
                    self.logger.warning(
                        "HTTP ICE 交换未完成（可能已通过 SDP 内联 candidate 连通）: %s",
                        exc,
                    )
            else:
                self.logger.warning("无本地 ICE candidate，跳过 HTTP ICE 交换")

        await self._wait_connection_state(timeout=25.0)
        await self._wait_input_ready(timeout=15.0)
        self._ready = True
        self._connect_time = time.monotonic()
        self.logger.info("GSSV WebRTC 会话就绪: session=%s", self._play_ctx.session_id)

    def _bind_message_channel(self) -> None:
        channel = self._message_channel
        if channel is None:
            return

        @channel.on("open")
        def on_open():
            self.logger.info("DataChannel message opened，发送 Handshake")
            channel.send(_message_handshake())

        @channel.on("message")
        def on_message(message):
            text = message if isinstance(message, str) else message.decode("utf-8", "ignore")
            try:
                payload = json.loads(text)
            except json.JSONDecodeError:
                return
            if str(payload.get("type", "")).lower() != "handshakeack":
                return
            self.logger.info("收到 HandshakeAck，发送 control 授权与 input ClientMetadata")
            self._send_control_json(_authorization_request())
            self._send_control_json(_gamepad_changed(0))
            self._send_input_bytes(self._input_sender.client_metadata_packet())
            self._send_message_json(
                _message_negotiation(
                    "/streaming/systemUi/configuration",
                    '"version": "[0, 1, 0]", "systemUis": "[33]"',
                )
            )
            self._send_message_json(
                _message_negotiation(
                    "/streaming/properties/clientappinstallidchanged",
                    '{"clientAppInstallId": "c11ddb2e-c7e3-4f02-a62b-fd5448e0b851"}',
                )
            )
            self._send_message_json(
                _message_negotiation(
                    "/streaming/characteristics/orientationchanged",
                    '{"orientation":0}',
                )
            )
            self._send_message_json(
                _message_negotiation(
                    "/streaming/characteristics/touchinputenabledchanged",
                    '{"touchInputEnabled":false}',
                )
            )
            self._input_ready = True

    def _bind_input_channel(self) -> None:
        channel = self._input_channel
        if channel is None:
            return

        @channel.on("close")
        def on_close():
            self.logger.warning("WebRTC input DataChannel closed")
            self._notify_input_closed()

    def _send_control_json(self, payload: str) -> None:
        if self._control_channel and getattr(self._control_channel, "readyState", "") == "open":
            self._control_channel.send(payload)

    def _send_message_json(self, payload: str) -> None:
        if self._message_channel and getattr(self._message_channel, "readyState", "") == "open":
            self._message_channel.send(payload)

    def _send_input_bytes(self, payload: bytes) -> None:
        if self._input_channel and getattr(self._input_channel, "readyState", "") == "open":
            self._input_channel.send(payload)

    async def _wait_ice_gathering(self, timeout: float) -> None:
        if not self._pc:
            return
        if self._pc.iceGatheringState == "complete":
            return
        done = asyncio.Event()

        @self._pc.on("icegatheringstatechange")
        def on_state_change():
            if self._pc and self._pc.iceGatheringState == "complete":
                done.set()

        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.logger.warning("ICE gathering 超时，继续 SDP 交换")

    def _collect_local_candidates(self) -> List[str]:
        """合并 trickle 事件与 local SDP 中的全部本地 candidate（去重保序）。"""
        seen: Set[str] = set()
        ordered: List[str] = []
        for raw in self._gathered_local_candidates:
            line = _normalize_candidate_line(raw)
            if line not in seen:
                seen.add(line)
                ordered.append(line)
        if self._pc and self._pc.localDescription:
            for raw in self._extract_all_candidates(self._pc.localDescription.sdp):
                line = _normalize_candidate_line(raw)
                if line not in seen:
                    seen.add(line)
                    ordered.append(line)
        return ordered

    @staticmethod
    def _extract_all_candidates(sdp: str) -> List[str]:
        results: List[str] = []
        for line in (sdp or "").splitlines():
            if "a=candidate:" in line:
                results.append(line.split("a=", 1)[1])
        return results

    async def _exchange_sdp(self, offer_sdp: str) -> str:
        url = self._endpoints.sdp(self._play_ctx.session_path)
        body = {
            "messageType": "offer",
            "sdp": offer_sdp,
            "configuration": _sdp_configuration(),
        }
        async with await self._client.post(url, body, timeout=60) as resp:
            post_text = await resp.text()
            if resp.status not in (200, 201, 202):
                raise RuntimeError(
                    f"GSSV SDP POST failed: HTTP {resp.status} {post_text[:400]}"
                )
            if resp.status == 200 and post_text:
                try:
                    data = json.loads(post_text)
                    exchange = _parse_exchange_response(data)
                    if isinstance(exchange, dict) and exchange.get("sdp"):
                        return self._normalize_sdp(str(exchange["sdp"]))
                except json.JSONDecodeError:
                    pass

        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline:
            async with await self._client.get(url, timeout=30) as resp:
                text = await resp.text()
                if resp.status in (202, 204):
                    await asyncio.sleep(1.0)
                    continue
                if resp.status != 200:
                    raise RuntimeError(f"GSSV SDP GET failed: HTTP {resp.status} {text[:400]}")
                data = json.loads(text) if text else {}
                exchange = _parse_exchange_response(data)
                if isinstance(exchange, dict) and exchange.get("sdp"):
                    return self._normalize_sdp(str(exchange["sdp"]))
            await asyncio.sleep(1.0)
        raise TimeoutError("GSSV SDP answer 等待超时")

    @staticmethod
    def _normalize_sdp(sdp: str) -> str:
        """GSSV exchangeResponse 中 SDP 可能含转义换行。"""
        text = (sdp or "").replace("\\r\\n", "\r\n").replace("\\n", "\n")
        if "v=0" in text and "\r\n" not in text and "\n" in text:
            text = text.replace("\n", "\r\n")
        return text

    async def _post_local_ice_candidate(self, candidate_line: str) -> None:
        """向 GSSV 上报单条本地 ICE candidate（含 end-of-candidates）。"""
        url = self._endpoints.ice(self._play_ctx.session_path)
        body = {"messageType": "iceCandidate", "candidate": candidate_line}
        async with await self._client.post(url, body, timeout=30) as resp:
            text = await resp.text()
            if resp.status not in (200, 202, 204):
                raise RuntimeError(
                    f"GSSV ICE POST failed: HTTP {resp.status} {text[:300]}"
                )
            if text:
                await self._apply_remote_ice(text)

    async def _run_ice_exchange(self, local_candidates: List[str]) -> None:
        """
        完整 HTTP ICE 交换：上报全部本地 candidate → 轮询远端 trickle candidate。

        GSSV answer SDP 使用 ice-options:trickle 且 c=0.0.0.0，必须双向补 candidate。
        """
        url = self._endpoints.ice(self._play_ctx.session_path)
        remote_applied = 0

        for candidate_line in local_candidates:
            self.logger.info("上报本地 ICE candidate: %s", candidate_line[:120])
            await self._post_local_ice_candidate(candidate_line)

        self.logger.info("上报本地 end-of-candidates")
        await self._post_local_ice_candidate("end-of-candidates")

        poll_deadline = time.monotonic() + float(
            config.get("gssv.cloud_ice_poll_sec", 25)
        )
        while time.monotonic() < poll_deadline:
            if self._pc and self._pc.connectionState in ("connected", "completed"):
                self.logger.info(
                    "HTTP ICE 轮询期间 WebRTC 已连通 (state=%s)",
                    self._pc.connectionState,
                )
                return
            if self._remote_ice_complete and remote_applied > 0:
                self.logger.info(
                    "已收到远端 end-of-candidates 且应用 %d 条 candidate",
                    remote_applied,
                )
                return

            async with await self._client.get(url, timeout=30) as resp:
                text = await resp.text()
                if resp.status in (202, 204):
                    await asyncio.sleep(0.5)
                    continue
                if resp.status != 200:
                    raise RuntimeError(
                        f"GSSV ICE GET failed: HTTP {resp.status} {text[:300]}"
                    )
                if not text:
                    self.logger.debug("GSSV ICE GET 200 但 body 为空")
                    await asyncio.sleep(0.5)
                    continue
                applied = await self._apply_remote_ice(text)
                remote_applied += applied
                if self._remote_ice_complete and remote_applied > 0:
                    return
            await asyncio.sleep(0.5)

        if remote_applied == 0:
            raise TimeoutError("GSSV ICE 远端 candidate 等待超时（未收到可解析 candidate）")
        self.logger.warning(
            "GSSV ICE 轮询超时，但已应用 %d 条远端 candidate，继续连接等待",
            remote_applied,
        )

    @staticmethod
    def _parse_ice_response_items(response_text: str) -> List[Dict[str, Any]]:
        """从 GSSV ICE 响应提取 candidate 条目（兼容 JSON / 转义嵌套）。"""
        text = (response_text or "").strip()
        if not text or '"candidate"' not in text and '\\"candidate\\"' not in text:
            return []

        items: List[Dict[str, Any]] = []

        try:
            data = json.loads(text)
            if isinstance(data, dict):
                exchange = _parse_exchange_response(data)
            else:
                exchange = data
            if isinstance(exchange, list):
                for element in exchange:
                    if isinstance(element, dict):
                        items.append(element)
                    elif isinstance(element, str):
                        try:
                            parsed = json.loads(element)
                            if isinstance(parsed, dict):
                                items.append(parsed)
                        except json.JSONDecodeError:
                            pass
            elif isinstance(exchange, dict):
                items.append(exchange)
            if items:
                return items
        except json.JSONDecodeError:
            pass

        marker = '{\\"candidate\\"'
        if marker in text:
            offset = 0
            while True:
                start = text.find(marker, offset)
                if start < 0:
                    break
                end = text.find("}", start) + 1
                if end <= start:
                    break
                chunk = text[start:end].replace("\\", "")
                try:
                    item = json.loads(chunk)
                    if isinstance(item, dict):
                        items.append(item)
                except json.JSONDecodeError:
                    pass
                offset = end
        return items

    async def _apply_remote_ice(self, response_text: str) -> int:
        """解析并应用 GSSV 返回的远端 ICE candidate，返回本次新应用条数。"""
        if not self._pc:
            return 0

        items = self._parse_ice_response_items(response_text)
        if not items and response_text.strip():
            preview = response_text.strip().replace("\n", " ")[:240]
            self.logger.debug("GSSV ICE 响应未能解析 candidate: %s", preview)

        applied = 0
        for item in items:
            cand = str(item.get("candidate", "")).strip()
            if not cand:
                continue
            if cand in self._remote_ice_seen:
                continue
            self._remote_ice_seen.add(cand)

            if "end-of-candidates" in cand:
                self._remote_ice_complete = True
                self.logger.info("收到远端 end-of-candidates")
                applied += 1
                continue

            ice = self._build_remote_ice_candidate(item)
            if ice is None:
                continue
            try:
                await self._pc.addIceCandidate(ice)
                applied += 1
                self.logger.info(
                    "已添加远端 ICE candidate (mid=%s idx=%s): %s",
                    ice.sdpMid,
                    ice.sdpMLineIndex,
                    _normalize_candidate_line(cand)[:120],
                )
            except Exception as exc:
                self.logger.warning(
                    "添加 ICE candidate 失败 (%s): %s",
                    _normalize_candidate_line(cand)[:80],
                    exc,
                )
        return applied

    def _build_remote_ice_candidate(
        self, item: Dict[str, Any]
    ) -> Optional[RTCIceCandidate]:
        """从 GSSV ICE 条目构造 aiortc candidate（补全 sdpMid / sdpMLineIndex）。"""
        cand = str(item.get("candidate", "")).strip()
        if not cand or "end-of-candidates" in cand:
            return None

        line = _normalize_candidate_line(cand)
        try:
            ice = candidate_from_sdp(line)
        except Exception as exc:
            self.logger.warning("解析远端 candidate 失败 (%s): %s", line[:80], exc)
            return None

        sdp_mid = item.get("sdpMid")
        if sdp_mid is None and item.get("id") is not None:
            sdp_mid = item.get("id")

        mline_index = item.get("sdpMLineIndex")
        if mline_index is None and item.get("label") is not None:
            mline_index = item.get("label")

        if sdp_mid is None and mline_index is None:
            # GSSV trickle 常只给 candidate 行；BUNDLE 会话默认挂到 video (mid=0)
            sdp_mid = "0"
            mline_index = 0

        if sdp_mid is not None:
            ice.sdpMid = str(sdp_mid)
        if mline_index is not None:
            ice.sdpMLineIndex = int(mline_index)
        elif ice.sdpMid is None:
            ice.sdpMLineIndex = 0
        return ice

    async def _wait_connection_state(self, timeout: float) -> None:
        if not self._pc:
            raise RuntimeError("PeerConnection 未初始化")
        state = self._pc.connectionState
        if state in ("connected", "completed"):
            return
        # aiortc 1.9 在已收到 track / open channel 时 state 可能仍为 connecting
        if self._input_ready or self._latest_frame is not None:
            self.logger.info(
                "WebRTC 已收到 track/input，跳过 connectionState 等待 (state=%s)",
                state,
            )
            return
        done = asyncio.Event()

        @self._pc.on("connectionstatechange")
        async def on_state_change():
            cur = self._pc.connectionState if self._pc else ""
            self.logger.info("WebRTC connectionState=%s", cur)
            if cur in ("connected", "completed", "failed"):
                done.set()

        try:
            await asyncio.wait_for(done.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            if self._input_ready or self._latest_frame is not None:
                self.logger.warning(
                    "connectionState 等待超时但 media/input 已就绪 (state=%s)",
                    self._pc.connectionState,
                )
                return
            raise RuntimeError(
                f"WebRTC 连接失败: state={self._pc.connectionState}"
            )
        if self._pc.connectionState == "failed":
            if self._input_ready or self._latest_frame is not None:
                return
            raise RuntimeError(f"WebRTC 连接失败: state={self._pc.connectionState}")

    async def _wait_input_ready(self, timeout: float) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self._input_ready:
                return
            msg = getattr(self._message_channel, "readyState", "")
            if msg == "open" and self._control_channel and self._input_channel:
                self._send_control_json(_authorization_request())
                self._send_control_json(_gamepad_changed(0))
                self._send_input_bytes(self._input_sender.client_metadata_packet())
                self._input_ready = True
                return
            await asyncio.sleep(0.2)
        raise TimeoutError("WebRTC input/message 通道握手超时")

    async def _consume_video(self, track) -> None:
        while True:
            try:
                frame = await track.recv()
            except Exception as exc:
                self.logger.debug("video track recv 结束: %s", exc)
                break
            try:
                img = frame.to_ndarray(format="bgr24")
            except Exception as exc:
                self.logger.debug("video frame 解码失败: %s", exc)
                continue
            with self._frame_lock:
                self._latest_frame = img
            self._frame_event.set()

    async def wait_first_frame(self, timeout: Optional[float] = None) -> bool:
        timeout = timeout or float(config.get("gssv.cloud_first_frame_timeout_sec", 20))
        if self._latest_frame is not None:
            return True
        try:
            await asyncio.wait_for(self._frame_event.wait(), timeout=timeout)
            return self._latest_frame is not None
        except asyncio.TimeoutError:
            return False

    async def get_latest_frame(self, timeout: float = 1.0) -> Optional[np.ndarray]:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return self._latest_frame.copy()
            await asyncio.sleep(0.01)
        return None

    async def send_gamepad(self, gamepad_data: Dict[str, Any]) -> bool:
        if not self._input_ready or not self._input_channel:
            return False
        if getattr(self._input_channel, "readyState", "") != "open":
            return False
        try:
            packet = self._input_sender.next_gamepad_packet(gamepad_data)
            self._input_channel.send(packet)
            return True
        except Exception as exc:
            self.logger.debug("send_gamepad 失败: %s", exc)
            return False

    async def send_keepalive(self) -> bool:
        return await self.send_gamepad(
            {
                "buttons": 0,
                "left_trigger": 0,
                "right_trigger": 0,
                "left_thumb_x": 0,
                "left_thumb_y": 0,
                "right_thumb_x": 0,
                "right_thumb_y": 0,
            }
        )

    async def close(self) -> None:
        if self._video_task and not self._video_task.done():
            self._video_task.cancel()
            try:
                await self._video_task
            except asyncio.CancelledError:
                pass
        if self._pc:
            await self._pc.close()
            self._pc = None
        self._ready = False
        self._input_ready = False
