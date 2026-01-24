from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from sqlalchemy import delete, update

from inventarios.db import session_scope
from inventarios.excel_import import ExcelImporter
from inventarios.models import CashClose, CashDay, CashMove, Product, ProductImage, Sale, SaleLine
from inventarios.repos import ProductRepo, SalesRepo
from inventarios.services import PosService
from inventarios.settings import Settings


@dataclass(frozen=True)
class OkResult:
    ok: bool
    error: str | None = None


def _file_url(path: str | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if not p.exists():
        return None
    try:
        url = p.resolve().as_uri()
    except Exception:
        # Fall back to best-effort file URL
        url = p.absolute().as_uri()

    try:
        v = int(p.stat().st_mtime_ns)
        return f"{url}?v={v}"
    except Exception:
        return url


_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9_.-]+")


def _safe_filename(name: str) -> str:
    s = _SAFE_NAME_RE.sub("_", (name or "").strip())
    return s.strip("_.") or "img"


def _ask_open_filename(title: str, filetypes: list[tuple[str, str]]):
    # Tkinter is in the stdlib on Windows python.org builds.
    # We keep it isolated so importing this module doesn't pop a window.
    import tkinter as tk
    from tkinter import filedialog

    root = tk.Tk()
    root.withdraw()
    try:
        return filedialog.askopenfilename(title=title, initialdir=str(Path.cwd()), filetypes=filetypes)
    finally:
        try:
            root.destroy()
        except Exception:
            pass


def _open_folder(path: Path) -> bool:
    p = path.resolve()
    try:
        if os.name == "nt":
            os.startfile(str(p))  # type: ignore[attr-defined]
            return True
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(p)])
            return True
        subprocess.Popen(["xdg-open", str(p)])
        return True
    except Exception:
        return False


