from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from inventarios.models import Product
from inventarios.repos import ProductRepo, SalesRepo


def money(x: float | Decimal) -> Decimal:
    d = x if isinstance(x, Decimal) else Decimal(str(x))
    return d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class CheckoutResult:
    ok: bool
    error: str | None = None
    details: list[dict] | None = None
    sale_id: int | None = None
    total: Decimal | None = None
    payment_method: str | None = None
    cash_received: Decimal | None = None
    change_given: Decimal | None = None


class PosService:
    def __init__(self, session: Session):
        self.session = session
        self.products = ProductRepo(session)
        self.sales = SalesRepo(session)

    def checkout(
        self,
        cart: dict[str, int],
        *,
        payment_method: str = "cash",
        cash_received: float | Decimal | None = None,
    ) -> CheckoutResult:
        cart = {k: int(v) for k, v in (cart or {}).items() if int(v) > 0}
        if not cart:
            return CheckoutResult(ok=False, error="Carrito vacío")

        pm = (payment_method or "cash").strip().lower()
        if pm not in {"cash", "card", "nequi", "virtual"}:
            return CheckoutResult(ok=False, error="Método de pago inválido")

        by_key = self.products.get_by_keys(list(cart.keys()))
        missing = [k for k in cart.keys() if k not in by_key]
        if missing:
            return CheckoutResult(ok=False, error=f"Productos no encontrados: {missing}")

        insufficient: list[dict] = []
        for k, qty in cart.items():
            p = by_key[k]
            if p.unidades < qty:
                insufficient.append(
                    {
                        "key": k,
                        "producto": p.producto,
                        "available": p.unidades,
                        "requested": qty,
                    }
                )
        if insufficient:
            return CheckoutResult(ok=False, error="Stock insuficiente", details=insufficient)

        lines: list[dict] = []
        total = Decimal("0.00")
        for k, qty in cart.items():
            p: Product = by_key[k]
            unit = money(p.precio_final)
            line_total = (unit * Decimal(qty)).quantize(Decimal("0.01"))
            total += line_total
            lines.append(
                {
                    "product_key": p.key,
                    "producto": p.producto,
                    "descripcion": p.descripcion,
                    "qty": int(qty),
                    "unit_price": unit,
                    "line_total": line_total,
                }
            )

        # Apply stock updates
        for k, qty in cart.items():
            by_key[k].unidades = int(by_key[k].unidades - qty)

        cash_received_d: Decimal | None = None
        change_given: Decimal | None = None
        if pm == "cash":
            if cash_received is not None:
                cash_received_d = money(cash_received)
                if cash_received_d < total:
                    return CheckoutResult(ok=False, error="Efectivo insuficiente")
                change_given = money(cash_received_d - total)

        sale = self.sales.create_sale(
            lines=lines,
            total=total,
            payment_method=pm,
            cash_received=cash_received_d,
            change_given=change_given,
        )
        return CheckoutResult(
            ok=True,
            sale_id=sale.id,
            total=total,
            payment_method=pm,
            cash_received=cash_received_d,
            change_given=change_given,
        )
