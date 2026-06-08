"""通过 GSSV GET /v6/servers/home 获取云端主机列表。"""

from typing import Any, List, Optional

from ..auth.api import StreamingCredentials
from ..core.logger import get_logger
from ..gssv.client import GssvClient
from .models import ConsoleTarget


class GssvDiscovery:
    def __init__(self):
        self.logger = get_logger("gssv_discovery")

    def _client(self, credentials: StreamingCredentials) -> Optional[GssvClient]:
        base = getattr(credentials, "gssv_base_uri", None)
        token = getattr(credentials, "gs_token", None)
        if not base or not token:
            xbox_tokens = credentials.xbox_tokens
            if xbox_tokens:
                base = getattr(xbox_tokens, "gssv_base_uri", None) or getattr(
                    xbox_tokens, "base_uri", None
                )
                token = getattr(xbox_tokens, "access_token", None) or getattr(
                    xbox_tokens, "gs_token", None
                )
        if not base or not token:
            return None
        return GssvClient(base, token)

    async def list_consoles(self, credentials: StreamingCredentials) -> List[ConsoleTarget]:
        client = self._client(credentials)
        if not client:
            return []
        try:
            servers = await client.list_home_servers()
            result = []
            for s in servers:
                result.append(
                    ConsoleTarget(
                        id=s.get("serverId") or s.get("id", ""),
                        name=s.get("name", "Xbox"),
                        server_id=s.get("serverId") or s.get("id", ""),
                        live_id=s.get("liveId", ""),
                        ip_address=s.get("ipAddress", ""),
                        mac_address=s.get("macAddress", ""),
                        power_state=s.get("powerState", ""),
                        console_type=s.get("consoleType", ""),
                        play_path=s.get("playPath", "v5/sessions/home/play"),
                    )
                )
            return result
        except Exception as exc:
            self.logger.error("GSSV list_consoles failed: %s", exc)
            return []
        finally:
            if client:
                await client.close()
