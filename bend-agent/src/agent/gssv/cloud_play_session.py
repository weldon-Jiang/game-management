"""GSSV 云端 play session：POST play + 轮询 Provisioned（对照 libxsrp xboxseries.cpp）。"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ..core.config import config
from ..core.logger import get_logger
from ..xbox.streaming_credentials import gssv_server_id_for_api
from .client import GssvClient
from .endpoints import GssvEndpoints


def build_play_body(server_id: str) -> Dict[str, Any]:
    """与 streaming/xsplayer.py、libxsrp 一致的 play 请求体。"""
    return {
        "clientSessionId": "",
        "titleId": "",
        "systemUpdateGroup": "",
        "settings": {
            "enableTextToSpeech": False,
            "highContrast": 0,
            "locale": "en-US",
            "nanoVersion": "V3;WebrtcTransport.dll",
            "osName": "windows",
            "sdkType": "web",
            "timezoneOffsetMinutes": 480,
            "useIceConnection": False,
        },
        "serverId": server_id,
        "fallbackRegionNames": [None],
    }


@dataclass
class CloudPlayContext:
    """Provisioned play session 上下文。"""

    session_id: str
    session_path: str
    state: str
    server_id: str
    play_path: str
    raw: Dict[str, Any]


class GssvCloudPlaySession:
    """创建并等待 GSSV play session 进入 Provisioned。"""

    TERMINAL_FAIL_STATES = frozenset({"Failed", "Error", "Terminated"})

    def __init__(self, client: GssvClient, endpoints: GssvEndpoints):
        self.logger = get_logger("gssv_cloud_play")
        self._client = client
        self._endpoints = endpoints

    async def create_and_wait(
        self,
        server_id: str,
        play_path: str,
        *,
        timeout_sec: Optional[float] = None,
    ) -> CloudPlayContext:
        timeout = timeout_sec or float(config.get("gssv.cloud_provision_timeout_sec", 45))
        api_server_id = gssv_server_id_for_api(server_id)
        if not api_server_id:
            raise ValueError("server_id 为空，无法 POST play")
        play_url = self._endpoints.play(play_path)
        body = build_play_body(api_server_id)

        async with await self._client.post(play_url, body, timeout=60) as resp:
            raw_text = await resp.text()
            if resp.status not in (200, 201, 202):
                raise RuntimeError(
                    f"GSSV play POST failed: HTTP {resp.status} {raw_text[:500]}"
                )
            play_ctx = json.loads(raw_text) if raw_text else {}

        session_path = str(play_ctx.get("sessionPath") or "")
        session_id = str(play_ctx.get("sessionId") or "")
        initial_state = str(play_ctx.get("state") or "")
        if not session_path:
            raise RuntimeError(f"GSSV play 响应缺少 sessionPath: {play_ctx}")

        if initial_state == "Provisioned":
            return CloudPlayContext(
                session_id=session_id,
                session_path=session_path,
                state=initial_state,
                server_id=api_server_id,
                play_path=play_path,
                raw=play_ctx,
            )

        final_state = await self._poll_provisioned(session_path, timeout)
        return CloudPlayContext(
            session_id=session_id,
            session_path=session_path,
            state=final_state,
            server_id=api_server_id,
            play_path=play_path,
            raw=play_ctx,
        )

    async def _poll_provisioned(self, session_path: str, timeout_sec: float) -> str:
        url = self._endpoints.state(session_path)
        deadline = time.monotonic() + timeout_sec
        last_state = ""

        while time.monotonic() < deadline:
            async with await self._client.get(url) as resp:
                text = await resp.text()
                if resp.status != 200:
                    raise RuntimeError(f"GSSV state poll HTTP {resp.status}: {text[:300]}")
                data = json.loads(text) if text else {}
                last_state = str(data.get("state") or "")
                if last_state == "Provisioned":
                    self.logger.info("GSSV play session Provisioned: %s", session_path)
                    return last_state
                if last_state in self.TERMINAL_FAIL_STATES:
                    raise RuntimeError(f"GSSV play session 失败: state={last_state} data={data}")

            await asyncio.sleep(1.0)

        raise TimeoutError(
            f"GSSV Provisioned 等待超时 ({timeout_sec}s), last_state={last_state or 'unknown'}"
        )
