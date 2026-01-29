from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ProductoImportado:
    """Producto normalizado para hacer UPSERT en la base de datos.

    Nota: este tipo existe para desacoplar la importación desde Google Sheets
    de cualquier formato o librería externa.
    """

    key: str
    producto: str
    descripcion: str
    unidades: int
    precio_final: float
