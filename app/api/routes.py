import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import settings
from app.database import get_db
from app.models import LocalCampaign, LocalStream
from app.schemas import (
    AddOfferRequest,
    CampaignCreatedResponse,
    CampaignEditorView,
    CreateCampaignRequest,
    PinWeightRequest,
    PushResult,
    StreamOfferView,
    StreamView,
)
from app.services.campaign_creator import create_campaign_with_streams
from app.services.editor import (
    add_offer,
    bring_back_offer,
    cancel_stream_draft,
    fetch_and_sync_campaign,
    pin_offer_weight,
    push_stream_to_keitaro,
    remove_offer,
)
from app.services.keitaro_client import KeitaroClient, KeitaroError

router = APIRouter()
keitaro = KeitaroClient()


def _raise_keitaro(exc: KeitaroError) -> None:
    detail = str(exc)
    if exc.payload:
        detail = f"{detail} | {exc.payload}"
    raise HTTPException(status_code=502, detail=detail) from exc


def _campaign_view(campaign: LocalCampaign) -> CampaignEditorView:
    return CampaignEditorView(
        local_campaign_id=campaign.id,
        keitaro_campaign_id=campaign.keitaro_campaign_id,
        name=campaign.name,
        streams=[
            StreamView(
                id=s.id,
                keitaro_stream_id=s.keitaro_stream_id,
                name=s.name,
                has_offers=s.has_offers,
                is_dirty=s.is_dirty,
                offers=[
                    StreamOfferView(
                        id=o.id,
                        keitaro_offer_id=o.keitaro_offer_id,
                        weight=o.weight,
                        weight_pinned=o.weight_pinned,
                        status=o.status,
                        pending_add=o.pending_add,
                    )
                    for o in s.offers
                ],
            )
            for s in campaign.streams
        ],
    )


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/keitaro/offers")
async def list_keitaro_offers() -> list[dict]:
    try:
        return await keitaro.list_offers()
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/campaigns", response_model=CampaignCreatedResponse)
async def create_campaign(body: CreateCampaignRequest, db: Session = Depends(get_db)) -> CampaignCreatedResponse:
    try:
        local = await create_campaign_with_streams(
            db,
            keitaro,
            name=body.name,
            country_code=body.country_code,
            keitaro_offer_id=body.keitaro_offer_id,
        )
    except KeitaroError as exc:
        _raise_keitaro(exc)
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Не достучались до Keitaro ({settings.keitaro_base_url}): {exc}",
        ) from exc

    return CampaignCreatedResponse(
        local_campaign_id=local.id,
        keitaro_campaign_id=local.keitaro_campaign_id,
        name=local.name,
        alias=KeitaroClient.slug_alias(local.name),
    )


