from __future__ import annotations

import argparse
import os

from inventarios.db import create_engine_from_url, init_db, make_session_factory
from inventarios.settings import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument(
        "--ui",
        choices=["qt", "webview"],
        default=(os.environ.get("INVENTARIOS_UI") or "qt").strip().lower(),
        help="UI host: 'qt' (default) or 'webview' (pywebview/WebView2)",
    )
    args = parser.parse_args(argv)

    settings = Settings()
    settings.ensure_instance()

    engine = create_engine_from_url(settings.DATABASE_URL)
    init_db(engine)
    session_factory = make_session_factory(engine)

    if args.ui == "webview":
        from inventarios.ui.webview_app import run_app_webview

        return run_app_webview(session_factory, settings)

    from inventarios.ui.main_window import run_app

    return run_app(session_factory, settings)


if __name__ == "__main__":
    raise SystemExit(main())
