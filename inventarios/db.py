from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from inventarios.models import Base


def create_engine_from_url(database_url: str) -> Engine:
    # sqlite pragmas: WAL improves concurrency; foreign_keys for integrity
    if database_url.startswith("sqlite:"):
        engine = create_engine(
            database_url,
            future=True,
            connect_args={"check_same_thread": False},
        )
        with engine.connect() as conn:
            conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
            conn.exec_driver_sql("PRAGMA foreign_keys=ON;")
        return engine

    return create_engine(database_url, future=True)


def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    _ensure_sqlite_schema(engine)


def _sqlite_columns(conn, table: str) -> set[str]:
    rows = conn.exec_driver_sql(f"PRAGMA table_info({table});").fetchall()
    return {str(r[1]) for r in rows}


def _ensure_sqlite_schema(engine: Engine) -> None:
    url = str(engine.url)
    if not url.startswith("sqlite:"):
        return

    with engine.connect() as conn:
        # products.category
        try:
            cols = _sqlite_columns(conn, "products")
            if "category" not in cols:
                conn.exec_driver_sql("ALTER TABLE products ADD COLUMN category VARCHAR(80) NOT NULL DEFAULT '';" )
        except Exception:
            # If table doesn't exist yet, create_all already handled it.
            pass

        # sales payment fields
        try:
            cols = _sqlite_columns(conn, "sales")
            if "payment_method" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE sales ADD COLUMN payment_method VARCHAR(20) NOT NULL DEFAULT 'cash';"
                )
            if "cash_received" not in cols:
                conn.exec_driver_sql("ALTER TABLE sales ADD COLUMN cash_received NUMERIC(12,2);")
            if "change_given" not in cols:
                conn.exec_driver_sql("ALTER TABLE sales ADD COLUMN change_given NUMERIC(12,2);")
        except Exception:
            pass

        # cash_closes extended fields (cierre de caja + retiros + arrastre)
        try:
            cols = _sqlite_columns(conn, "cash_closes")
            if "opening_cash" not in cols:
                conn.exec_driver_sql("ALTER TABLE cash_closes ADD COLUMN opening_cash NUMERIC(12,2) NOT NULL DEFAULT 0;")
            if "withdrawals_total" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE cash_closes ADD COLUMN withdrawals_total NUMERIC(12,2) NOT NULL DEFAULT 0;"
                )
            if "nequi_total" not in cols:
                conn.exec_driver_sql("ALTER TABLE cash_closes ADD COLUMN nequi_total NUMERIC(12,2) NOT NULL DEFAULT 0;")
            if "virtual_total" not in cols:
                conn.exec_driver_sql("ALTER TABLE cash_closes ADD COLUMN virtual_total NUMERIC(12,2) NOT NULL DEFAULT 0;")
            if "expected_cash_end" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE cash_closes ADD COLUMN expected_cash_end NUMERIC(12,2) NOT NULL DEFAULT 0;"
                )
            if "carry_to_next_day" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE cash_closes ADD COLUMN carry_to_next_day NUMERIC(12,2) NOT NULL DEFAULT 0;"
                )
        except Exception:
            # Table may not exist yet; create_all handles it.
            pass

        # cash_days: track manual opening override
        try:
            cols = _sqlite_columns(conn, "cash_days")
            if "opening_cash_manual" not in cols:
                conn.exec_driver_sql(
                    "ALTER TABLE cash_days ADD COLUMN opening_cash_manual INTEGER NOT NULL DEFAULT 0;"
                )
        except Exception:
            pass

        conn.commit()


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