@router.get("/campaigns")
def list_local_campaigns(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.scalars(select(LocalCampaign).order_by(LocalCampaign.id.desc())).all()
    return [{"id": r.id, "keitaro_campaign_id": r.keitaro_campaign_id, "name": r.name} for r in rows]


@router.get("/campaigns/{local_id}", response_model=CampaignEditorView)
def get_campaign(local_id: int, db: Session = Depends(get_db)) -> CampaignEditorView:
    campaign = db.scalar(
        select(LocalCampaign)
        .where(LocalCampaign.id == local_id)
        .options(selectinload(LocalCampaign.streams).selectinload(LocalStream.offers))
    )
    if not campaign:
        raise HTTPException(status_code=404, detail="Campaign not found")
    return _campaign_view(campaign)


@router.post("/campaigns/{local_id}/fetch", response_model=CampaignEditorView)
async def fetch_campaign(local_id: int, db: Session = Depends(get_db)) -> CampaignEditorView:
    try:
        campaign = await fetch_and_sync_campaign(db, keitaro, local_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return _campaign_view(campaign)


@router.post("/streams/{stream_id}/offers", response_model=StreamView)
def api_add_offer(stream_id: int, body: AddOfferRequest, db: Session = Depends(get_db)) -> StreamView:
    try:
        stream = add_offer(db, stream_id, body.keitaro_offer_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamView(
        id=stream.id,
        keitaro_stream_id=stream.keitaro_stream_id,
        name=stream.name,
        has_offers=stream.has_offers,
        is_dirty=stream.is_dirty,
        offers=[
            StreamOfferView(
                id=o.id,
                keitaro_offer_id=o.keitaro_offer_id,
                weight=o.weight,
                weight_pinned=o.weight_pinned,
                status=o.status,
                pending_add=o.pending_add,
            )
            for o in stream.offers
        ],
    )


@router.delete("/streams/{stream_id}/offers/{link_id}", response_model=StreamView)
def api_remove_offer(stream_id: int, link_id: int, db: Session = Depends(get_db)) -> StreamView:
    try:
        stream = remove_offer(db, stream_id, link_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamView(
        id=stream.id,
        keitaro_stream_id=stream.keitaro_stream_id,
        name=stream.name,
        has_offers=stream.has_offers,
        is_dirty=stream.is_dirty,
        offers=[
            StreamOfferView(
                id=o.id,
                keitaro_offer_id=o.keitaro_offer_id,
                weight=o.weight,
                weight_pinned=o.weight_pinned,
                status=o.status,
                pending_add=o.pending_add,
            )
            for o in stream.offers
        ],
    )


@router.post("/streams/{stream_id}/offers/{link_id}/bring-back", response_model=StreamView)
def api_bring_back(stream_id: int, link_id: int, db: Session = Depends(get_db)) -> StreamView:
    try:
        stream = bring_back_offer(db, stream_id, link_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamView(
        id=stream.id,
        keitaro_stream_id=stream.keitaro_stream_id,
        name=stream.name,
        has_offers=stream.has_offers,
        is_dirty=stream.is_dirty,
        offers=[
            StreamOfferView(
                id=o.id,
                keitaro_offer_id=o.keitaro_offer_id,
                weight=o.weight,
                weight_pinned=o.weight_pinned,
                status=o.status,
                pending_add=o.pending_add,
            )
            for o in stream.offers
        ],
    )


@router.post("/streams/{stream_id}/offers/{link_id}/pin", response_model=StreamView)
def api_pin(stream_id: int, link_id: int, body: PinWeightRequest, db: Session = Depends(get_db)) -> StreamView:
    try:
        stream = pin_offer_weight(db, stream_id, link_id, body.weight)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamView(
        id=stream.id,
        keitaro_stream_id=stream.keitaro_stream_id,
        name=stream.name,
        has_offers=stream.has_offers,
        is_dirty=stream.is_dirty,
        offers=[
            StreamOfferView(
                id=o.id,
                keitaro_offer_id=o.keitaro_offer_id,
                weight=o.weight,
                weight_pinned=o.weight_pinned,
                status=o.status,
                pending_add=o.pending_add,
            )
            for o in stream.offers
        ],
    )


@router.post("/streams/{stream_id}/cancel", response_model=StreamView)
def api_cancel(stream_id: int, db: Session = Depends(get_db)) -> StreamView:
    try:
        stream = cancel_stream_draft(db, stream_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return StreamView(
        id=stream.id,
        keitaro_stream_id=stream.keitaro_stream_id,
        name=stream.name,
        has_offers=stream.has_offers,
        is_dirty=stream.is_dirty,
        offers=[
            StreamOfferView(
                id=o.id,
                keitaro_offer_id=o.keitaro_offer_id,
                weight=o.weight,
                weight_pinned=o.weight_pinned,
                status=o.status,
                pending_add=o.pending_add,
            )
            for o in stream.offers
        ],
    )


@router.post("/streams/{stream_id}/push", response_model=PushResult)
async def api_push(stream_id: int, db: Session = Depends(get_db)) -> PushResult:
    try:
        await push_stream_to_keitaro(db, keitaro, stream_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except KeitaroError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return PushResult(ok=True, message="Pushed to Keitaro")