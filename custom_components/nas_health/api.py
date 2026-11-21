"""Small client for the read-only nas-health HTTP API (/api/v1)."""

from __future__ import annotations

from typing import Any

import aiohttp


class NasHealthError(Exception):
    """The API could not be reached or answered with something unexpected."""


class NasHealthApi:
    def __init__(self, session: aiohttp.ClientSession, base_url: str) -> None:
        self._session = session
        self.base_url = base_url.rstrip("/")

    async def _get(self, path: str) -> dict[str, Any]:
        url = f"{self.base_url}{path}"
        try:
            async with self._session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
                if resp.status != 200:
                    raise NasHealthError(f"HTTP {resp.status} from {path}")
                data = await resp.json(content_type=None)
        except (aiohttp.ClientError, TimeoutError, ValueError) as exc:
            raise NasHealthError(f"{path}: {exc.__class__.__name__}") from exc
        if not isinstance(data, dict):
            raise NasHealthError(f"{path}: not a JSON object")
        return data

    async def summary(self) -> dict[str, Any]:
        data = await self._get("/api/v1/summary")
        if "overall" not in data:
            raise NasHealthError("not a nas-health API (no 'overall')")
        return data

    async def checks(self) -> list[dict[str, Any]]:
        return (await self._get("/api/v1/checks")).get("checks", [])

    async def updates(self) -> dict[str, Any]:
        return await self._get("/api/v1/updates")
