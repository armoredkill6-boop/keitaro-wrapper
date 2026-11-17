from __future__ import annotations

import re
from typing import Any

import httpx

from app.config import settings


class KeitaroError(Exception):
    def __init__(self, message: str, status_code: int | None = None, payload: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.payload = payload


def _as_list(data: Any) -> list[dict]:
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        for key in ("data", "rows", "items", "campaigns", "offers"):
            if isinstance(data.get(key), list):
                return data[key]
    return []


class KeitaroClient:
    def __init__(self) -> None:
        base = settings.keitaro_base_url.rstrip("/")
        self._base = base
        self._api = f"{base}/admin_api/v1"
        self._headers = {
            "Api-Key": settings.keitaro_api_key,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> Any:
        if not settings.keitaro_api_key:
            raise KeitaroError("KEITARO_API_KEY is not set in .env")
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.request(
                method,
                f"{self._api}{path}",
                headers=self._headers,
                json=json,
                params=params,
            )
        if response.status_code >= 400:
            raise KeitaroError(
                f"Keitaro API {method} {path} failed",
                status_code=response.status_code,
                payload=response.text,
            )
        if not response.content:
            return None
        return response.json()

    async def _try_get_list(self, path: str, params: dict | None = None) -> list[dict]:
        try:
            data = await self._request("GET", path, params=params)
            return _as_list(data)
        except KeitaroError:
            return []

    async def list_domains(self) -> list[dict]:
        return await self._try_get_list("/domains")

    async def list_groups(self) -> list[dict]:
        for path, params in (
            ("/groups", {"type": "campaigns"}),
            ("/groups", {"type": "campaign"}),
            ("/campaign_groups", None),
            ("/groups", None),
        ):
            rows = await self._try_get_list(path, params=params)
            if rows:
                return rows
        return []

    async def list_traffic_sources(self) -> list[dict]:
        return await self._try_get_list("/traffic_sources")

    async def list_offers(self) -> list[dict]:
        data = await self._request("GET", "/offers")
        return _as_list(data)

    async def list_campaigns(self) -> list[dict]:
        data = await self._request("GET", "/campaigns")
        return _as_list(data)

    async def get_campaign(self, campaign_id: int) -> dict:
        return await self._request("GET", f"/campaigns/{campaign_id}")

    async def get_campaign_streams(self, campaign_id: int) -> list[dict]:
        paths = (
            f"/campaigns/{campaign_id}/streams",
            f"/streams?campaign_id={campaign_id}",
        )
        last: KeitaroError | None = None
        for path in paths:
            try:
                data = await self._request("GET", path)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict):
                    rows = data.get("streams") or data.get("data")
                    if isinstance(rows, list):
                        return rows
            except KeitaroError as exc:
                last = exc
        if last:
            raise last
        return []

    async def create_campaign(self, payload: dict) -> dict:
        return await self._request("POST", "/campaigns", json=payload)

    async def create_stream(self, payload: dict) -> dict:
        try:
            return await self._request("POST", "/streams", json=payload)
        except KeitaroError as exc:
            if exc.status_code in (404, 405):
                return await self._request("POST", "/streams/create", json=payload)
            raise

    async def update_stream(self, stream_id: int, payload: dict) -> dict:
        try:
            return await self._request("PUT", f"/streams/{stream_id}", json=payload)
        except KeitaroError as exc:
            if exc.status_code in (404, 405, 422):
                return await self._request("POST", f"/streams/{stream_id}", json=payload)
            raise

    @staticmethod
    def slug_alias(name: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
        return slug[:64] or "campaign"