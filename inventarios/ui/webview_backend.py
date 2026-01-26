from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import threading

from sqlalchemy import delete, update

from inventarios.db import session_scope
from inventarios.excel_export import ExportRow, export_inventory_to_excel
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
    # Flask runs handlers in worker threads; Tk file dialogs must run on the main thread.
    # In HTTP/tablet mode we cannot safely open OS dialogs from a request thread.
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError(
            "El selector de archivos solo funciona en el PC (hilo principal). "
            "En modo servidor/tablet configura el Excel copiándolo a la carpeta 'instance' "
            "(ruta recomendada) o usando el import/export desde el PC."
        )

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

    def _excel_sync_path(self) -> Path:
        return (self._settings.INSTANCE_DIR / "excel_sync.json").resolve()

    def _default_excel_path(self) -> Path:
        p = Path(getattr(self._settings, "EXCEL_IMPORT_PATH", "") or "GAROM OK.xlsx")
        if not p.is_absolute():
            p = (self._settings.INSTANCE_DIR / p)
        return p.resolve()

    def _load_excel_sync(self) -> dict:
        p = self._excel_sync_path()
        if not p.exists():
            # If user placed the Excel in the recommended default location, pick it up automatically.
            d = self._default_excel_path()
            last = str(d) if d.exists() else None
            return {"last_excel_path": last, "auto_export_on_close": True}
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            d = self._default_excel_path()
            last = str(d) if d.exists() else None
            return {"last_excel_path": last, "auto_export_on_close": True}
        if not isinstance(data, dict):
            d = self._default_excel_path()
            last = str(d) if d.exists() else None
            return {"last_excel_path": last, "auto_export_on_close": True}

        last = data.get("last_excel_path")
        if isinstance(last, str):
            last = last.strip() or None
        else:
            last = None

        # If configured file is missing, fall back to default location if present.
        if last:
            try:
                if not Path(last).exists():
                    last = None
            except Exception:
                last = None

        if not last:
            d = self._default_excel_path()
            if d.exists():
                last = str(d)

        return {"last_excel_path": last, "auto_export_on_close": bool(data.get("auto_export_on_close", True))}

    def _save_excel_sync(self, data: dict) -> None:
        p = self._excel_sync_path()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(p)

    def _export_inventory_to_excel_path(self, file_path: str) -> dict:
        fp = (file_path or "").strip()
        if not fp:
            return {"ok": False, "error": "Ruta inválida"}

        xlsx = Path(fp)
        if not xlsx.exists():
            return {"ok": False, "error": "El archivo Excel no existe"}

        with session_scope(self._session_factory) as session:
            rows = session.query(Product).order_by(Product.producto.asc()).all()
            out_rows: list[ExportRow] = []
            for r in rows:
                out_rows.append(
                    ExportRow(
                        producto=str(r.producto or ""),
                        descripcion=str(r.descripcion or ""),
                        unidades=int(r.unidades or 0),
                        precio_final=Decimal(str(r.precio_final or 0)).quantize(Decimal("0.01")),
                    )
                )

        try:
            written, worksheet_used = export_inventory_to_excel(
                xlsx_path=xlsx,
                worksheet_name=getattr(self._settings, "EXCEL_EXPORT_WORKSHEET_NAME", "INVENTARIO"),
                rows=out_rows,
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}

        return {"ok": True, "path": str(xlsx), "written": int(written), "worksheet": str(worksheet_used)}

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

    def setProductInfo(self, key: str, producto: str, descripcion: str = ""):
        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            try:
                ok = repo.set_info(key, producto=producto, descripcion=descripcion)
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": bool(ok)}

    def restockProduct(self, key: str, delta: int, notes: str = ""):
        """Add inventory units to a product (delta can be positive; negative will reduce but not below 0)."""
        try:
            d = int(delta or 0)
        except Exception:
            d = 0
        if d == 0:
            return {"ok": False, "error": "Cantidad inválida"}

        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            try:
                new_stock = repo.adjust_stock(key, delta=d, kind="restock", notes=notes)
            except Exception as e:
                return {"ok": False, "error": str(e)}

        return {"ok": True, "unidades": int(new_stock)}

    def setProductStock(self, key: str, stock: int, notes: str = ""):
        try:
            s = int(stock or 0)
        except Exception:
            s = 0

        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            try:
                new_stock = repo.set_stock(key, stock=s, notes=notes)
            except Exception as e:
                return {"ok": False, "error": str(e)}

        return {"ok": True, "unidades": int(new_stock)}

    def setProductPrice(self, key: str, precio_final):
        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            try:
                price = repo.set_price(key, precio_final=Decimal(str(precio_final or 0)))
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": True, "precio_final": float(price)}

    def createProduct(self, producto: str, descripcion: str = "", precio_final=None, unidades: int = 0, category: str = ""):
        with session_scope(self._session_factory) as session:
            repo = ProductRepo(session)
            try:
                row = repo.create_product(
                    producto=producto,
                    descripcion=descripcion,
                    unidades=int(unidades or 0),
                    precio_final=Decimal(str(precio_final or 0)),
                    category=category,
                )
            except Exception as e:
                return {"ok": False, "error": str(e)}
        return {"ok": True, "key": row.key}

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
        if row is None:
            row = CashDay(day=day, opening_cash=Decimal("0.00"), opening_cash_manual=0)
            session.add(row)
            session.flush()
        return row

    def _get_prev_close(self, session, day: str) -> CashClose | None:
        return (
            session.query(CashClose)
            .filter(CashClose.day < day)
            .order_by(CashClose.day.desc(), CashClose.created_at.desc())
            .first()
        )

    def _get_opening_cash(self, session, day: str) -> tuple[Decimal, str, bool]:
        """Returns (opening_cash, source, needs_initial_opening).

        source:
          - "prev_close": derived from previous day's close
          - "initial": one-time initial cash set by user
          - "zero": default 0 when system has no prior data
        """
        day_row = self._ensure_cash_day(session, day)
        prev = self._get_prev_close(session, day)
        if prev is not None:
            opening = Decimal(str(prev.carry_to_next_day or 0)).quantize(Decimal("0.01"))
            # Enforce rule: opening is derived from previous close.
            try:
                if Decimal(str(day_row.opening_cash or 0)).quantize(Decimal("0.01")) != opening or int(
                    getattr(day_row, "opening_cash_manual", 0) or 0
                ) != 0:
                    day_row.opening_cash = opening
                    day_row.opening_cash_manual = 0
                    day_row.updated_at = datetime.utcnow()
            except Exception:
                pass
            return opening, "prev_close", False

        # No previous close: allow one-time initial opening.
        opening = Decimal(str(day_row.opening_cash or 0)).quantize(Decimal("0.01"))
        is_initial = int(getattr(day_row, "opening_cash_manual", 0) or 0) == 1
        if is_initial:
            return opening, "initial", False
        # No initial set.
        any_close = session.query(CashClose.id).limit(1).first() is not None
        # If there are closes but none before this day, treat as prev_close scenario in past dates.
        # For simplicity: still requires opening unless user closes days in order.
        return Decimal("0.00"), "zero", not any_close

    def _next_day(self, day: str) -> str:
        d = datetime.strptime(day, "%Y-%m-%d")
        return (d + timedelta(days=1)).strftime("%Y-%m-%d")

    def getCashPanel(self, day_iso: str):
        day = (day_iso or "").strip()
        if not day:
            return {"ok": False, "error": "Día inválido"}

        with session_scope(self._session_factory) as session:
            day_row = self._ensure_cash_day(session, day)
            opening_cash, opening_source, needs_initial_opening = self._get_opening_cash(session, day)

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

            expected_cash_end = (opening_cash + Decimal(str(t["cash_total"] or 0)) - withdrawals_total).quantize(
                Decimal("0.01")
            )

            last_close = session.query(CashClose).filter(CashClose.day == day).order_by(CashClose.created_at.desc()).first()
            is_closed = last_close is not None

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
                "opening_cash": float(opening_cash),
                "opening_source": opening_source,
                "needs_initial_opening": bool(needs_initial_opening),
                "is_closed": bool(is_closed),
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
            # Only allowed as the one-time initial opening when there are no prior closes.
            any_close = session.query(CashClose.id).limit(1).first() is not None
            if any_close:
                return {"ok": False, "error": "La apertura se arrastra del cierre anterior. No se ingresa manual cada día."}

            row = self._ensure_cash_day(session, day)
            row.opening_cash = v
            row.opening_cash_manual = 1
            row.updated_at = datetime.utcnow()
        return {"ok": True, "opening_cash": float(v)}

    def useSuggestedOpeningCash(self, day_iso: str):
        day = (day_iso or "").strip()
        if not day:
            return {"ok": False, "error": "Día inválido"}

        # Deprecated in the new flow; keep endpoint for compatibility.
        with session_scope(self._session_factory) as session:
            any_close = session.query(CashClose.id).limit(1).first() is not None
            if any_close:
                return {"ok": False, "error": "Ya no aplica: la apertura se toma automáticamente del cierre anterior."}
            row = self._ensure_cash_day(session, day)
            row.opening_cash = Decimal("0.00")
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
            if session.query(CashClose.id).filter(CashClose.day == day).limit(1).first() is not None:
                return {"ok": False, "error": "El día ya está cerrado. No se pueden agregar retiros."}
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

    def closeCashDay(self, day_iso: str, cash_counted, carry_to_next_day, notes: str = "", force: bool = False):
        day = (day_iso or "").strip()
        if not day:
            return {"ok": False, "error": "Día inválido"}

        cash_counted_d: Decimal | None = None
        try:
            if cash_counted is not None and str(cash_counted).strip() != "":
                cash_counted_d = Decimal(str(cash_counted)).quantize(Decimal("0.01"))
        except Exception:
            return {"ok": False, "error": "Valores inválidos"}

        with session_scope(self._session_factory) as session:
            # Idempotency: don't allow closing the same day twice.
            if session.query(CashClose.id).filter(CashClose.day == day).limit(1).first() is not None:
                return {"ok": False, "error": "La caja de este día ya fue cerrada."}

            self._ensure_cash_day(session, day)
            opening_cash, _, _ = self._get_opening_cash(session, day)
            sales = SalesRepo(session)
            t = sales.totals_for_day(day)

            moves = session.query(CashMove).filter((CashMove.day == day) & (CashMove.kind == "withdrawal")).all()
            withdrawals_total = sum((Decimal(str(m.amount or 0)) for m in moves), Decimal("0.00")).quantize(
                Decimal("0.01")
            )

            expected_cash_end = (opening_cash + Decimal(str(t["cash_total"] or 0)) - withdrawals_total).quantize(
                Decimal("0.01")
            )

            diff: Decimal | None = None
            if cash_counted_d is not None:
                diff = (cash_counted_d - expected_cash_end).quantize(Decimal("0.01"))
                if diff != 0 and not bool(force):
                    return {
                        "ok": False,
                        "error": f"Diferencia en caja: $ {diff} (contado - esperado).",
                        "expected_cash_end": float(expected_cash_end),
                        "cash_diff": float(diff),
                        "needs_force": True,
                    }

            # Next day's opening:
            carry_d = cash_counted_d if cash_counted_d is not None else expected_cash_end

            row = CashClose(
                day=day,
                opening_cash=opening_cash,
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

            # Persist next day's opening for UI convenience.
            try:
                next_day = self._next_day(day)
                next_row = self._ensure_cash_day(session, next_day)
                next_row.opening_cash = carry_d
                next_row.opening_cash_manual = 0
                next_row.updated_at = datetime.utcnow()
            except Exception:
                pass

            msg = None
            if cash_counted_d is not None and (diff is None or diff == 0):
                msg = "Todo cuadra. Mucha chamba por hoy, hora de dormir."

            export_res = None
            try:
                sync = self._load_excel_sync()
                last_path = (sync.get("last_excel_path") or "").strip()
                if bool(sync.get("auto_export_on_close", True)) and last_path:
                    export_res = self._export_inventory_to_excel_path(last_path)
            except Exception:
                export_res = None

            return {
                "ok": True,
                "id": int(row.id),
                "created_at": row.created_at.strftime("%Y-%m-%d %H:%M"),
                "day": row.day,
                "expected_cash_end": float(row.expected_cash_end),
                "carry_to_next_day": float(row.carry_to_next_day),
                "cash_diff": float(row.cash_diff) if row.cash_diff is not None else None,
                "message": msg,
                "excel_export": export_res,
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
        try:
            file_name = _ask_open_filename("Importar desde Excel", [("Excel", "*.xlsx"), ("Todos", "*.*")])
        except Exception as e:
            return {"ok": False, "error": str(e)}
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

            # Remember this Excel path for future exports.
            try:
                sync = self._load_excel_sync()
                sync["last_excel_path"] = str(Path(file_name).resolve())
                if "auto_export_on_close" not in sync:
                    sync["auto_export_on_close"] = True
                self._save_excel_sync(sync)
            except Exception:
                pass

            return {"ok": True, "imported": int(len(products)), "upserted": int(changed)}
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def exportExcelSelect(self):
        try:
            file_name = _ask_open_filename(
                "Exportar inventario a Excel (selecciona el archivo)",
                [("Excel", "*.xlsx"), ("Todos", "*.*")],
            )
        except Exception as e:
            return {"ok": False, "error": str(e)}
        if not file_name:
            return {"ok": False, "error": "Exportación cancelada"}

        res = self._export_inventory_to_excel_path(file_name)
        if res.get("ok"):
            try:
                sync = self._load_excel_sync()
                sync["last_excel_path"] = str(Path(file_name).resolve())
                if "auto_export_on_close" not in sync:
                    sync["auto_export_on_close"] = True
                self._save_excel_sync(sync)
            except Exception:
                pass
        return res

    def exportExcelToLast(self):
        sync = self._load_excel_sync()
        last_path = (sync.get("last_excel_path") or "").strip()
        if not last_path:
            return {
                "ok": False,
                "error": f"No hay Excel configurado aún.\n\nOpciones:\n- En el PC del servidor: usa 'Exportar Excel' y selecciona el archivo.\n- O coloca el Excel aquí: {self._default_excel_path()}\n\nLuego, al cerrar caja se exporta automático.",
            }
        return self._export_inventory_to_excel_path(last_path)

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
