from __future__ import annotations


def money_es(n: float) -> str:
    # 12.345,67 format
    return f"{n:,.2f}".replace(",", "_").replace(".", ",").replace("_", ".")
