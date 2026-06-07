"""GSSV HTTP client with dynamic baseUri and Bearer auth."""

from typing import Any, Dict, Optional

import aiohttp

from ..core.logger import get_logger
from .device_info import build_device_info
from .endpoints import GssvEndpoints


class GssvClient:
    """Shared aiohttp client for GSSV APIs."""

    def __init__(
        self,
        base_uri: str,
        bearer_token: str,
        *,
        contract_version: str = "1",
    ):
        self.logger = get_logger("gssv_client")
        self.endpoints = GssvEndpoints(base_uri)
        self._token = bearer_token
        self._contract_version = contract_version
        self._session: Optional[aiohttp.ClientSession] = None

    async def _http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "x-xbl-contract-version": self._contract_version,
            "X-MS-Device-Info": build_device_info(),
        }

    async def get(self, url: str, *, timeout: int = 30) -> aiohttp.ClientResponse:
        session = await self._http()
        return await session.get(
            url,
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=timeout),
        )

    async def post(
        self,
        url: str,
        data: Optional[Dict[str, Any]] = None,
        *,
        timeout: int = 30,
    ) -> aiohttp.ClientResponse:
        session = await self._http()
        return await session.post(
            url,
            json=data or {},
            headers=self._headers(),
            timeout=aiohttp.ClientTimeout(total=timeout),
        )

    async def get_json(self, url: str) -> Any:
        async with await self.get(url) as resp:
            if resp.status != 200:
                text = await resp.text()
                raise RuntimeError(f"GSSV GET {url} failed: {resp.status} {text}")
            return await resp.json()

    async def list_home_servers(self) -> list:
        data = await self.get_json(self.endpoints.servers_home())
        if isinstance(data, list):
            return data
        return data.get("results", data.get("servers", []))

    async def power_on(self, server_id: str) -> bool:
        url = self.endpoints.power(server_id)
        async with await self.post(url, {"action": "on"}) as resp:
            return resp.status in (200, 201, 202, 204)

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