class WebviewBackend:
    """Backend API for pywebview (Edge WebView2 on Windows).

    Methods are intentionally named to match the existing JS calls in app.js.
    Return values must be JSON-serializable.
    """

    def __init__(self, session_factory, settings: Settings):
        self._session_factory = session_factory
        self._settings = settings

    def getAppInfo(self):
        db_url = str(getattr(self._settings, "DATABASE_URL", "") or "")
        db_file = ""
        if db_url.startswith("sqlite:///"):
            db_file = db_url[len("sqlite:///") :]
        return {"app_name": self._settings.APP_NAME, "db_url": db_url, "db_file": db_file}

    def searchProducts(self, q: str, limit: int = 120):
        qn = (q or "").strip()
        lim = max(1, min(int(limit or 120), 500))

        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            rows = repo.list(q=qn, limit=lim)
            keys = [r.key for r in rows]
            images = {
                img.product_key: img.path
                for img in session.query(ProductImage).filter(ProductImage.product_key.in_(keys)).all()
            }

            out: list[dict] = []
            for r in rows:
                out.append(
                    {
                        "key": r.key,
                        "producto": r.producto,
                        "descripcion": r.descripcion or "",
                        "unidades": int(r.unidades),
                        "precio_final": float(r.precio_final),
                        "category": (r.category or ""),
                        "image_url": _file_url(images.get(r.key)),
                    }
                )
            return out

    def getCategories(self):
        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            cats = repo.list_categories()
        return ["Todas"] + cats

    def pickProductImage(self, product_key: str):
        key = (product_key or "").strip()
        if not key:
            return {"ok": False, "error": "Producto inválido"}

        file_name = _ask_open_filename(
            "Seleccionar imagen del producto",
            [
                ("Imagen", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("Todos", "*.*"),
            ],
        )
        if not file_name:
            return {"ok": False, "error": "Selección cancelada"}

        src = Path(file_name)
        if not src.exists():
            return {"ok": False, "error": "Archivo no existe"}

        img_dir = (self._settings.INSTANCE_DIR / str(self._settings.IMAGES_DIR)).resolve()
        img_dir.mkdir(parents=True, exist_ok=True)

        ext = src.suffix.lower() or ".png"
        dst = img_dir / f"{_safe_filename(key)}{ext}"
        try:
            shutil.copy2(src, dst)
        except Exception as e:
            return {"ok": False, "error": f"No se pudo copiar imagen: {e}"}

        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            repo.set_image(key, str(dst))

        return {"ok": True, "image_url": _file_url(str(dst))}

    def clearProductImage(self, product_key: str):
        key = (product_key or "").strip()
        if not key:
            return {"ok": False, "error": "Producto inválido"}

        with session_scope(self._session_factory) as session:
            img = session.get(ProductImage, key)
            if img is not None:
                session.delete(img)
        return {"ok": True}

    def setProductCategory(self, key: str, category: str):
        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            ok = repo.set_category(key, category)
        return {"ok": bool(ok)}

    def checkout(self, lines, payment=None):
        cart: dict[str, int] = {}
        for ln in (lines or []):
            try:
                k = str(ln.get("key") or "").strip()
                qty = int(ln.get("qty") or 0)
            except Exception:
                continue
            if k and qty > 0:
                cart[k] = cart.get(k, 0) + qty

        payment_method = "cash"
        cash_received: Decimal | None = None
        try:
            if isinstance(payment, dict):
                pm = str(payment.get("method") or "").strip().lower()
                if pm:
                    payment_method = pm
                cr = payment.get("cash_received")
                if cr is not None and str(cr).strip() != "":
                    cash_received = Decimal(str(cr))
        except Exception:
            pass

        with session_scope(self._session_factory) as session:
            service = PosService(session)
            res = service.checkout(cart, payment_method=payment_method, cash_received=cash_received)
            if not res.ok:
                return {"ok": False, "error": res.error or "Error", "details": res.details or None}

            return {
                "ok": True,
                "sale_id": int(res.sale_id or 0),
                "total": float(res.total or 0),
                "payment_method": res.payment_method or payment_method,
                "cash_received": float(res.cash_received) if res.cash_received is not None else None,
                "change_given": float(res.change_given) if res.change_given is not None else None,
            }

    def _ensure_cash_day(self, session, day: str) -> CashDay:
        row = session.get(CashDay, day)
        if row is not None:
            return row

        opening = Decimal("0.00")
        prev = (
            session.query(CashClose)
            .filter(CashClose.day < day)
            .order_by(CashClose.day.desc(), CashClose.created_at.desc())
            .first()
        )
        if prev is not None:
            try:
                opening = Decimal(str(prev.carry_to_next_day or 0)).quantize(Decimal("0.01"))
            except Exception:
                opening = Decimal("0.00")

        row = CashDay(day=day, opening_cash=opening, opening_cash_manual=0)
        session.add(row)
        session.flush()
        return row

    def _suggest_opening_cash(self, session, day: str) -> Decimal:
        opening = Decimal("0.00")
        prev = (
            session.query(CashClose)
            .filter(CashClose.day < day)
            .order_by(CashClose.day.desc(), CashClose.created_at.desc())
            .first()
        )
        if prev is None:
            return opening
        try:
            return Decimal(str(prev.carry_to_next_day or 0)).quantize(Decimal("0.01"))
        except Exception:
            return Decimal("0.00")

    def getCashPanel(self, day_iso: str):
        day = (day_iso or "").strip()
        if not day:
            return {"ok": False, "error": "Día inválido"}

        with session_scope(self._session_factory) as session:
            day_row = self._ensure_cash_day(session, day)
            suggested_opening = self._suggest_opening_cash(session, day)

            try:
                if int(getattr(day_row, "opening_cash_manual", 0) or 0) == 0:
                    current_opening = Decimal(str(day_row.opening_cash or 0)).quantize(Decimal("0.01"))
                    if current_opening != suggested_opening:
                        day_row.opening_cash = suggested_opening
                        day_row.updated_at = datetime.utcnow()
            except Exception:
                pass

            sales = SalesRepo(session)
            t = sales.totals_for_day(day)

            moves = (
                session.query(CashMove)
                .filter((CashMove.day == day) & (CashMove.kind == "withdrawal"))
                .order_by(CashMove.created_at.desc())
                .limit(50)
                .all()
            )
            withdrawals_total = sum((Decimal(str(m.amount or 0)) for m in moves), Decimal("0.00")).quantize(
                Decimal("0.01")
            )

            expected_cash_end = (
                Decimal(str(day_row.opening_cash or 0)) + Decimal(str(t["cash_total"] or 0)) - withdrawals_total
            ).quantize(Decimal("0.01"))

            last_close = (
                session.query(CashClose)
                .filter(CashClose.day == day)
                .order_by(CashClose.created_at.desc())
                .first()
            )

            out_moves = []
            for m in moves:
                out_moves.append(
                    {
                        "id": int(m.id),
                        "created_at": m.created_at.strftime("%H:%M"),
                        "amount": float(Decimal(str(m.amount or 0)).quantize(Decimal("0.01"))),
                        "notes": m.notes or "",
                    }
                )

            out_close = None
            if last_close is not None:
                out_close = {
                    "created_at": last_close.created_at.strftime("%Y-%m-%d %H:%M"),
                    "carry_to_next_day": float(Decimal(str(last_close.carry_to_next_day or 0)).quantize(Decimal("0.01"))),
                    "cash_counted": float(last_close.cash_counted) if last_close.cash_counted is not None else None,
                    "cash_diff": float(last_close.cash_diff) if last_close.cash_diff is not None else None,
                }

            return {
                "ok": True,
                "day": day,
                "opening_cash": float(Decimal(str(day_row.opening_cash or 0)).quantize(Decimal("0.01"))),
                "opening_cash_manual": int(getattr(day_row, "opening_cash_manual", 0) or 0),
                "suggested_opening_cash": float(suggested_opening),
                "withdrawals_total": float(withdrawals_total),
                "withdrawals": out_moves,
                "gross_total": float(t["gross_total"]),
                "cash_total": float(t["cash_total"]),
                "card_total": float(t["card_total"]),
                "nequi_total": float(t.get("nequi_total", 0)),
                "virtual_total": float(t.get("virtual_total", 0)),
                "sales_count": int(t["sales_count"]),
                "expected_cash_end": float(expected_cash_end),
                "last_close": out_close,
            }

    def setOpeningCash(self, day_iso: str, opening_cash):
        day = (day_iso or "").strip()
        if not day:
            return {"ok": False, "error": "Día inválido"}

        try:
            v = Decimal(str(opening_cash)).quantize(Decimal("0.01"))
        except Exception:
            return {"ok": False, "error": "Valor inválido"}

        with session_scope(self._session_factory) as session:
            row = self._ensure_cash_day(session, day)
            row.opening_cash = v
            row.opening_cash_manual = 1
            row.updated_at = datetime.utcnow()
        return {"ok": True}

    def useSuggestedOpeningCash(self, day_iso: str):
        day = (day_iso or "").strip()
        if not day:
            return {"ok": False, "error": "Día inválido"}

        with session_scope(self._session_factory) as session:
            row = self._ensure_cash_day(session, day)
            row.opening_cash = self._suggest_opening_cash(session, day)
            row.opening_cash_manual = 0
            row.updated_at = datetime.utcnow()
            return {"ok": True, "opening_cash": float(row.opening_cash)}

    def addCashWithdrawal(self, day_iso: str, amount, notes: str = ""):
        day = (day_iso or "").strip()
        if not day:
            return {"ok": False, "error": "Día inválido"}

        try:
            v = Decimal(str(amount)).quantize(Decimal("0.01"))
        except Exception:
            return {"ok": False, "error": "Monto inválido"}
        if v <= 0:
            return {"ok": False, "error": "El retiro debe ser mayor a 0"}

        with session_scope(self._session_factory) as session:
            self._ensure_cash_day(session, day)
            mv = CashMove(day=day, kind="withdrawal", amount=v, notes=(notes or "") or None)
            session.add(mv)
            session.flush()
            return {"ok": True, "id": int(mv.id)}

    def deleteCashMove(self, move_id: int):
        mid = int(move_id or 0)
        if mid <= 0:
            return {"ok": False, "error": "Movimiento inválido"}
        with session_scope(self._session_factory) as session:
            mv = session.get(CashMove, mid)
            if mv is None:
                return {"ok": False, "error": "No existe"}
            session.delete(mv)
        return {"ok": True}

    def closeCashDay(self, day_iso: str, cash_counted, carry_to_next_day, notes: str = ""):
        day = (day_iso or "").strip()
        if not day:
            return {"ok": False, "error": "Día inválido"}

        cash_counted_d: Decimal | None = None
        carry_d: Decimal | None = None
        try:
            if cash_counted is not None and str(cash_counted).strip() != "":
                cash_counted_d = Decimal(str(cash_counted)).quantize(Decimal("0.01"))
            if carry_to_next_day is not None and str(carry_to_next_day).strip() != "":
                carry_d = Decimal(str(carry_to_next_day)).quantize(Decimal("0.01"))
        except Exception:
            return {"ok": False, "error": "Valores inválidos"}

        with session_scope(self._session_factory) as session:
            day_row = self._ensure_cash_day(session, day)
            sales = SalesRepo(session)
            t = sales.totals_for_day(day)

            moves = session.query(CashMove).filter((CashMove.day == day) & (CashMove.kind == "withdrawal")).all()
            withdrawals_total = sum((Decimal(str(m.amount or 0)) for m in moves), Decimal("0.00")).quantize(
                Decimal("0.01")
            )

            expected_cash_end = (
                Decimal(str(day_row.opening_cash or 0)) + Decimal(str(t["cash_total"] or 0)) - withdrawals_total
            ).quantize(Decimal("0.01"))

            if carry_d is None:
                carry_d = expected_cash_end

            diff: Decimal | None = None
            if cash_counted_d is not None:
                diff = (cash_counted_d - expected_cash_end).quantize(Decimal("0.01"))

            row = CashClose(
                day=day,
                opening_cash=Decimal(str(day_row.opening_cash or 0)).quantize(Decimal("0.01")),
                withdrawals_total=withdrawals_total,
                gross_total=t["gross_total"],
                cash_total=t["cash_total"],
                card_total=t["card_total"],
                nequi_total=t.get("nequi_total", Decimal("0.00")),
                virtual_total=t.get("virtual_total", Decimal("0.00")),
                expected_cash_end=expected_cash_end,
                carry_to_next_day=carry_d,
                cash_counted=cash_counted_d,
                cash_diff=diff,
                notes=(notes or "") or None,
            )
            session.add(row)
            session.flush()

            return {
                "ok": True,
                "id": int(row.id),
                "created_at": row.created_at.strftime("%Y-%m-%d %H:%M"),
                "day": row.day,
                "expected_cash_end": float(row.expected_cash_end),
                "carry_to_next_day": float(row.carry_to_next_day),
                "cash_diff": float(row.cash_diff) if row.cash_diff is not None else None,
            }

    def listCashCloses(self, limit: int = 30):
        lim = max(1, min(int(limit or 30), 200))
        with session_scope(self._session_factory) as session:
            rows = session.query(CashClose).order_by(CashClose.created_at.desc()).limit(lim).all()

            out: list[dict] = []
            for r in rows:
                out.append(
                    {
                        "id": int(r.id),
                        "created_at": r.created_at.strftime("%Y-%m-%d %H:%M"),
                        "day": r.day,
                        "opening_cash": float(r.opening_cash) if r.opening_cash is not None else 0,
                        "withdrawals_total": float(r.withdrawals_total) if r.withdrawals_total is not None else 0,
                        "gross_total": float(r.gross_total),
                        "cash_total": float(r.cash_total),
                        "card_total": float(r.card_total),
                        "nequi_total": float(getattr(r, "nequi_total", 0) or 0),
                        "virtual_total": float(getattr(r, "virtual_total", 0) or 0),
                        "expected_cash_end": float(getattr(r, "expected_cash_end", 0) or 0),
                        "carry_to_next_day": float(getattr(r, "carry_to_next_day", 0) or 0),
                        "cash_counted": float(r.cash_counted) if r.cash_counted is not None else None,
                        "cash_diff": float(r.cash_diff) if r.cash_diff is not None else None,
                    }
                )
            return out

    def getSummary(self, limit: int = 25):
        lim = max(1, min(int(limit or 25), 200))
        with session_scope(self._session_factory) as session:
            sales = SalesRepo(session)
            total = sales.total_sold()
            last = sales.list_sales_summary(limit=lim)

            out_last: list[dict] = []
            for row in last:
                created = row.get("created_at")
                if isinstance(created, datetime):
                    created_str = created.strftime("%Y-%m-%d %H:%M")
                else:
                    created_str = str(created)
                out_last.append(
                    {
                        "id": int(row.get("id") or 0),
                        "created_at": created_str,
                        "total": float(row.get("total") or 0),
                        "items": int(row.get("items") or 0),
                        "payment_method": str(row.get("payment_method") or "cash"),
                    }
                )

        return {"total_vendido": float(total), "ultimas_ventas": out_last}

    def importExcel(self):
        file_name = _ask_open_filename("Importar desde Excel", [("Excel", "*.xlsx"), ("Todos", "*.*")])
        if not file_name:
            return {"ok": False, "error": "Importación cancelada"}

        try:
            importer = ExcelImporter(
                xlsx_path=Path(file_name),
                worksheet_name=self._settings.EXCEL_WORKSHEET_NAME,
                engine=self._settings.LOCAL_EXCEL_ENGINE,
                cache_dir=self._settings.INSTANCE_DIR,
            )
            products = importer.read_products()
            if not products:
                return {
                    "ok": False,
                    "error": "No se encontraron productos para importar (revisa hoja/encabezados).",
                }

            with session_scope(self._session_factory) as session:
                repo = ProductRepo(session)
                changed = repo.upsert_many(products)

            return {"ok": True, "imported": int(len(products)), "upserted": int(changed)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def resetDatabase(self, confirm_text: str):
        if (confirm_text or "").strip().upper() != "BORRAR":
            return {"ok": False, "error": "Confirmación inválida (escribe BORRAR)"}

        try:
            with session_scope(self._session_factory) as session:
                session.execute(delete(SaleLine))
                session.execute(delete(Sale))

                session.execute(delete(CashMove))
                session.execute(delete(CashClose))
                session.execute(delete(CashDay))

                session.execute(update(Product).values(unidades=0, updated_at=datetime.utcnow()))

            return {"ok": True}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def openImagesFolder(self):
        try:
            img_dir = (self._settings.INSTANCE_DIR / str(self._settings.IMAGES_DIR)).resolve()
            img_dir.mkdir(parents=True, exist_ok=True)
            ok = _open_folder(img_dir)
            return {"ok": bool(ok), "path": str(img_dir)}
        except Exception as e:
            return {"ok": False, "error": str(e)}
