from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import LocalCampaign, LocalStream, OfferLinkStatus, StreamOffer
from app.services.keitaro_client import KeitaroClient
from app.services.weights import recalculate_weights


def _stream_has_offers(stream: dict) -> bool:
    offers = stream.get("offers") or []
    return len(offers) > 0


def _offer_ids_from_keitaro(stream: dict) -> list[tuple[int, float, bool]]:
    result: list[tuple[int, float, bool]] = []
    for item in stream.get("offers") or []:
        offer_id = int(item.get("offer_id") or item.get("id"))
        share = float(item.get("share") or item.get("weight") or 0)
        result.append((offer_id, share, False))
    return result


async def fetch_and_sync_campaign(db: Session, client: KeitaroClient, local_id: int) -> LocalCampaign:
    campaign = db.scalar(
        select(LocalCampaign)
        .where(LocalCampaign.id == local_id)
        .options(selectinload(LocalCampaign.streams).selectinload(LocalStream.offers))
    )
    if not campaign:
        raise ValueError("Campaign not found")

    streams = await client.get_campaign_streams(campaign.keitaro_campaign_id)
    known = {s.keitaro_stream_id: s for s in campaign.streams}

    for kt_stream in streams:
        stream_id = int(kt_stream["id"])
        has_offers = _stream_has_offers(kt_stream)
        local_stream = known.get(stream_id)
        if not local_stream:
            local_stream = LocalStream(
                campaign_id=campaign.id,
                keitaro_stream_id=stream_id,
                name=str(kt_stream.get("name", f"Stream {stream_id}")),
                has_offers=has_offers,
                is_dirty=False,
            )
            db.add(local_stream)
            db.flush()
            campaign.streams.append(local_stream)

        local_stream.name = str(kt_stream.get("name", local_stream.name))
        local_stream.has_offers = has_offers

        if not has_offers:
            continue

        kt_offers = {oid: (share, pinned) for oid, share, pinned in _offer_ids_from_keitaro(kt_stream)}
        local_by_offer = {o.keitaro_offer_id: o for o in local_stream.offers}

        for oid, (share, _) in kt_offers.items():
            row = local_by_offer.get(oid)
            if row is None:
                db.add(
                    StreamOffer(
                        stream_id=local_stream.id,
                        keitaro_offer_id=oid,
                        weight=share,
                        status=OfferLinkStatus.active.value,
                        pending_add=False,
                    )
                )
            elif row.status == OfferLinkStatus.active.value and not row.pending_add and not local_stream.is_dirty:
                row.weight = share

        for oid, row in local_by_offer.items():
            if oid not in kt_offers and row.status == OfferLinkStatus.active.value and not row.pending_add:
                row.status = OfferLinkStatus.removed.value
                row.weight = 0.0

    db.commit()
    db.refresh(campaign)
    return campaign


def add_offer(db: Session, stream_id: int, keitaro_offer_id: int) -> LocalStream:
    stream = db.scalar(
        select(LocalStream)
        .where(LocalStream.id == stream_id)
        .options(selectinload(LocalStream.offers))
    )
    if not stream or not stream.has_offers:
        raise ValueError("Stream not found or has no offers")

    for offer in stream.offers:
        if offer.keitaro_offer_id == keitaro_offer_id and offer.status == OfferLinkStatus.active.value:
            raise ValueError("Offer already in stream")

    stale = next((o for o in stream.offers if o.keitaro_offer_id == keitaro_offer_id), None)
    if stale and stale.status == OfferLinkStatus.removed.value:
        stale.status = OfferLinkStatus.active.value
        stale.pending_add = True
    else:
        db.add(
            StreamOffer(
                stream_id=stream.id,
                keitaro_offer_id=keitaro_offer_id,
                weight=0.0,
                status=OfferLinkStatus.active.value,
                pending_add=True,
            )
        )

    db.flush()
    active = [o for o in stream.offers if o.status == OfferLinkStatus.active.value]
    recalculate_weights(active)
    stream.is_dirty = True
    db.commit()
    db.refresh(stream)
    return stream


