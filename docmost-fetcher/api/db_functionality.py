import os
import psycopg2

from typing import Any, Dict, List
from psycopg2.extras import RealDictCursor
from uuid import UUID


DB_HOST = os.getenv("DOCMOST_DB_HOST", "db")
DB_PORT = int(os.getenv("DOCMOST_DB_PORT", "5432"))
DB_NAME = os.getenv("DOCMOST_DB_NAME", "docmost")
DB_USER = os.getenv("DOCMOST_DB_USER", "docmost")
DB_PASS = os.getenv("DOCMOST_DB_PASSWORD", "STRONG_DB_PASSWORD")

def _conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor,
    )

def get_spaces(id=None):
    space_id = id
    sql = """
    SELECT id, name
    FROM public.spaces
    WHERE deleted_at IS NULL
    ORDER BY created_at ASC
    """

    if space_id:
        sql = f"""
        SELECT id, name
        FROM public.spaces
        WHERE id = {space_id}
        WHERE deleted_at IS NULL
        ORDER BY created_at ASC
        """

    with _conn() as c:
        with c.cursor() as cur:
            if space_id:
                cur.execute(sql, {"space_id": space_id})
            else:
                cur.execute(sql)
            rows = cur.fetchall()
            if not rows or rows == []:
                return None
            else:
                return rows

def get_pages_in_space(space_id):
    sql = f"""
    SELECT id, title, 
    """

def get_pages_content(space_ids: List[UUID]):
    _space_ids = space_ids
    for _id in _space_ids:

        sql = f"""
        SELECT id, text_content
        FROM public.pages
        WHERE id = {_id}
        WHERE deleted_at IS NULL
        """
        contents = []
        with _conn() as c:
            with c.cursor() as cur:
                r = cur.execute(sql)

                if r.rowcount == 0:
                    contents.append()

                row = r.fetchone()

