from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.sqlite import insert

from inventarios.excel_import import ImportedProduct
from inventarios.models import Product, ProductImage, Sale, SaleLine


@dataclass(frozen=True)
class TopProduct:
    product_key: str
    producto: str
    qty: int
    total: Decimal


class ProductRepo:
    def __init__(self, session: Session):
        self.session = session

    def upsert_many(self, products: list[ImportedProduct]) -> int:
        if not products:
            return 0

        # Excel sheets can contain repeated product keys; keep the last occurrence.
        dedup: dict[str, ImportedProduct] = {}
        for p in products:
            dedup[p.key] = p
        products = list(dedup.values())

        # Fast path for SQLite: single executemany UPSERT.
        bind = self.session.get_bind()
        if bind is not None and getattr(bind.dialect, "name", "") == "sqlite":
            now = datetime.utcnow()
            rows = []
            for p in products:
                rows.append(
                    {
                        "key": p.key,
                        "producto": p.producto,
                        "descripcion": p.descripcion,
                        "unidades": int(p.unidades),
                        "precio_final": Decimal(str(p.precio_final)).quantize(Decimal("0.01")),
                        "category": "",  # only applies on insert; updates keep existing
                        "updated_at": now,
                    }
                )

            stmt = insert(Product).values(rows)
            # Do NOT overwrite manual category on update.
            stmt = stmt.on_conflict_do_update(
                index_elements=[Product.key],
                set_={
                    "producto": stmt.excluded.producto,
                    "descripcion": stmt.excluded.descripcion,
                    "unidades": stmt.excluded.unidades,
                    "precio_final": stmt.excluded.precio_final,
                    "updated_at": stmt.excluded.updated_at,
                },
            )
            self.session.execute(stmt)
            return len(products)

        # Generic fallback (non-sqlite)
        keys = [p.key for p in products]
        existing = {
            p.key: p
            for p in self.session.execute(select(Product).where(Product.key.in_(keys))).scalars().all()
        }

        changed = 0
        now = datetime.utcnow()
        for p in products:
            row = existing.get(p.key)
            if row is None:
                row = Product(
                    key=p.key,
                    producto=p.producto,
                    descripcion=p.descripcion,
                    unidades=int(p.unidades),
                    precio_final=Decimal(str(p.precio_final)).quantize(Decimal("0.01")),
                    category="",
                    updated_at=now,
                )
                self.session.add(row)
                changed += 1
            else:
                row.producto = p.producto
                row.descripcion = p.descripcion
                row.unidades = int(p.unidades)
                row.precio_final = Decimal(str(p.precio_final)).quantize(Decimal("0.01"))
                row.updated_at = now
                changed += 1

        return changed

    def list(self, q: str = "", limit: int = 300) -> list[Product]:
        stmt = select(Product)
        qn = (q or "").strip()
        if qn:
            like = f"%{qn}%"
            stmt = stmt.where((Product.producto.like(like)) | (Product.descripcion.like(like)))
        stmt = stmt.order_by(Product.producto.asc()).limit(int(limit))
        return self.session.execute(stmt).scalars().all()

    def list_categories(self) -> list[str]:
        stmt = (
            select(func.trim(Product.category))
            .where(func.trim(Product.category) != "")
            .group_by(func.trim(Product.category))
            .order_by(func.trim(Product.category).asc())
        )
        rows = [str(r[0]) for r in self.session.execute(stmt).all() if r and r[0]]
        return rows

    def set_category(self, product_key: str, category: str) -> bool:
        k = (product_key or "").strip()
        if not k:
            return False
        row = self.session.execute(select(Product).where(Product.key == k)).scalar_one_or_none()
        if row is None:
            return False
        row.category = (category or "").strip()
        row.updated_at = datetime.utcnow()
        return True

    def get_by_keys(self, keys: list[str]) -> dict[str, Product]:
        if not keys:
            return {}
        rows = self.session.execute(select(Product).where(Product.key.in_(keys))).scalars().all()
        return {r.key: r for r in rows}

    def set_image(self, product_key: str, path: str) -> None:
        img = self.session.get(ProductImage, product_key)
        if img is None:
            self.session.add(ProductImage(product_key=product_key, path=path))
        else:
            img.path = path

    def get_image(self, product_key: str) -> str | None:
        img = self.session.get(ProductImage, product_key)
        return img.path if img else None


