import os
from typing import Any, Dict, List

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import jsonify

from datetime import datetime

DB_URL="postgresql://docmost:STRONG_DB_PASSWORD@64.112.126.69:54327/docmost"
DB_HOST="db"
DB_PORT="54327"
DB_NAME="docmost"
DB_USER="docmost"
DB_PASS=""


def _conn():
    return psycopg2.connect(
        DB_URL,
        cursor_factory=RealDictCursor
    )

def get_spaces(space_id = None) -> dict[str, Any]:
    # Dict[str, Dict[str, str, datetime, datetime, str]]
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


def get_pages_in_space(dict_space_id) -> dict[str, Any]:
    """
    Expects format from get_spaces, this is important in case of direct usage from get_pages_content

    @dict_space_id -
        {
            space_id: {
                name: string,
                created_at: Datetime,
                updated_at: Datetime,
                visibility: string
            },
            // if get_spaces called without id, all pages below will be presented too, else only first match
            space_id: {
                name: string,
                created_at: Datetime,
                updated_at: Datetime,
                visibility: string
            },
            space_id: {
                name: string,
                created_at: Datetime,
                updated_at: Datetime,
                visibility: string
            },
            space_id: {
                name: string,
                created_at: Datetime,
                updated_at: Datetime,
                visibility: string
            }
        }
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

def get_pages_content (page_ids_space: Dict = None, space_id: str = None):
    """
    Expects format from get_pages_in_space, should use directly if not passed from ui
    {
        space_id: {
            page_id: {
                title: string,
                parent_page_id: string,
                creator_id: string,
                space_id: string,
                created_at: Datetime,
                updated_at: Datetime,
            },
            page_id: {
                title: string,
                parent_page_id: string,
                creator_id: string,
                space_id: string,
                created_at: Datetime,
                updated_at: Datetime,
            }
        },
        space_id: {
            page_id: {
                title: string,
                parent_page_id: string,
                creator_id: string,
                space_id: string,
                created_at: Datetime,
                updated_at: Datetime,
            }
        }
    }
    """
    _page_ids_space = page_ids_space
    _space_id = space_id
    contents = {}

    target = None

    if not _page_ids_space:
        if not _space_id:
            return {
                "error": "Missing both page_ids_space (page ids in list) and _space_id",
                "message": "Must provide space_id or list of space_ids (_page_ids_space)"
            }

        _space_dict = get_spaces(_space_id)
        if "error" in _space_dict:
            try:
                value = _space_dict["error"]
            except KeyError:
                value = None
            return {
                "error": f"Getting space dict from space_id rendered an error or did not find any results",
                "message": "Make sure that the space_id exists",
                "value": value
            }
        if not _space_dict:
            return {
                "error": f"No result for _space_id",
                "message": f"When querying for the space information, we could not find any result for {_space_id}"
            }
        _pages_in_space = None
        try:
            _pages_in_space = get_pages_in_space(_space_dict)
        except KeyError as e:
            return {
                "error": f"{str(e)} - {_pages_in_space}",
                "message": "Make sure that the space_id exists"
            }

    return contents








if __name__ == '__main__':
    spaces = get_spaces("019baa5d-007c-7d12-9671-af7cf1b3061a")
    print(spaces)