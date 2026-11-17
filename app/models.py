import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class OfferLinkStatus(str, enum.Enum):
    active = "active"
    removed = "removed"  # soft-remove in UI; may still exist in Keitaro until push


class LocalCampaign(Base):
    """Mirror of a Keitaro campaign we manage in the wrapper."""

    __tablename__ = "local_campaigns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    keitaro_campaign_id: Mapped[int] = mapped_column(Integer, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    streams: Mapped[list["LocalStream"]] = relationship(back_populates="campaign", cascade="all, delete-orphan")


class LocalStream(Base):
    __tablename__ = "local_streams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    campaign_id: Mapped[int] = mapped_column(ForeignKey("local_campaigns.id", ondelete="CASCADE"))
    keitaro_stream_id: Mapped[int] = mapped_column(Integer, index=True)
    name: Mapped[str] = mapped_column(String(255), default="")
    has_offers: Mapped[bool] = mapped_column(Boolean, default=False)
    is_dirty: Mapped[bool] = mapped_column(Boolean, default=False)

    campaign: Mapped[LocalCampaign] = relationship(back_populates="streams")
    offers: Mapped[list["StreamOffer"]] = relationship(back_populates="stream", cascade="all, delete-orphan")


class StreamOffer(Base):
    __tablename__ = "stream_offers"
    __table_args__ = (UniqueConstraint("stream_id", "keitaro_offer_id", name="uq_stream_offer"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stream_id: Mapped[int] = mapped_column(ForeignKey("local_streams.id", ondelete="CASCADE"), index=True)
    keitaro_offer_id: Mapped[int] = mapped_column(Integer)
    weight: Mapped[float] = mapped_column(Float, default=0.0)
    weight_pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(32), default=OfferLinkStatus.active.value)
    pending_add: Mapped[bool] = mapped_column(Boolean, default=False)

    stream: Mapped[LocalStream] = relationship(back_populates="offers")