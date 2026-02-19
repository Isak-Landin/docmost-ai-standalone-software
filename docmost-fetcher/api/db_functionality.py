import os
import psycopg2

from typing import Any, Dict, List, Tuple

from psycopg2.extras import RealDictCursor, RealDictRow
from uuid import UUID
from datetime import datetime

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

def get_spaces(space_id: str = None):
    """
    This function is used to retrieve specific information about one or all spaces.
    @space_id: type str
    return: Dict[]
    """
    _space_id = space_id
    if _space_id:
        sql = """
            SELECT id, name, created_at, updated_at, visibility
            FROM public.spaces
            WHERE id = %s
              AND deleted_at IS NULL
            ORDER BY created_at ASC
        """
        params = (_space_id,)
    else:
        sql = """
            SELECT id, name, created_at, updated_at, visibility
            FROM public.spaces
            WHERE deleted_at IS NULL
            ORDER BY created_at ASC
        """
        params = None

    with _conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            if params:
                cur.execute(sql, params)
            else:
                cur.execute(sql)

            rows = cur.fetchall()
            if not rows:
                return {}

            contents = {}

            for row in rows:
                contents[row["id"]] = {
                    "name": row["name"], "created_at": row["created_at"], "updated_at": row["updated_at"], "visibility": row["visibility"]
                }
            return contents

def get_pages_in_space(dict_space_id: Dict[Any, Any]):
    """
    This function is used to retrieve specific information about one or all pages per space id passed.
    @dict_space_id: type dict
    return: Dict[_space_id, Dict[, Any]]
    """
    _space_id = None
    contents = {}
    _space_id_not_found = 1
    for key, value in dict_space_id.items():
        if not _space_id:
            if not value:
                value = None
            contents[f"error_{_space_id_not_found}"] = {
                "error": "No space_id provided",
                "message": "We expected",
                "key": _space_id,
                "value": value
            }

            _space_id_not_found += 1

        _space_id = str(key)
        contents[_space_id] = {}

        sql = f"""
            SELECT id, title, parent_page_id, creator_id, space_id, created_at, updated_at
            FROM public.pages
            WHERE space_id = %s
                AND deleted_at IS NULL
            ORDER BY created_at ASC
        """

        params = (_space_id,)

        with _conn() as c:
            with c.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()

                if not rows:
                    contents[_space_id] = None
                else:
                    for row in rows:
                        contents[_space_id][row["id"]] = {
                            "title": row["title"],
                            "parent_page_id": row["parent_page_id"],
                            "creator_id": row["creator_id"],
                            "space_id": row["space_id"],
                            "created_at": row["created_at"],
                            "updated_at": row["updated_at"],
                        }

    return contents


def get_pages_content(space_id, page_ids: List[UUID]):
    _space_id = space_id
    _page_ids = page_ids
    contents = {}
    for _id in page_ids:

        sql = f"""
        SELECT
        id,
        space_id,
        title,
        text_content,
        content,
        updated_at,
        deleted_at
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

