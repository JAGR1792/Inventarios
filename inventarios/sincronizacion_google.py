from __future__ import annotations

import logging
from dataclasses import dataclass

from inventarios.db import session_scope
from inventarios.google_sheets import GoogleSheetsSync
from inventarios.repos import ProductRepo, SalesRepo
from inventarios.settings import Settings
from inventarios.tipos_importacion import ProductoImportado

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ResultadoSync:
    ok: bool
    error: str | None = None


class SincronizadorGoogleSheets:
    """Servicio de sincronización SOLO con Google Sheets.

    Replica el flujo probado en scripts/test_google_sheets.py:
    - GoogleSheetsSync(settings)
    - Import: leer hoja -> convertir -> upsert_many
    - Export: leer DB -> export_products
    - Ventas: leer DB -> export_sales

    Este módulo evita dependencias legacy y concentra la lógica.
    """

    def __init__(self, session_factory, settings: Settings):
        self._session_factory = session_factory
        self._settings = settings

    def _sync(self) -> GoogleSheetsSync:
        return GoogleSheetsSync(self._settings)

    def importar_inventario(self) -> dict:
        sync = self._sync()
        if not sync.enabled:
            return {"ok": False, "error": "Google Sheets no está configurado. Revisa el archivo .env"}

        productos_sheet = sync.import_products()
        if not productos_sheet:
            return {"ok": False, "error": "No se encontraron productos en Google Sheets"}

        importados = [
            ProductoImportado(
                key=p.key,
                producto=p.producto,
                descripcion=p.descripcion,
                unidades=int(p.unidades or 0),
                precio_final=float(p.precio_final or 0),
            )
            for p in productos_sheet
        ]

        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            count = repo.upsert_many(importados)

        logger.info("Importados %s productos desde Google Sheets", len(importados))
        return {"ok": True, "imported": len(importados), "upserted": int(count), "source": "Google Sheets"}

    def exportar_inventario(self) -> dict:
        sync = self._sync()
        if not sync.enabled:
            return {"ok": False, "error": "Google Sheets no está configurado. Revisa el archivo .env"}

        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            productos_db = repo.list(limit=9999)

        if not productos_db:
            return {"ok": False, "error": "No hay productos para exportar"}

        ok = bool(sync.export_products(productos_db))
        if not ok:
            return {"ok": False, "error": "Error exportando a Google Sheets"}

        return {"ok": True, "exported": len(productos_db), "url": sync.get_spreadsheet_url(), "target": "Google Sheets"}

    def exportar_ventas(self, limit: int = 500) -> dict:
        sync = self._sync()
        if not sync.enabled:
            return {"ok": False, "error": "Google Sheets no está configurado"}

        with session_scope(self._session_factory) as session:
            sales_repo = SalesRepo(session)
            sales = sales_repo.list_sales(limit=int(limit or 500))

        if not sales:
            return {"ok": True, "exported": 0, "message": "No hay ventas para exportar"}

        ok = bool(sync.export_sales(sales))
        if not ok:
            return {"ok": False, "error": "Error exportando ventas a Google Sheets"}

        return {"ok": True, "exported": len(sales), "url": sync.get_spreadsheet_url(), "target": "Google Sheets - VENTAS"}

    def sincronizar_todo(self) -> dict:
        imp = self.importar_inventario()
        if not imp.get("ok"):
            return imp

        exp = self.exportar_inventario()
        if not exp.get("ok"):
            return {
                "ok": False,
                "error": exp.get("error") or "Error exportando inventario",
                "imported": imp.get("imported", 0),
            }

        sales = self.exportar_ventas()
        return {
            "ok": True,
            "imported": imp.get("imported", 0),
            "exported": exp.get("exported", 0),
            "sales_exported": sales.get("exported", 0) if isinstance(sales, dict) else 0,
            "url": exp.get("url") or imp.get("url"),
            "source": "Google Sheets",
        }
