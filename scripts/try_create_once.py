import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.services.campaign_creator import create_campaign_with_streams
from app.services.keitaro_client import KeitaroClient, KeitaroError


async def main() -> None:
    name = sys.argv[1] if len(sys.argv) > 1 else "pe4514_script_test"
    client = KeitaroClient()
    db = SessionLocal()
    t0 = time.time()
    try:
        local = await create_campaign_with_streams(
            db,
            client,
            name=name,
            country_code="PE",
            keitaro_offer_id=4514,
        )
        print(f"OK keitaro={local.keitaro_campaign_id} name={local.name} streams={len(local.streams)}")
        print(f"time_sec={time.time() - t0:.1f}")
    except KeitaroError as exc:
        print("KEITARO_ERROR", exc)
        print("payload", exc.payload)
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())