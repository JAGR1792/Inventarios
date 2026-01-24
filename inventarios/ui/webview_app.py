from __future__ import annotations

import sys
from pathlib import Path

from inventarios.settings import Settings
from inventarios.ui.webview_backend import WebviewBackend


def _resolve_web_dir() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    web_dir = base / "inventarios" / "ui" / "web"
    if not web_dir.exists():
        # Dev fallback
        web_dir = Path(__file__).resolve().parent / "web"
    return web_dir


def run_app_webview(session_factory, settings: Settings) -> int:
    try:
        import webview  # pywebview
    except Exception as e:
        raise RuntimeError(
            "pywebview no está instalado. Instala con: pip install pywebview"
        ) from e

    web_dir = _resolve_web_dir()
    index_html = web_dir / "store.html"
    if not index_html.exists():
        raise FileNotFoundError(f"Web UI not found: {index_html}")

    backend = WebviewBackend(session_factory=session_factory, settings=settings)

    # Note: pywebview injects window.pywebview and triggers 'pywebviewready' in JS.
    webview.create_window(
        title=settings.APP_NAME,
        url=index_html.resolve().as_uri(),
        width=1280,
        height=760,
        js_api=backend,
    )

    # gui='edgechromium' ensures WebView2 on Windows when available.
    webview.start(gui="edgechromium")
    return 0
