import asyncio
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.services.keitaro_client import KeitaroClient
from app.services.stream_factory import _find_template_streams


async def main() -> None:
    client = KeitaroClient()
    t0 = time.time()
    streams = await _find_template_streams(client)
    print("found_streams", len(streams), "sec", round(time.time() - t0, 1))


if __name__ == "__main__":
    asyncio.run(main())