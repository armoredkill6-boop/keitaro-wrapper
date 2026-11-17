"""Create tables without Alembic (handy if PostgreSQL/Docker not installed)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Base, engine
from app import models  # noqa: F401


def main() -> None:
    Base.metadata.create_all(bind=engine)
    print("OK: tables created in", engine.url)


if __name__ == "__main__":
    main()