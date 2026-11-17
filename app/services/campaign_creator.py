from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from app.config import settings
from app.models import LocalCampaign, LocalStream
from app.services.keitaro_client import KeitaroClient, KeitaroError
from app.services.stream_factory import create_geo_and_offer_streams

_SKIP_CAMPAIGN_FIELDS = frozenset(
    {
        "id",
        "name",
        "alias",
        "token",
        "created_at",
        "updated_at",
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
        "streams",
        "uniques",
    }
)

_COPY_CAMPAIGN_FIELDS = (
    "domain_id",
    "group_id",
    "traffic_source_id",
    "type",
    "state",
    "cookies_ttl",
    "cost_model",
    "cost_value",
    "cost_currency",
    "parameters",
    "uniqueness_method",
    "bind_visitors",
    "postbacks",
)


async def _template_campaign(client: KeitaroClient) -> dict | None:
    campaigns = await client.list_campaigns()
    if not campaigns:
        return None
    first = campaigns[0]
    campaign_id = first.get("id")
    if campaign_id is not None:
        return await client.get_campaign(int(campaign_id))
    return first


def _payload_from_template(name: str, alias: str, template: dict | None) -> dict:
    payload: dict = {"name": name, "alias": alias}
    if not template:
        return payload
    for key in _COPY_CAMPAIGN_FIELDS:
        if key in template and template[key] is not None and key not in _SKIP_CAMPAIGN_FIELDS:
            payload[key] = template[key]
    return payload


async def _create_campaign_flex(client: KeitaroClient, name: str, base_alias: str, template: dict | None) -> dict:
    last: KeitaroError | None = None

    for attempt in range(5):
        suffix = "" if attempt == 0 else f"-{uuid.uuid4().hex[:6]}"
        current_name = name if not suffix else f"{name}{suffix}"
        current_alias = base_alias if not suffix else f"{base_alias}{suffix}"

        variants = [
            _payload_from_template(current_name, current_alias, template),
            {
                "name": current_name,
                "alias": current_alias,
                **{
                    k: template[k]
                    for k in ("domain_id", "group_id", "traffic_source_id")
                    if template and template.get(k)
                },
            },
            {"name": current_name, "alias": current_alias},
        ]
        seen: set[str] = set()
        for payload in variants:
            key = repr(sorted(payload.items()))
            if key in seen:
                continue
            seen.add(key)
            try:
                return await client.create_campaign(payload)
            except KeitaroError as exc:
                last = exc
                body = str(exc.payload or "").lower()
                if exc.status_code in (409, 422) and (
                    "alias" in body or "name has already" in body or "name" in body
                ):
                    break
                continue

    assert last is not None
    raise last


async def create_campaign_with_streams(
    db: Session,
    client: KeitaroClient,
    *,
    name: str,
    country_code: str,
    keitaro_offer_id: int,
) -> LocalCampaign:
    prefix = settings.campaign_name_prefix
    if not name.startswith(prefix):
        name = f"{prefix}{name}"

    country = country_code.upper()
    base_alias = KeitaroClient.slug_alias(name)
    template = await _template_campaign(client)

    created = await _create_campaign_flex(client, name, base_alias, template)
    campaign_id = int(created["id"])
    if created.get("name"):
        name = str(created["name"])

    geo_stream, offer_stream = await create_geo_and_offer_streams(
        client, campaign_id, country, keitaro_offer_id
    )

    local = LocalCampaign(keitaro_campaign_id=campaign_id, name=name)
    db.add(local)
    db.flush()

    db.add(
        LocalStream(
            campaign_id=local.id,
            keitaro_stream_id=int(geo_stream["id"]),
            name=str(geo_stream.get("name", "Geo stream")),
            has_offers=False,
            is_dirty=False,
        )
    )
    db.add(
        LocalStream(
            campaign_id=local.id,
            keitaro_stream_id=int(offer_stream["id"]),
            name=str(offer_stream.get("name", "Offer stream")),
            has_offers=True,
            is_dirty=False,
        )
    )
    db.commit()
    db.refresh(local)
    return local