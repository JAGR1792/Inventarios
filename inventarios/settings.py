from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    # App
    APP_NAME: str = os.environ.get("APP_NAME", "Inventarios POS")

    # Storage
    INSTANCE_DIR: Path = Path(os.environ.get("INSTANCE_DIR", "instance")).resolve()
    DATABASE_URL: str = os.environ.get(
        "DATABASE_URL", f"sqlite:///{(Path('instance') / 'pos.sqlite').as_posix()}"
    )

    # Excel import (optional)
    EXCEL_IMPORT_PATH: str = os.environ.get("EXCEL_IMPORT_PATH", "GAROM OK.xlsx")
    EXCEL_WORKSHEET_NAME: str = os.environ.get("EXCEL_WORKSHEET_NAME", "INVENTARIO")
    # Excel export (inventory sync)
    # Keep this separate from import because many workbooks have a different sheet for costs.
    EXCEL_EXPORT_WORKSHEET_NAME: str = os.environ.get("EXCEL_EXPORT_WORKSHEET_NAME", "INVENTARIO")
    LOCAL_EXCEL_ENGINE: str = os.environ.get("LOCAL_EXCEL_ENGINE", "openpyxl")

    # Images
    IMAGES_DIR: str = os.environ.get("IMAGES_DIR", "product_images")
    
    # Google Sheets integration (optional)
    GOOGLE_SHEETS_ENABLED: bool = os.environ.get("GOOGLE_SHEETS_ENABLED", "false").lower() == "true"
    GOOGLE_SHEETS_SPREADSHEET_ID: str = os.environ.get("GOOGLE_SHEETS_SPREADSHEET_ID", "")
    GOOGLE_SHEETS_WORKSHEET_NAME: str = os.environ.get("GOOGLE_SHEETS_WORKSHEET_NAME", "INVENTARIO")
    GOOGLE_CREDENTIALS_FILE: str = os.environ.get("GOOGLE_CREDENTIALS_FILE", "credentials.json")
    GOOGLE_TOKEN_FILE: str = os.environ.get("GOOGLE_TOKEN_FILE", "token.json")
    GOOGLE_SHEETS_SYNC_INTERVAL_SECONDS: int = int(os.environ.get("GOOGLE_SHEETS_SYNC_INTERVAL_SECONDS", "300"))

    def _default_windows_instance_dir(self) -> Path:
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if not base:
            base = str(Path.home())
        safe = "".join(c for c in (self.APP_NAME or "InventariosPOS") if c.isalnum() or c in (" ", "-", "_"))
        safe = safe.strip().replace(" ", "_") or "InventariosPOS"
        return (Path(base) / safe / "instance").resolve()

    def __post_init__(self) -> None:
        db_url_env_set = os.environ.get("DATABASE_URL") is not None

        # When packaged as an .exe, default to a per-user writable instance folder.
        if getattr(sys, "frozen", False) and os.environ.get("INSTANCE_DIR") is None:
            object.__setattr__(self, "INSTANCE_DIR", self._default_windows_instance_dir())

        # Always resolve INSTANCE_DIR; many other paths depend on it.
        object.__setattr__(self, "INSTANCE_DIR", Path(self.INSTANCE_DIR).resolve())

        # If DATABASE_URL was not explicitly provided, always place the DB inside INSTANCE_DIR.
        # This avoids mismatches when the process working directory changes (e.g. running from dist/).
        if not db_url_env_set:
            abs_db = (self.INSTANCE_DIR / "pos.sqlite").resolve()
            object.__setattr__(self, "DATABASE_URL", f"sqlite:///{abs_db.as_posix()}")
            return

        # Normalize SQLite URLs so they don't depend on the process working directory.
        # Example: sqlite:///instance/pos.sqlite -> sqlite:///C:/.../Inventarios/instance/pos.sqlite
        db = str(self.DATABASE_URL or "").strip()
        if not db:
            abs_db = (self.INSTANCE_DIR / "pos.sqlite").resolve()
            object.__setattr__(self, "DATABASE_URL", f"sqlite:///{abs_db.as_posix()}")
            return

        if db.startswith("sqlite:///") and not db.startswith("sqlite:////"):
            path_part = db[len("sqlite:///") :]
            # Strip query string if present
            if "?" in path_part:
                path_part = path_part.split("?", 1)[0]

            p = Path(path_part)
            if not p.is_absolute():
                project_root = Path(__file__).resolve().parents[1]
                abs_path = (project_root / p).resolve()
                object.__setattr__(self, "DATABASE_URL", f"sqlite:///{abs_path.as_posix()}")

    def ensure_instance(self) -> None:
        self.INSTANCE_DIR.mkdir(parents=True, exist_ok=True)
        (self.INSTANCE_DIR / str(self.IMAGES_DIR)).mkdir(parents=True, exist_ok=True)
