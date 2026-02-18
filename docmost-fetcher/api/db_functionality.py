import os
import psycopg2

from typing import Any, Dict, List
from psycopg2.extras import RealDictCursor, RealDictRow
from uuid import UUID

DB_URL = os.environ.get("DB_URL", "")
DB_HOST = os.getenv("DOCMOST_DB_HOST", "db")
DB_PORT = int(os.getenv("DOCMOST_DB_PORT", "5432"))
DB_NAME = os.getenv("DOCMOST_DB_NAME", "docmost")
DB_USER = os.getenv("DOCMOST_DB_USER", "docmost")
DB_PASS = os.getenv("DOCMOST_DB_PASSWORD", "STRONG_DB_PASSWORD")

def _conn():
    return psycopg2.connect(
        DB_URL,
        cursor_factory=RealDictCursor
    )

def get_spaces(space_id=None):
    _space_id = space_id
    sql = """
    SELECT id, name
    FROM public.spaces
    WHERE deleted_at IS NULL
    ORDER BY created_at ASC
    """

    if _space_id:
        sql = f"""
        SELECT id, name
        FROM public.spaces
        WHERE id = {_space_id}
        WHERE deleted_at IS NULL
        ORDER BY created_at ASC
        """
    contents = {}
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql)
            rows: RealDictRow = cur.fetchall()
            if rows.__len__() == 0:
                return {}
            if not rows or rows:
                return {}
            else:
                for row in rows:
                    contents[row["id"]] = row["name"]

                return contents

def get_pages_in_space(space_id):
    sql = f"""
    SELECT id, title, space_id
    FROM public.pages
    WHERE deleted_at IS NULL
    AND space_id = {space_id}
    """
    contents = {
        f"{space_id}": {}
    }
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, {"space_id": space_id})
            rows: RealDictRow = cur.fetchall()
            if rows.__len__() == 0:
                return {}
            if not rows or rows:
                return {}
            else:
                for row in rows:
                    contents[f"{space_id}"][row["id"]] = row["title"]

    return contents

def get_pages_content(space_ids: List[UUID]):
    _space_ids = space_ids
    contents = {}
    for _id in _space_ids:

        sql = f"""
        SELECT id, text_content
        FROM public.pages
        WHERE id = {_id}
        WHERE deleted_at IS NULL
        """
        with _conn() as c:
            with c.cursor() as cur:
                r = cur.execute(sql)
                row = r.fetchone()
                if not row:
                    continue
                if not row["id"] or not row["text_content"]:
                    continue
                if row["id"] and row["text_content"]:
                    contents[row["id"]] = row["text_content"]

    return contents

