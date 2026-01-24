from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)

    producto: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=False, default="")

    unidades: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    precio_final: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    # Optional manual categorization (used by the HTML UI filters)
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="")

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)

    image: Mapped["ProductImage"] = relationship("ProductImage", back_populates="product", uselist=False)


class ProductImage(Base):
    __tablename__ = "product_images"

    product_key: Mapped[str] = mapped_column(
        String(255), ForeignKey("products.key", ondelete="CASCADE"), primary_key=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)

    product: Mapped[Product] = relationship("Product", back_populates="image")


class Sale(Base):
    __tablename__ = "sales"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    # Payment info (optional)
    payment_method: Mapped[str] = mapped_column(String(20), nullable=False, default="cash")
    cash_received: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    change_given: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    lines: Mapped[list["SaleLine"]] = relationship("SaleLine", back_populates="sale", cascade="all, delete-orphan")


class SaleLine(Base):
    __tablename__ = "sale_lines"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(Integer, ForeignKey("sales.id", ondelete="CASCADE"), nullable=False, index=True)

    product_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    producto: Mapped[str] = mapped_column(String(255), nullable=False)
    descripcion: Mapped[str] = mapped_column(Text, nullable=True)

    qty: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    sale: Mapped[Sale] = relationship("Sale", back_populates="lines")

    __table_args__ = (
        UniqueConstraint("sale_id", "id", name="uq_sale_line"),
    )


class CashClose(Base):
    __tablename__ = "cash_closes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)

    # ISO date string (YYYY-MM-DD) representing the day being closed.
    day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)

    # Cash drawer state for the day
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    withdrawals_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    gross_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    cash_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    card_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    nequi_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    virtual_total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    # Expected cash in drawer after sales/withdrawals (opening + cash_sales - withdrawals)
    expected_cash_end: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    # How much cash will remain in the drawer for next day (defaults to expected_cash_end)
    carry_to_next_day: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))

    cash_counted: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cash_diff: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class CashDay(Base):
    __tablename__ = "cash_days"

    # ISO date string (YYYY-MM-DD)
    day: Mapped[str] = mapped_column(String(10), primary_key=True)
    opening_cash: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    # True when user explicitly set opening_cash; otherwise auto from previous day.
    opening_cash_manual: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)


class CashMove(Base):
    __tablename__ = "cash_moves"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=False), nullable=False, default=datetime.utcnow)

    # ISO date string (YYYY-MM-DD)
    day: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="withdrawal")
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=Decimal("0.00"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
