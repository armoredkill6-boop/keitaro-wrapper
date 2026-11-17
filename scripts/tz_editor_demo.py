"""Прогон сценария редактора по ТЗ (CLI). Нужен local campaign в SQLite."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import SessionLocal
from app.models import LocalStream
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


async def run(local_id: int, extra_offer: int) -> None:
    db = SessionLocal()
    client = KeitaroClient()
    try:
        campaign = await fetch_and_sync_campaign(db, client, local_id)
        offer_stream = next(s for s in campaign.streams if s.has_offers)
        link = next(o for o in offer_stream.offers if o.status == "active")
        print("1) remove", link.keitaro_offer_id)
        remove_offer(db, offer_stream.id, link.id)
        print("2) bring back")
        offer_stream = db.scalar(
            select(LocalStream).where(LocalStream.id == offer_stream.id).options(selectinload(LocalStream.offers))
        )
        restored = next(o for o in offer_stream.offers if o.keitaro_offer_id == link.keitaro_offer_id)
        bring_back_offer(db, offer_stream.id, restored.id)
        print("3) add offer", extra_offer)
        if not any(o.keitaro_offer_id == extra_offer and o.status == "active" for o in offer_stream.offers):
            add_offer(db, offer_stream.id, extra_offer)
        offer_stream = db.scalar(
            select(LocalStream).where(LocalStream.id == offer_stream.id).options(selectinload(LocalStream.offers))
        )
        primary = min((o for o in offer_stream.offers if o.status == "active"), key=lambda o: o.id)
        pin_offer_weight(db, offer_stream.id, primary.id, 70.0)
        print("4) push")
        await push_stream_to_keitaro(db, client, offer_stream.id)
        print("OK — editor flow completed")
    except (KeitaroError, ValueError) as exc:
        print("FAIL", exc)
        sys.exit(1)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--local-id", type=int, default=2)
    parser.add_argument("--extra-offer", type=int, default=4514, help="second offer id for add/pin demo")
    args = parser.parse_args()
    asyncio.run(run(args.local_id, args.extra_offer))


if __name__ == "__main__":
    main()