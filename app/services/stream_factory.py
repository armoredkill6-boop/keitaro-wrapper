from __future__ import annotations

import copy

from app.config import settings
from app.services.keitaro_client import KeitaroClient, KeitaroError

_STRIP_STREAM_KEYS = frozenset(
    {
        "id",
        "campaign_id",
        "clicks",
        "leads",
        "conversions",
        "revenue",
        "cost",
        "profit",
        "roi",
        "cr",
        "epc",
        "cpc",
        "uniques",
        "created_at",
        "updated_at",
    }
)


def _stream_has_offers(stream: dict) -> bool:
    return bool(stream.get("offers"))


def _sanitize_stream_payload(stream: dict, campaign_id: int) -> dict:
    payload = copy.deepcopy(stream)
    for key in list(payload.keys()):
        if key in _STRIP_STREAM_KEYS:
            payload.pop(key, None)
    payload["campaign_id"] = campaign_id
    payload.pop("filters", None)
    return payload


def _country_filters(country: str) -> list[dict]:
    """Keitaro on tlgk.host: only filter name 'country', NOT 'geo'."""
    return [{"name": "country", "mode": "accept", "payload": [country]}]


async def _find_template_streams(client: KeitaroClient) -> list[dict]:
    for campaign in await client.list_campaigns():
        cid = campaign.get("id")
        if cid is None:
            continue
        streams = await client.get_campaign_streams(int(cid))
        if len(streams) >= 2:
            return streams
    for campaign in await client.list_campaigns():
        cid = campaign.get("id")
        if cid is None:
            continue
        streams = await client.get_campaign_streams(int(cid))
        if streams:
            return streams
    return []


async def _create_stream_try(client: KeitaroClient, variants: list[dict]) -> dict:
    last: KeitaroError | None = None
    for payload in variants:
        try:
            return await client.create_stream(payload)
        except KeitaroError as exc:
            last = exc
            if "geo" in str(exc.payload or "").lower():
                continue
    assert last is not None
    raise last


async def _create_geo_stream(client: KeitaroClient, campaign_id: int, country: str) -> dict:
    url = settings.google_redirect_url
    base = {
        "campaign_id": campaign_id,
        "name": f"Geo {country} -> Google",
        "type": "regular",
        "weight": 100,
        "state": "active",
    }
    # tlgk.host: schema redirect + action_type http (not "redirect")
    variants = [
        {
            **base,
            "schema": "redirect",
            "action_type": "http",
            "action_payload": url,
            "filters": _country_filters(country),
        },
        {
            **base,
            "schema": "redirect",
            "action_type": "http",
            "action_payload": url,
            "filters": [{"name": "country", "mode": "accept", "payload": [country]}],
        },
    ]
    return await _create_stream_try(client, variants)


async def _create_offer_stream(client: KeitaroClient, campaign_id: int, offer_id: int) -> dict:
    base = {
        "campaign_id": campaign_id,
        "name": "Offer stream",
        "type": "regular",
        "weight": 100,
        "state": "active",
    }
    variants = [
        {
            **base,
            "schema": "landings",
            "action_type": "http",
            "offers": [{"offer_id": offer_id, "share": 100, "state": "active"}],
        },
        {
            **base,
            "schema": "offers",
            "action_type": "http",
            "offers": [{"offer_id": offer_id, "share": 100}],
        },
        {
            **base,
            "type": "default",
            "schema": "landings_offers",
            "action_type": "do_nothing",
            "offers": [{"offer_id": offer_id, "share": 100}],
        },
    ]
    return await _create_stream_try(client, variants)


async def create_geo_and_offer_streams(
    client: KeitaroClient,
    campaign_id: int,
    country: str,
    offer_id: int,
) -> tuple[dict, dict]:
    country = country.upper()

    try:
        geo = await _create_geo_stream(client, campaign_id, country)
        offer = await _create_offer_stream(client, campaign_id, offer_id)
        return geo, offer
    except KeitaroError:
        pass

    url = settings.google_redirect_url
    template_streams = await _find_template_streams(client)
    if template_streams:
        geo_tpl = next((s for s in template_streams if not _stream_has_offers(s)), template_streams[0])
        offer_tpl = next((s for s in template_streams if _stream_has_offers(s)), template_streams[-1])

        geo_payload = _sanitize_stream_payload(geo_tpl, campaign_id)
        geo_payload["name"] = f"Geo {country} -> Google"
        geo_payload["type"] = "regular"
        geo_payload["schema"] = "redirect"
        geo_payload["action_type"] = "http"
        geo_payload["action_payload"] = url
        geo_payload["filters"] = _country_filters(country)

        offer_payload = _sanitize_stream_payload(offer_tpl, campaign_id)
        offer_payload["name"] = "Offer stream"
        offer_payload["type"] = "regular"
        offer_payload["schema"] = "landings"
        offer_payload["action_type"] = "http"
        offer_payload["offers"] = [{"offer_id": offer_id, "share": 100, "state": "active"}]
        offer_payload.pop("filters", None)

        geo = await client.create_stream(geo_payload)
        offer = await client.create_stream(offer_payload)
        return geo, offer

    raise KeitaroError("Could not create streams for campaign")