class SalesRepo:
    def __init__(self, session: Session):
        self.session = session

    def create_sale(
        self,
        *,
        lines: list[dict],
        total: Decimal,
        payment_method: str = "cash",
        cash_received: Decimal | None = None,
        change_given: Decimal | None = None,
    ) -> Sale:
        sale = Sale(
            total=total,
            payment_method=(payment_method or "cash"),
            cash_received=cash_received,
            change_given=change_given,
        )
        for ln in lines:
            sale.lines.append(
                SaleLine(
                    product_key=ln["product_key"],
                    producto=ln["producto"],
                    descripcion=ln.get("descripcion"),
                    qty=int(ln["qty"]),
                    unit_price=ln["unit_price"],
                    line_total=ln["line_total"],
                )
            )
        self.session.add(sale)
        self.session.flush()
        return sale

    def totals_for_day(self, day_iso: str) -> dict:
        day = (day_iso or "").strip()
        if not day:
            return {
                "gross_total": Decimal("0.00"),
                "cash_total": Decimal("0.00"),
                "card_total": Decimal("0.00"),
                "nequi_total": Decimal("0.00"),
                "virtual_total": Decimal("0.00"),
                "sales_count": 0,
            }

        # SQLite: date(created_at) yields YYYY-MM-DD
        sums_stmt = (
            select(
                Sale.payment_method,
                func.coalesce(func.sum(Sale.total), 0),
            )
            .where(func.date(Sale.created_at) == day)
            .group_by(Sale.payment_method)
        )
        sums = {str(method or "cash"): Decimal(str(total or 0)) for method, total in self.session.execute(sums_stmt).all()}

        cnt = self.session.execute(select(func.count(Sale.id)).where(func.date(Sale.created_at) == day)).scalar_one()

        cash_total = sums.get("cash", Decimal("0"))
        card_total = sums.get("card", Decimal("0"))
        nequi_total = sums.get("nequi", Decimal("0"))
        virtual_total = sums.get("virtual", Decimal("0"))
        gross_total = (cash_total + card_total + nequi_total + virtual_total).quantize(Decimal("0.01"))

        return {
            "gross_total": Decimal(str(gross_total)).quantize(Decimal("0.01")),
            "cash_total": Decimal(str(cash_total)).quantize(Decimal("0.01")),
            "card_total": Decimal(str(card_total)).quantize(Decimal("0.01")),
            "nequi_total": Decimal(str(nequi_total)).quantize(Decimal("0.01")),
            "virtual_total": Decimal(str(virtual_total)).quantize(Decimal("0.01")),
            "sales_count": int(cnt),
        }

    def list_sales_summary(self, limit: int = 200) -> list[dict]:
        lim = max(1, min(int(limit or 200), 500))
        stmt = (
            select(
                Sale.id,
                Sale.created_at,
                Sale.total,
                func.coalesce(func.count(SaleLine.id), 0),
                Sale.payment_method,
            )
            .select_from(Sale)
            .outerjoin(SaleLine, SaleLine.sale_id == Sale.id)
            .group_by(Sale.id)
            .order_by(Sale.created_at.desc())
            .limit(lim)
        )
        rows = self.session.execute(stmt).all()
        out: list[dict] = []
        for sale_id, created_at, total, items, payment_method in rows:
            out.append(
                {
                    "id": int(sale_id),
                    "created_at": created_at,
                    "total": Decimal(str(total)).quantize(Decimal("0.01")),
                    "items": int(items),
                    "payment_method": str(payment_method or "cash"),
                }
            )
        return out

    def list_sales(self, limit: int = 200) -> list[Sale]:
        stmt = select(Sale).order_by(Sale.created_at.desc()).limit(int(limit))
        return self.session.execute(stmt).scalars().all()

    def total_sold(self) -> Decimal:
        v = self.session.execute(select(func.coalesce(func.sum(Sale.total), 0))).scalar_one()
        return Decimal(str(v)).quantize(Decimal("0.01"))

    def total_sold_by_day(self, limit_days: int = 30) -> list[tuple[date, Decimal]]:
        # SQLite date() groups by day in UTC-ish local, adequate for POS.
        stmt = (
            select(func.date(Sale.created_at), func.coalesce(func.sum(Sale.total), 0))
            .group_by(func.date(Sale.created_at))
            .order_by(func.date(Sale.created_at).desc())
            .limit(int(limit_days))
        )
        rows = self.session.execute(stmt).all()
        out: list[tuple[date, Decimal]] = []
        for d, total in rows:
            out.append((date.fromisoformat(d), Decimal(str(total)).quantize(Decimal("0.01"))))
        return out

    def top_products(self, limit: int = 10) -> list[TopProduct]:
        stmt = (
            select(
                SaleLine.product_key,
                SaleLine.producto,
                func.coalesce(func.sum(SaleLine.qty), 0),
                func.coalesce(func.sum(SaleLine.line_total), 0),
            )
            .group_by(SaleLine.product_key, SaleLine.producto)
            .order_by(func.sum(SaleLine.line_total).desc())
            .limit(int(limit))
        )
        rows = self.session.execute(stmt).all()
        out: list[TopProduct] = []
        for key, producto, qty, total in rows:
            out.append(
                TopProduct(
                    product_key=str(key),
                    producto=str(producto),
                    qty=int(qty),
                    total=Decimal(str(total)).quantize(Decimal("0.01")),
                )
            )
        return out
