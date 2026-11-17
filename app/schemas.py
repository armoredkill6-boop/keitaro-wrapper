from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    country_code: str = Field(..., min_length=2, max_length=2, description="ISO, e.g. DE")
    keitaro_offer_id: int = Field(..., gt=0)


class CampaignCreatedResponse(BaseModel):
    local_campaign_id: int
    keitaro_campaign_id: int
    name: str
    alias: str


class StreamOfferView(BaseModel):
    id: int
    keitaro_offer_id: int
    weight: float
    weight_pinned: bool
    status: str
    pending_add: bool


class StreamView(BaseModel):
    id: int
    keitaro_stream_id: int
    name: str
    has_offers: bool
    is_dirty: bool
    offers: list[StreamOfferView]


class CampaignEditorView(BaseModel):
    local_campaign_id: int
    keitaro_campaign_id: int
    name: str
    streams: list[StreamView]


class AddOfferRequest(BaseModel):
    keitaro_offer_id: int = Field(..., gt=0)


class PinWeightRequest(BaseModel):
    weight: float = Field(..., ge=0, le=100)


class PushResult(BaseModel):
    ok: bool
    message: str