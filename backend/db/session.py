import os
from contextlib import contextmanager
from typing import Iterator, Optional

import psycopg2
from psycopg2.extensions import connection as PgConnection


def _get_dsn() -> str:
    dsn = (os.getenv("DAH_DB_URL") or "").strip()
    if not dsn:
        raise RuntimeError("DAH_DB_URL is required (env)")
    return dsn


@contextmanager
def get_conn(*, autocommit: bool = False) -> Iterator[PgConnection]:
    """
    Application DB connection only.
    No pooling in MVP. Caller controls transaction boundaries via commit/rollback.
    """
    conn: Optional[PgConnection] = None
    try:
        conn = psycopg2.connect(_get_dsn())
        conn.autocommit = autocommit
        yield conn
        if not autocommit:
            conn.commit()
    except Exception:
        if conn is not None and not conn.autocommit:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()
