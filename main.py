from __future__ import annotations

from inventarios.db import create_engine_from_url, init_db, make_session_factory
from inventarios.settings import Settings
from inventarios.ui.main_window import run_app


def main() -> int:
    settings = Settings()
    settings.ensure_instance()

    engine = create_engine_from_url(settings.DATABASE_URL)
    init_db(engine)
    session_factory = make_session_factory(engine)

    return run_app(session_factory, settings)


if __name__ == "__main__":
    raise SystemExit(main())
