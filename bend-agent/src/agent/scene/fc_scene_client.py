"""
FC Server 远程场景/比赛客户端
============================

对齐 streaming/payload.py 的 PayloadFrame(GRAPH/PLAY) 与 PayloadConfig(INIT/TERMINATE)。
"""

from __future__ import annotations

import json
from base64 import b64encode
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from ..core.logger import get_logger

# payload type（对齐 streaming PayloadBase）
PAYLOAD_TYPE_FRAME = 1
PAYLOAD_TYPE_CONTROLLER = 2
PAYLOAD_TYPE_CONFIG = 3
PAYLOAD_TYPE_REPORT = 4
PAYLOAD_TYPE_SCENE = 6

# payload action
PAYLOAD_ACTION_GRAPH = 1
PAYLOAD_ACTION_PLAY = 2
PAYLOAD_ACTION_INIT = 3
PAYLOAD_ACTION_TERMINATE = 4

KEY_TYPE = "type"
KEY_ACTION = "action"
KEY_SESSION = "session"
KEY_ERRNO = "errno"
KEY_ERRMSG = "errmsg"
KEY_MAIL = "mail"
KEY_CONTROLLER_INDEX = "controller_index"
KEY_FRAME = "frame"
KEY_FRAME_ID = "frame_id"
KEY_FRAME_OBJECTS = "frame_objects"
KEY_SCENE = "scene"
KEY_CONTROLLER = "controller"
KEY_CONFIG = "config"

# FC 业务 errno（对齐 streaming/xsrp.py Errs）
FC_ERR_OK = 0
FC_ERR_NETWORK = 20000
FC_ERR_MATCH_EXISTED = 20003
FC_ERR_MATCH_OVER = 20005


@dataclass
class FCSceneResult:
    errno: int = 0
    scene_id: int = -1
    controller_actions: List[Dict[str, Any]] = field(default_factory=list)
    errmsg: str = ""


@dataclass
class FCReportResult:
    errno: int = 0
    session: str = ""
    errmsg: str = ""


@dataclass
class FCPlayResult:
    errno: int = 0
    session: str = ""
    frame_seq: int = 0
    controller_actions: List[Dict[str, Any]] = field(default_factory=list)
    errmsg: str = ""


