from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
import unicodedata

from openpyxl import load_workbook


@dataclass(frozen=True)
class ImportedProduct:
    key: str
    producto: str
    descripcion: str
    unidades: int
    precio_final: float


class ExcelImporter:
    REQUIRED = {
        "producto": "Producto",
        "descripcion": "Descripcion",
        "unidades": "unidades",
        "precio_final": "Precio Final",
    }

    def __init__(
        self,
        xlsx_path: Path,
        worksheet_name: str,
        *,
        engine: str = "openpyxl",
        cache_dir: Path | None = None,
    ):
        self.xlsx_path = xlsx_path
        self.worksheet_name = worksheet_name
        self.engine = (engine or "openpyxl").strip().casefold()
        self.cache_dir = cache_dir
        if self.cache_dir is not None:
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _norm(x: Any) -> str:
        s = str(x or "").strip()
        s = " ".join(s.split())
        s = unicodedata.normalize("NFKD", s)
        s = "".join(ch for ch in s if not unicodedata.combining(ch))
        return s.casefold()

    def _price_cache_path(self) -> Path | None:
        if self.cache_dir is None:
            return None
        return self.cache_dir / "price_cache.json"

    def _load_price_cache(self) -> dict[str, float]:
        p = self._price_cache_path()
        if not p or not p.exists():
            return {}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
        if not isinstance(data, dict):
            return {}
        out: dict[str, float] = {}
        for k, v in data.items():
            try:
                out[str(k)] = float(v)
            except Exception:
                continue
        return out

    def _save_price_cache(self, cache: dict[str, float]) -> None:
        p = self._price_cache_path()
        if not p:
            return
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)

    def _open(self, *, data_only: bool):
        # read_only=True is dramatically faster and avoids huge memory spikes.
        # values_only iteration is used throughout to prevent creating cell objects.
        return load_workbook(
            filename=self.xlsx_path,
            data_only=bool(data_only),
            read_only=True,
        )

    def _find_header(self, ws, scan_rows: int = 40) -> tuple[int, dict[str, int]]:
        required = [self._norm(v) for v in self.REQUIRED.values()]

        best_row = None
        best_score = -1
        best_values = None

        # Iterate values only; ws.max_row can be misleadingly huge if formatting extends.
        max_r = min(int(getattr(ws, "max_row", 0) or 0) or scan_rows, scan_rows)
        for r in range(1, max_r + 1):
            row_vals = list(next(ws.iter_rows(min_row=r, max_row=r, values_only=True)))
            present = {self._norm(v) for v in row_vals if self._norm(v)}
            score = sum(1 for req in required if req in present)
            if score > best_score:
                best_score = score
                best_row = r
                best_values = row_vals

        if best_score < 3 or best_row is None or best_values is None:
            raise RuntimeError(
                "Could not detect header row in first rows of 'Costos'. "
                "Ensure it contains columns Producto, Descripcion, unidades, Precio Final."
            )

        header_map = {self._norm(name): idx + 1 for idx, name in enumerate(best_values) if self._norm(name)}
        return best_row, header_map

    def _excel_com_read(self) -> list[ImportedProduct]:
        try:
            import win32com.client  # type: ignore
        except Exception as e:
            raise RuntimeError(
                "EXCEL_ENGINE=excel requires pywin32 (Windows). Install it or use EXCEL_ENGINE=openpyxl."
            ) from e

        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        wb = None
        try:
            wb = excel.Workbooks.Open(str(self.xlsx_path))
            ws = wb.Worksheets(self.worksheet_name)

            used = ws.UsedRange
            values = used.Value
            if values is None:
                return []

            max_r = min(len(values), 30)
            required = [self._norm(v) for v in self.REQUIRED.values()]

            best_row = None
            best_score = -1
            best_values = None
            for r in range(1, max_r + 1):
                row_vals = list(values[r - 1])
                present = {self._norm(v) for v in row_vals if self._norm(v)}
                score = sum(1 for req in required if req in present)
                if score > best_score:
                    best_score = score
                    best_row = r
                    best_values = row_vals

            if best_score < 3 or best_row is None or best_values is None:
                raise RuntimeError("Could not detect header row in Costos")

            header_map = {self._norm(name): idx + 1 for idx, name in enumerate(best_values)}

            def col(display: str) -> int:
                k = self._norm(display)
                if k not in header_map:
                    raise RuntimeError(f"Missing required column '{display}'")
                return header_map[k]

            i_prod = col(self.REQUIRED["producto"])
            i_desc = col(self.REQUIRED["descripcion"])
            i_units = col(self.REQUIRED["unidades"])
            i_price = col(self.REQUIRED["precio_final"])

            out: list[ImportedProduct] = []
            for r in range(best_row + 1, len(values) + 1):
                row_vals = values[r - 1]
                producto = str(row_vals[i_prod - 1] or "").strip()
                if not producto:
                    continue
                descripcion = str(row_vals[i_desc - 1] or "").strip()

                unidades_raw = row_vals[i_units - 1]
                try:
                    unidades = int(float(unidades_raw)) if unidades_raw not in (None, "") else 0
                except (ValueError, TypeError):
                    unidades = 0

                precio_raw = row_vals[i_price - 1]
                try:
                    precio_final = float(precio_raw) if precio_raw not in (None, "") else 0.0
                except (ValueError, TypeError):
                    precio_final = 0.0

                out.append(
                    ImportedProduct(
                        key=producto,
                        producto=producto,
                        descripcion=descripcion,
                        unidades=unidades,
                        precio_final=precio_final,
                    )
                )
            return out
        finally:
            try:
                if wb is not None:
                    wb.Close(SaveChanges=False)
            finally:
                excel.Quit()

    def read_products(self) -> list[ImportedProduct]:
        if not self.xlsx_path.exists():
            raise RuntimeError(f"Excel file not found: {self.xlsx_path}")

        if self.engine == "excel":
            return self._excel_com_read()

        cache = self._load_price_cache()
        cache_changed = False

        wb = self._open(data_only=True)
        if self.worksheet_name not in wb.sheetnames:
            raise RuntimeError(f"Worksheet '{self.worksheet_name}' not found")

        ws = wb[self.worksheet_name]
        header_row, header_map = self._find_header(ws)

        def col(display: str) -> int:
            k = self._norm(display)
            if k not in header_map:
                raise RuntimeError(f"Missing required column '{display}'")
            return header_map[k]

        i_prod = col(self.REQUIRED["producto"])
        i_desc = col(self.REQUIRED["descripcion"])
        i_units = col(self.REQUIRED["unidades"])
        i_price = col(self.REQUIRED["precio_final"])

        out: list[ImportedProduct] = []
        empty_streak = 0
        max_empty_streak = 200  # stop early if the sheet has long blank tails/formatting

        for row_vals in ws.iter_rows(min_row=header_row + 1, values_only=True):
            # Guard against short rows
            def at(idx1: int):
                i0 = idx1 - 1
                return row_vals[i0] if i0 >= 0 and i0 < len(row_vals) else None

            producto = str(at(i_prod) or "").strip()
            if not producto:
                empty_streak += 1
                if empty_streak >= max_empty_streak:
                    break
                continue

            empty_streak = 0

            descripcion = str(at(i_desc) or "").strip()

            unidades_raw = at(i_units)
            try:
                unidades = int(float(unidades_raw)) if unidades_raw not in (None, "") else 0
            except (ValueError, TypeError):
                unidades = 0

            precio_raw = at(i_price)
            try:
                precio_final = float(precio_raw) if precio_raw not in (None, "") else 0.0
            except (ValueError, TypeError):
                precio_final = 0.0

            if precio_final == 0.0 and cache.get(producto, 0) > 0:
                precio_final = float(cache[producto])
            elif precio_final > 0:
                if cache.get(producto) != precio_final:
                    cache[producto] = float(precio_final)
                    cache_changed = True

            out.append(
                ImportedProduct(
                    key=producto,
                    producto=producto,
                    descripcion=descripcion,
                    unidades=unidades,
                    precio_final=precio_final,
                )
            )

        if cache_changed:
            self._save_price_cache(cache)

        # If mostly zeros, try one-time COM read to seed cache (if Excel is installed).
        if out:
            zero_ratio = sum(1 for p in out if float(p.precio_final) == 0.0) / float(len(out))
            if zero_ratio > 0.5:
                try:
                    com = self._excel_com_read()
                    by_key = {p.key: p for p in com if float(p.precio_final) > 0}
                    patched: list[ImportedProduct] = []
                    for p in out:
                        if float(p.precio_final) == 0.0 and p.key in by_key:
                            patched_price = float(by_key[p.key].precio_final)
                            cache[p.key] = patched_price
                            patched.append(
                                ImportedProduct(
                                    key=p.key,
                                    producto=p.producto,
                                    descripcion=p.descripcion,
                                    unidades=p.unidades,
                                    precio_final=patched_price,
                                )
                            )
                        else:
                            patched.append(p)
                    out = patched
                    self._save_price_cache(cache)
                except Exception:
                    pass

        return out