def remove_offer(db: Session, stream_id: int, link_id: int) -> LocalStream:
    stream = db.scalar(
        select(LocalStream)
        .where(LocalStream.id == stream_id)
        .options(selectinload(LocalStream.offers))
    )
    if not stream:
        raise ValueError("Stream not found")

    offer = next((o for o in stream.offers if o.id == link_id), None)
    if not offer:
        raise ValueError("Offer link not found")

    offer.status = OfferLinkStatus.removed.value
    offer.weight = 0.0
    offer.pending_add = False
    recalculate_weights([o for o in stream.offers if o.status == OfferLinkStatus.active.value])
    stream.is_dirty = True
    db.commit()
    db.refresh(stream)
    return stream


def bring_back_offer(db: Session, stream_id: int, link_id: int) -> LocalStream:
    stream = db.scalar(
        select(LocalStream)
        .where(LocalStream.id == stream_id)
        .options(selectinload(LocalStream.offers))
    )
    if not stream:
        raise ValueError("Stream not found")
    offer = next((o for o in stream.offers if o.id == link_id), None)
    if not offer or offer.status != OfferLinkStatus.removed.value:
        raise ValueError("Offer is not removed")

    offer.status = OfferLinkStatus.active.value
    offer.pending_add = True
    recalculate_weights([o for o in stream.offers if o.status == OfferLinkStatus.active.value])
    stream.is_dirty = True
    db.commit()
    db.refresh(stream)
    return stream


def pin_offer_weight(db: Session, stream_id: int, link_id: int, weight: float) -> LocalStream:
    stream = db.scalar(
        select(LocalStream)
        .where(LocalStream.id == stream_id)
        .options(selectinload(LocalStream.offers))
    )
    if not stream:
        raise ValueError("Stream not found")
    offer = next((o for o in stream.offers if o.id == link_id), None)
    if not offer or offer.status != OfferLinkStatus.active.value:
        raise ValueError("Offer not active")

    offer.weight = weight
    offer.weight_pinned = True
    recalculate_weights([o for o in stream.offers if o.status == OfferLinkStatus.active.value])
    stream.is_dirty = True
    db.commit()
    db.refresh(stream)
    return stream


def cancel_stream_draft(db: Session, stream_id: int) -> LocalStream:
    stream = db.scalar(
        select(LocalStream)
        .where(LocalStream.id == stream_id)
        .options(selectinload(LocalStream.offers))
    )
    if not stream:
        raise ValueError("Stream not found")

    to_delete = [o for o in stream.offers if o.pending_add]
    for offer in to_delete:
        db.delete(offer)

    for offer in stream.offers:
        if offer.pending_add:
            continue
        offer.pending_add = False

    stream.is_dirty = False
    db.commit()
    db.refresh(stream)
    return stream


async def push_stream_to_keitaro(db: Session, client: KeitaroClient, stream_id: int) -> LocalStream:
    stream = db.scalar(
        select(LocalStream)
        .where(LocalStream.id == stream_id)
        .options(selectinload(LocalStream.offers))
    )
    if not stream or not stream.has_offers:
        raise ValueError("Stream not found")

    active_offers = [o for o in stream.offers if o.status == OfferLinkStatus.active.value]
    if not active_offers:
        raise ValueError("No active offers to push")

    await client.update_stream(
        stream.keitaro_stream_id,
        {
            "offers": [
                {"offer_id": o.keitaro_offer_id, "share": int(round(o.weight)), "state": "active"}
                for o in active_offers
            ],
            "schema": "landings",
            "action_type": "http",
        },
    )

    for offer in list(stream.offers):
        if offer.status == OfferLinkStatus.removed.value:
            db.delete(offer)
        else:
            offer.pending_add = False

    stream.is_dirty = False
    db.commit()
    db.refresh(stream)
    return stream