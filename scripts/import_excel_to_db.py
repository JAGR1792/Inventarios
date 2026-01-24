from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from inventarios.db import create_engine_from_url, init_db, make_session_factory, session_scope
from inventarios.excel_import import ExcelImporter
from inventarios.repos import ProductRepo
from inventarios.settings import Settings


def main() -> int:
    settings = Settings()
    settings.ensure_instance()

    engine = create_engine_from_url(settings.DATABASE_URL)
    init_db(engine)
    sf = make_session_factory(engine)

    xlsx = Path(settings.EXCEL_IMPORT_PATH)
    if not xlsx.is_absolute():
        xlsx = (ROOT / xlsx).resolve()

    importer = ExcelImporter(
        xlsx_path=xlsx,
        worksheet_name=settings.EXCEL_WORKSHEET_NAME,
        engine=settings.LOCAL_EXCEL_ENGINE,
        cache_dir=settings.INSTANCE_DIR,
    )
    products = importer.read_products()

    with session_scope(sf) as session:
        repo = ProductRepo(session)
        changed = repo.upsert_many(products)

    print("imported", len(products), "upserted", changed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
