"""
FC Server 远程场景识别客户端
============================

对齐 streaming/payload.py 的 PayloadFrame(GRAPH) 协议，
作为 step4 本地模板匹配的备选决策层。
"""

import json
from base64 import b64encode
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import cv2
import numpy as np

from ..core.logger import get_logger

PAYLOAD_TYPE_FRAME = 1
PAYLOAD_TYPE_SCENE = 6
PAYLOAD_ACTION_GRAPH = 1

KEY_TYPE = "type"
KEY_ACTION = "action"
KEY_SESSION = "session"
KEY_ERRNO = "errno"
KEY_ERRMSG = "errmsg"
KEY_MAIL = "mail"
KEY_CONTROLLER_INDEX = "controller_index"
KEY_FRAME = "frame"
KEY_FRAME_OBJECTS = "frame_objects"
KEY_SCENE = "scene"
KEY_CONTROLLER = "controller"


@dataclass
class FCSceneResult:
    errno: int = 0
    scene_id: int = -1
    controller_actions: List[Dict[str, Any]] = field(default_factory=list)
    errmsg: str = ""


class FCSceneClient:
    """HTTP client for remote scene recognition via FC server."""

    def __init__(
        self,
        host: str,
        port: int,
        username: str,
        session_token: str = "",
        gamepad_index: int = 0,
    ):
        self.logger = get_logger("fc_scene_client")
        self.host = host
        self.port = port
        self.username = username
        self.session_token = session_token
        self.gamepad_index = gamepad_index
        self._api_url = f"http://{host}:{port}/api/payload"

    def build_graph_packet(self, frame: np.ndarray) -> str:
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
        if not ok:
            raise ValueError("Failed to encode frame for FC payload")

        packet = {
            KEY_TYPE: PAYLOAD_TYPE_FRAME,
            KEY_ACTION: PAYLOAD_ACTION_GRAPH,
            KEY_SESSION: self.session_token,
            KEY_ERRNO: 0,
            KEY_ERRMSG: "",
            KEY_MAIL: self.username,
            KEY_CONTROLLER_INDEX: self.gamepad_index,
            KEY_FRAME: b64encode(encoded.tobytes()).decode("utf-8"),
            KEY_FRAME_OBJECTS: [],
        }
        return json.dumps(packet, ensure_ascii=False)

    def parse_scene_response(self, response_text: str) -> Optional[FCSceneResult]:
        if not response_text:
            return None
        try:
            packet = json.loads(response_text)
            if packet.get(KEY_TYPE) != PAYLOAD_TYPE_SCENE:
                return None
            return FCSceneResult(
                errno=int(packet.get(KEY_ERRNO, -1)),
                scene_id=int(packet.get(KEY_SCENE, -1)),
                controller_actions=list(packet.get(KEY_CONTROLLER, []) or []),
                errmsg=str(packet.get(KEY_ERRMSG, "")),
            )
        except (json.JSONDecodeError, TypeError, ValueError) as exc:
            self.logger.error(f"Failed to parse FC scene response: {exc}")
            return None

    async def recognize_scene(self, frame: np.ndarray) -> FCSceneResult:
        packet = self.build_graph_packet(frame)
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.post(self._api_url, data=packet) as resp:
                    if resp.status != 200:
                        self.logger.error(f"FC server HTTP {resp.status}")
                        return FCSceneResult(errno=-1, errmsg=f"HTTP {resp.status}")

                    body = await resp.json()
                    result_obj = body.get("result", body)
                    response_text = json.dumps(result_obj, ensure_ascii=False)
        except Exception as exc:
            self.logger.error(f"FC scene request failed: {exc}")
            return FCSceneResult(errno=-1, errmsg=str(exc))

        parsed = self.parse_scene_response(response_text)
        return parsed or FCSceneResult(errno=-1, errmsg="invalid response")

    async def recognize_scene_id(self, frame: np.ndarray) -> Tuple[int, List[Dict[str, Any]]]:
        result = await self.recognize_scene(frame)
        if result.errno != 0:
            return -1, []
        return result.scene_id, result.controller_actions
