from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator

import psycopg2
from psycopg2 import OperationalError
from psycopg2.extras import RealDictCursor
from psycopg2.extensions import connection as PgConnection

from app.bridge.errors import BridgeConfigurationError


class BridgeConnectionError(BridgeConfigurationError):
    """Raised when the bridge-owned database cannot be reached."""


def _get_dsn() -> str:
    url = (os.getenv("BRIDGE_DB_URL") or "").strip()
    if url:
        return url

    host = (os.getenv("BRIDGE_DB_HOST") or "").strip()
    port = (os.getenv("BRIDGE_DB_PORT") or "5432").strip()
    dbname = (os.getenv("BRIDGE_DB_NAME") or "").strip()
    user = (os.getenv("BRIDGE_DB_USER") or "").strip()
    password = os.getenv("BRIDGE_DB_PASSWORD", "")
    if host and dbname and user:
        return f"postgresql://{user}:{password}@{host}:{port}/{dbname}"

    raise BridgeConnectionError(
        "Bridge database configuration is missing. Set BRIDGE_DB_URL or BRIDGE_DB_HOST/PORT/NAME/USER/PASSWORD."
    )


@contextmanager
def get_conn() -> Iterator[PgConnection]:
    conn = None
    try:
        conn = psycopg2.connect(_get_dsn(), cursor_factory=RealDictCursor)
        yield conn
        conn.commit()
    except BridgeConnectionError:
        if conn is not None:
            conn.rollback()
        raise
    except OperationalError as exc:
        if conn is not None:
            conn.rollback()
        raise BridgeConnectionError("Bridge database connection failed") from exc
    except Exception:
        if conn is not None:
            conn.rollback()
        raise
    finally:
        if conn is not None:
            conn.close()
