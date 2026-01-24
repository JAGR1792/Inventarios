from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets
from PySide6.QtWebChannel import QWebChannel
from PySide6.QtWebEngineCore import QWebEngineSettings
from PySide6.QtWebEngineWidgets import QWebEngineView

from inventarios.settings import Settings
from inventarios.ui.web_backend import WebBackend


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self, session_factory, settings: Settings):
        super().__init__()
        self.setWindowTitle(settings.APP_NAME)
        self.resize(1280, 760)

        view = QWebEngineView(self)
        view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessFileUrls, True)
        view.settings().setAttribute(QWebEngineSettings.LocalContentCanAccessRemoteUrls, False)

        channel = QWebChannel(view.page())
        backend = WebBackend(session_factory=session_factory, settings=settings, parent=channel)
        channel.registerObject("backend", backend)
        view.page().setWebChannel(channel)

        base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
        web_dir = base / "inventarios" / "ui" / "web"
        if not web_dir.exists():
            # Dev fallback (not frozen)
            web_dir = Path(__file__).resolve().parent / "web"
        index_html = web_dir / "store.html"
        if not index_html.exists():
            raise FileNotFoundError(f"Web UI not found: {index_html}")

        # Helpful for debugging broken paths in WebEngine.
        os.environ.setdefault("QTWEBENGINE_DISABLE_SANDBOX", "1")

        view.load(QtCore.QUrl.fromLocalFile(str(index_html)))
        self.setCentralWidget(view)


def _try_set_app_icon(app: QtWidgets.QApplication) -> None:
    # Optional: if user provides an .ico, use it (taskbar + window icon).
    candidates: list[Path] = []

    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        candidates.append(Path(str(meipass)) / "assets" / "app.ico")

    # Dev/project layout: repoRoot/assets/app.ico
    candidates.append(Path(__file__).resolve().parents[2] / "assets" / "app.ico")

    for p in candidates:
        try:
            if p.exists():
                app.setWindowIcon(QtGui.QIcon(str(p)))
                return
        except Exception:
            continue


def run_app(session_factory, settings: Settings) -> int:
    app = QtWidgets.QApplication(sys.argv)
    _try_set_app_icon(app)
    win = MainWindow(session_factory, settings)
    win.show()
    return app.exec()
