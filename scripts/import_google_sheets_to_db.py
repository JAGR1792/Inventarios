"""Importa inventario desde Google Sheets a la base de datos local.

Reemplaza el script legacy de importación.

Uso:
  python scripts/import_google_sheets_to_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# Agregar el directorio raíz al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from inventarios.db import create_engine_from_url, init_db, make_session_factory
from inventarios.settings import Settings
from inventarios.sincronizacion_google import SincronizadorGoogleSheets


def main() -> int:
    settings = Settings()

    if not settings.GOOGLE_SHEETS_ENABLED:
        print("Google Sheets está deshabilitado. Configura GOOGLE_SHEETS_ENABLED=true")
        return 1

    engine = create_engine_from_url(settings.DATABASE_URL)
    init_db(engine)
    factory = make_session_factory(engine)

    svc = SincronizadorGoogleSheets(factory, settings)
    res = svc.importar_inventario()

    if not res.get("ok"):
        print("ERROR:", res.get("error") or "Fallo desconocido")
        return 1

    print(f"OK: importados {res.get('imported', 0)} • actualizados {res.get('upserted', 0)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