class FCSceneClient:
    """经 FC Server HTTP 的 GRAPH / PLAY / INIT / TERMINATE 客户端。"""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        session_token: str = "",
        gamepad_index: int = 0,
        frame_width: int = 1280,
        frame_height: int = 720,
    ):
        self.logger = get_logger("fc_scene_client")
        self.host = host
        self.port = port
        self.username = username
        self.session_token = session_token
        self.gamepad_index = gamepad_index
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._frame_seq = 0
        self._api_url = f"http://{host}:{port}/api/payload"

    def _encode_frame(self, frame: np.ndarray) -> str:
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("Failed to encode frame for FC payload")
        return b64encode(encoded.tobytes()).decode("utf-8")

    def build_graph_packet(self, frame: np.ndarray) -> str:
        packet = {
            KEY_TYPE: PAYLOAD_TYPE_FRAME,
            KEY_ACTION: PAYLOAD_ACTION_GRAPH,
            KEY_SESSION: self.session_token,
            KEY_ERRNO: 0,
            KEY_ERRMSG: "",
            KEY_MAIL: self.username,
            KEY_CONTROLLER_INDEX: self.gamepad_index,
            KEY_FRAME: self._encode_frame(frame),
            KEY_FRAME_OBJECTS: [],
        }
        return json.dumps(packet, ensure_ascii=False)

    def build_play_packet(self, frame: np.ndarray) -> str:
        self._frame_seq += 1
        packet = {
            KEY_TYPE: PAYLOAD_TYPE_FRAME,
            KEY_ACTION: PAYLOAD_ACTION_PLAY,
            KEY_SESSION: self.session_token,
            KEY_ERRNO: 0,
            KEY_ERRMSG: "",
            KEY_MAIL: self.username,
            KEY_CONTROLLER_INDEX: self.gamepad_index,
            KEY_FRAME: self._encode_frame(frame),
            KEY_FRAME_OBJECTS: [],
        }
        return json.dumps(packet, ensure_ascii=False)

    def build_config_packet(self, action: int) -> str:
        packet = {
            KEY_TYPE: PAYLOAD_TYPE_CONFIG,
            KEY_ACTION: action,
            KEY_SESSION: self.session_token,
            KEY_ERRNO: 0,
            KEY_ERRMSG: "",
            KEY_MAIL: self.username,
            KEY_CONFIG: {
                "username": self.username,
                "height": self.frame_height,
                "width": self.frame_width,
                "controller_index": self.gamepad_index,
            },
        }
        return json.dumps(packet, ensure_ascii=False)

    def parse_scene_response(self, response_text: str) -> Optional[FCSceneResult]:
        if not response_text:
            return None
        try:
            packet = json.loads(response_text)
            if packet.get(KEY_TYPE) != PAYLOAD_TYPE_SCENE:
                return None
            session = str(packet.get(KEY_SESSION, "") or "")
            if session:
                self.session_token = session
            return FCSceneResult(
                errno=int(packet.get(KEY_ERRNO, -1)),
                scene_id=int(packet.get(KEY_SCENE, -1)),
                controller_actions=list(packet.get(KEY_CONTROLLER, []) or []),
                errmsg=str(packet.get(KEY_ERRMSG, "")),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.logger.error("Failed to parse FC scene response: %s", exc)
            return None

    def parse_report_response(self, response_text: str) -> Optional[FCReportResult]:
        if not response_text:
            return None
        try:
            packet = json.loads(response_text)
            if packet.get(KEY_TYPE) != PAYLOAD_TYPE_REPORT:
                return None
            session = str(packet.get(KEY_SESSION, "") or "")
            if session:
                self.session_token = session
            return FCReportResult(
                errno=int(packet.get(KEY_ERRNO, -1)),
                session=session,
                errmsg=str(packet.get(KEY_ERRMSG, "")),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.logger.error("Failed to parse FC report response: %s", exc)
            return None

    def parse_play_response(self, response_text: str) -> FCPlayResult:
        if not response_text:
            return FCPlayResult(errno=FC_ERR_NETWORK, errmsg="empty response")
        try:
            packet = json.loads(response_text)
            payload_type = int(packet.get(KEY_TYPE, 0))
            session = str(packet.get(KEY_SESSION, "") or "")
            if session:
                self.session_token = session
            errno = int(packet.get(KEY_ERRNO, -1))
            errmsg = str(packet.get(KEY_ERRMSG, ""))

            if payload_type == PAYLOAD_TYPE_REPORT:
                return FCPlayResult(errno=errno, session=session, errmsg=errmsg)

            if payload_type == PAYLOAD_TYPE_CONTROLLER:
                return FCPlayResult(
                    errno=errno,
                    session=session,
                    frame_seq=int(packet.get(KEY_FRAME_ID, 0) or 0),
                    controller_actions=list(packet.get(KEY_CONTROLLER, []) or []),
                    errmsg=errmsg,
                )
            return FCPlayResult(errno=errno, session=session, errmsg=f"unexpected type {payload_type}")
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.logger.error("Failed to parse FC play response: %s", exc)
            return FCPlayResult(errno=FC_ERR_NETWORK, errmsg=str(exc))

    async def _post_packet(self, packet: str) -> Tuple[int, str]:
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(self._api_url, data=packet) as resp:
                    if resp.status != 200:
                        self.logger.error("FC server HTTP %s", resp.status)
                        return resp.status, ""
                    body = await resp.json()
                    result_obj = body.get("result", body)
                    return 200, json.dumps(result_obj, ensure_ascii=False)
        except Exception as exc:
            self.logger.error("FC request failed: %s", exc)
            return 0, ""

    async def recognize_scene(self, frame: np.ndarray) -> FCSceneResult:
        status, response_text = await self._post_packet(self.build_graph_packet(frame))
        if status != 200 or not response_text:
            return FCSceneResult(errno=FC_ERR_NETWORK, errmsg=f"HTTP {status or 'error'}")
        parsed = self.parse_scene_response(response_text)
        return parsed or FCSceneResult(errno=FC_ERR_NETWORK, errmsg="invalid response")

    async def recognize_scene_id(self, frame: np.ndarray) -> Tuple[int, List[Dict[str, Any]]]:
        result = await self.recognize_scene(frame)
        if result.errno != FC_ERR_OK:
            return -1, []
        return result.scene_id, result.controller_actions

    async def init_match(self) -> FCReportResult:
        """对齐 streaming remote_game_init：先 terminate 再 init。"""
        await self.terminate_match()
        status, response_text = await self._post_packet(
            self.build_config_packet(PAYLOAD_ACTION_INIT)
        )
        if status != 200 or not response_text:
            return FCReportResult(errno=FC_ERR_NETWORK, errmsg=f"HTTP {status or 'error'}")
        parsed = self.parse_report_response(response_text)
        return parsed or FCReportResult(errno=FC_ERR_NETWORK, errmsg="invalid init response")

    async def terminate_match(self) -> FCReportResult:
        status, response_text = await self._post_packet(
            self.build_config_packet(PAYLOAD_ACTION_TERMINATE)
        )
        if status != 200 or not response_text:
            return FCReportResult(errno=FC_ERR_NETWORK, errmsg=f"HTTP {status or 'error'}")
        parsed = self.parse_report_response(response_text)
        return parsed or FCReportResult(errno=FC_ERR_NETWORK, errmsg="invalid terminate response")

    async def play_frame(self, frame: np.ndarray) -> FCPlayResult:
        """对齐 streaming remote_game_play：发送帧并解析 Controller/Report 应答。"""
        status, response_text = await self._post_packet(self.build_play_packet(frame))
        if status != 200 or not response_text:
            return FCPlayResult(errno=FC_ERR_NETWORK, errmsg=f"HTTP {status or 'error'}")
        return self.parse_play_response(response_text)

    def update_frame_size(self, width: int, height: int) -> None:
        if width > 0:
            self.frame_width = width
        if height > 0:
            self.frame_height = height
