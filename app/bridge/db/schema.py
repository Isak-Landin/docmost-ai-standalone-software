from __future__ import annotations

from pathlib import Path
from threading import Lock

from app.bridge.db.connection import get_conn

_SCHEMA_READY = False
_SCHEMA_LOCK = Lock()


def ensure_schema() -> None:
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return

    with _SCHEMA_LOCK:
        if _SCHEMA_READY:
            return
        sql_path = Path(__file__).resolve().parents[3] / "migrations" / "bridge" / "001_initial.sql"
        sql = sql_path.read_text(encoding="utf-8")
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
        _SCHEMA_READY = True
