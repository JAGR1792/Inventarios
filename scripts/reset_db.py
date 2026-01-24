from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inventarios.db import create_engine_from_url
from inventarios.models import Base
from inventarios.settings import Settings


def main() -> int:
    settings = Settings()
    engine = create_engine_from_url(settings.DATABASE_URL)

    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    print("OK: database reset")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
