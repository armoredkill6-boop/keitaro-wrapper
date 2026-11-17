"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-11-17
"""

from alembic import op
import sqlalchemy as sa

revision = "001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "local_campaigns",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("keitaro_campaign_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_local_campaigns_keitaro_campaign_id", "local_campaigns", ["keitaro_campaign_id"], unique=True)

    op.create_table(
        "local_streams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("campaign_id", sa.Integer(), sa.ForeignKey("local_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keitaro_stream_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("has_offers", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_dirty", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.create_index("ix_local_streams_keitaro_stream_id", "local_streams", ["keitaro_stream_id"])

    op.create_table(
        "stream_offers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stream_id", sa.Integer(), sa.ForeignKey("local_streams.id", ondelete="CASCADE"), nullable=False),
        sa.Column("keitaro_offer_id", sa.Integer(), nullable=False),
        sa.Column("weight", sa.Float(), nullable=False, server_default="0"),
        sa.Column("weight_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("pending_add", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.UniqueConstraint("stream_id", "keitaro_offer_id", name="uq_stream_offer"),
    )
    op.create_index("ix_stream_offers_stream_id", "stream_offers", ["stream_id"])


def downgrade() -> None:
    op.drop_table("stream_offers")
    op.drop_table("local_streams")
    op.drop_table("local_campaigns")