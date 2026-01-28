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
    
    # Auto-importar desde Google Sheets al iniciar
    try:
        from inventarios.google_sheets import GoogleSheetsSync
        sync = GoogleSheetsSync()
        if sync.enabled:
            print("📥 Sincronizando desde Google Sheets...")
            products = sync.import_products()
            if products:
                from inventarios.repos import ProductRepo
                from inventarios.db import session_scope
                with session_scope(session_factory) as session:
                    repo = ProductRepo(session)
                    count = repo.upsert_many(products)
                print(f"✅ Importados {len(products)} productos ({count} actualizados)")
    except Exception as e:
        print(f"⚠️  Error en auto-importación: {e}")

    # Note: pywebview injects window.pywebview and triggers 'pywebviewready' in JS.
    webview.create_window(
        title=settings.APP_NAME,
        url=index_html.resolve().as_uri(),
        width=1280,
        height=760,
        js_api=backend,
    )

    # gui='edgechromium' ensures WebView2 on Windows when available.
    try:
        webview.start(gui="edgechromium")
    except Exception as e:
        # Common end-user failure: missing Edge WebView2 Runtime.
        msg = (
            "No se pudo iniciar la interfaz (WebView2).\n\n"
            "Solución: instala 'Microsoft Edge WebView2 Runtime' y vuelve a abrir la app.\n\n"
            f"Detalle: {e}"
        )
        try:
            import ctypes

            ctypes.windll.user32.MessageBoxW(0, msg, settings.APP_NAME, 0x10)  # MB_ICONERROR
        except Exception:
            pass
        raise
    return 0
