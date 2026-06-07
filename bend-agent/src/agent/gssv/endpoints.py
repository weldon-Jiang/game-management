"""GSSV URL builders — dynamic baseUri, no hardcoded region."""


class GssvEndpoints:
    def __init__(self, base_uri: str):
        self.base_uri = (base_uri or "").rstrip("/")

    def servers_home(self) -> str:
        return f"{self.base_uri}/v6/servers/home"

    def play(self, play_path: str) -> str:
        return f"{self.base_uri}/{play_path.lstrip('/')}"

    def state(self, session_path: str) -> str:
        return f"{self.base_uri}/{session_path.lstrip('/')}/state"

    def connect(self, session_path: str) -> str:
        return f"{self.base_uri}/{session_path.lstrip('/')}/connect"

    def sdp(self, session_path: str) -> str:
        return f"{self.base_uri}/{session_path.lstrip('/')}/sdp"

    def ice(self, session_path: str) -> str:
        return f"{self.base_uri}/{session_path.lstrip('/')}/ice"

    def power(self, server_id: str) -> str:
        return f"{self.base_uri}/v6/servers/home/{server_id}/power"
