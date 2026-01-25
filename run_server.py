from __future__ import annotations

import argparse

from inventarios.db import create_engine_from_url, init_db, make_session_factory
from inventarios.settings import Settings
from inventarios.ui.web_server import create_app


def main() -> int:
    p = argparse.ArgumentParser(description="Inventarios POS - Web server (LAN/tablet)")
    p.add_argument("--host", default="0.0.0.0", help="Bind host (use 0.0.0.0 for LAN)")
    p.add_argument("--port", type=int, default=8000, help="Port")
    p.add_argument("--debug", action="store_true", help="Flask debug mode")
    args = p.parse_args()

    settings = Settings()
    settings.ensure_instance()

    engine = create_engine_from_url(settings.DATABASE_URL)
    init_db(engine)
    session_factory = make_session_factory(engine)

    app = create_app(session_factory, settings)
    app.run(host=args.host, port=args.port, debug=args.debug)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
