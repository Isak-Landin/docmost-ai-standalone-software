import os
import psycopg2

from typing import Any, Dict, List, Tuple, Optional

import uuid
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
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor,
    )


def get_spaces(space_id: Optional[str] = None) -> Dict[str, Any]:
    if space_id:
        sql = """
            SELECT id, name, created_at, updated_at, visibility
            FROM public.spaces
            WHERE id = %s
              AND deleted_at IS NULL
            ORDER BY created_at ASC
        """
        params = (space_id,)
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
            cur.execute(sql, params) if params else cur.execute(sql)
            rows = cur.fetchall()

    if not rows:
        return {}

    contents: Dict[str, Any] = {}
    for row in rows:
        contents[str(row["id"])] = {
            "name": row["name"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "visibility": row["visibility"],
        }
    return contents


def get_pages(spaces_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Input: output of get_spaces()
    Output:
      {
        space_id: {
          page_id: { ...page meta... },
          ...
        },
        ...
      }
    """
    if not spaces_dict:
        return {"error": "No spaces provided", "message": "spaces_dict was empty", "value": None}

    contents: Dict[str, Any] = {}

    # Use one connection for all spaces
    with _conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            for space_id, space_meta in spaces_dict.items():
                # Validate space_id
                if not space_id:
                    contents.setdefault("_errors", []).append(
                        {
                            "error": "Invalid space_id",
                            "message": "Encountered falsy space_id key in spaces_dict",
                            "value": {"space_id": space_id, "space_meta": space_meta},
                        }
                    )
                    continue

                sql = """
                    SELECT id, title, parent_page_id, creator_id, space_id, created_at, updated_at
                    FROM public.pages
                    WHERE space_id = %s
                      AND deleted_at IS NULL
                    ORDER BY created_at ASC
                """
                cur.execute(sql, (space_id,))
                rows = cur.fetchall()

                # Always initialize the container for this space_id
                contents[space_id] = {}

                for row in rows:
                    page_id = str(row["id"])
                    contents[space_id][page_id] = {
                        "title": row["title"],
                        "parent_page_id": row["parent_page_id"],
                        "creator_id": row["creator_id"],
                        "space_id": row["space_id"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                    }

    return contents


def get_contents(
        pages_by_space: Optional[Dict[str, Any]] = None,
        *,
        space_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    If pages_by_space is provided, fetch content for those page IDs.
    If not provided but space_id is provided, the function will:
      1) get_spaces(space_id)
      2) get_pages_in_space(...)
      3) fetch content for the discovered pages

    Output:
      {
        space_id: {
          page_id: {
            ...page meta...,
            "text_content": "...",
            "content_updated_at": ...
          }
        }
      }
    """
    if not pages_by_space:
        if not space_id:
            return {
                "error": "Missing input",
                "message": "Provide pages_by_space or space_id",
                "value": None,
            }

        spaces = get_spaces(space_id)
        if not spaces:
            return {
                "error": "Space not found",
                "message": "No space returned for provided space_id",
                "value": {"space_id": space_id},
            }

        pages_by_space = get_pages(spaces)
        if "error" in pages_by_space:
            return pages_by_space

    # Collect page IDs per space
    out: Dict[str, Any] = {}

    with _conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            for sid, pages in pages_by_space.items():
                if sid == "_errors":
                    out["_errors"] = pages_by_space["_errors"]
                    continue

                if not isinstance(pages, dict):
                    out.setdefault("_errors", []).append(
                        {
                            "error": "Invalid pages structure",
                            "message": "Expected dict of page_id -> meta",
                            "value": {"space_id": sid, "pages": pages},
                        }
                    )
                    continue

                page_ids = [uuid.UUID(pid) for pid in pages.keys()]
                out[sid] = {}

                if not page_ids:
                    continue

                # IMPORTANT: Docmost schema may store content in a different table/column.
                # This assumes public.pages has text_content. If not, change this SQL to the correct table.
                sql = """
                    SELECT id, title, text_content, updated_at
                    FROM public.pages
                    WHERE id = ANY(%s)
                      AND deleted_at IS NULL
                """
                cur.execute(sql, (page_ids,))
                rows = cur.fetchall()
                content_by_id = {str(r["id"]): r for r in rows}

                for pid, meta in pages.items():
                    row = content_by_id.get(pid)
                    out[sid][pid] = dict(meta)
                    if row:
                        title = row["title"]
                        print("Name of file: " + title)
                        text_content = row.get("text_content")

                        refactored_text_content = refactor_content(text_content)

                        out[sid][pid]["text_content"] = refactored_text_content
                        out[sid][pid]["content_updated_at"] = row.get("updated_at")
                    else:
                        out[sid][pid]["text_content"] = None
                        out[sid][pid]["content_updated_at"] = None

    return out


# ---------------------------------------- #
# ------ SPACES SPECIFIC FUNCTIONS ------- #
# ---------------------------------------- #
def get_space_id_from_page_id(_page_id):
    if type(_page_id) != uuid:
        _page_id = uuid.UUID(_page_id).hex
    sql = """
        SELECT space_id
        FROM public.pages
        WHERE id = %s
        AND deleted_at IS NULL
    """

    param = (_page_id,)
    with _conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, param)
            rows = cur.fetchone()
            if rows:
                return rows["space_id"]
            else:
                return None


# ---------------------------------------- #
# --- END OF SPACES SPECIFIC FUNCTIONS --- #
# ---------------------------------------- #

# ---------------------------------------- #
# ------ PAGES SPECIFIC FUNCTIONS -------- #
# ---------------------------------------- #

"""
Output expected for pages - should be applied throughout all functions for pages:
      {
        space_id: {
          page_id: {
            ...page meta...,
            "text_content": "...",
            "content_updated_at": ...
          }
        }
      }
"""


# TODO - DONE - This also matches the output expectations for page content format expectations
def get_single_page_content(_page_id):
    if type(_page_id) != uuid.UUID:
        _page_id = uuid.UUID(_page_id)

    sql = """
        Select id, text_content, space_id
        FROM public.pages
        WHERE id = %s
        AND deleted_at IS NULL
    """

    params = _page_id

    with _conn() as c:
        with c.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql, (params,))
            row = cur.fetchone()
            if row:
                __content = refactor_content(row["text_content"])
                __space_id = str(row["space_id"])
                __page_id = str(row["id"])

                sql_meta = """
                    SELECT title, parent_page_id, creator_id, created_at, updated_at
                    FROM public.pages
                    WHERE id = %s
                    AND deleted_at IS NULL
                """
                cur.execute(sql_meta, (params,))
                __meta = cur.fetchone()

                output = {
                    __space_id: {
                        __page_id: {

                        }
                    }
                }

                output[__space_id][__page_id] = __meta
                output[__space_id][__page_id]["text_content"] = __content
                return output
            else:
                return None


def refactor_content(_text_content):
    _last_char_list = []
    _reformated_text = ""
    for char in _text_content:
        should_append = True
        try:
            if len(_last_char_list) >= 2:
                if char == "+" and _last_char_list[-1] == "+" and _last_char_list[-2] == "+":
                    should_append = False
                elif char == "\n" and _last_char_list[-1] == "\n":
                    should_append = False
            if should_append:
                _reformated_text += char

            _last_char_list.append(char)
        except IndexError as e:
            print("IndexError: ", e)
            continue
        except Exception as e:
            print("Other error when refactoring text content: ", e)
            continue

    return _reformated_text


# ---------------------------------------- #
# --- END OF PAGES SPECIFIC FUNCTIONS ---- #
# ---------------------------------------- #


# ---------------------------------------- #
# ------------ GENERAL TOOLS ------------- #
# ---------------------------------------- #

def verify_dictionary_of_type(_dict, _type: str):
    types_allowed = (
        "content_single",
        "content_multi",
        "page_single",
        "page_multi",
        "space_single",
        "space_multi",
    )

    if type(_dict) != dict:
        return {
            "error": f"Passed dict is not a dictionary: {_dict}",
            "message": "You passed an incorrect dict when attempting to verify dictionary structure",
            "value": f"{_dict}",
            "allowed": "type == dict",
        }

    if _type not in types_allowed:
        return {
            "error": f"Passed type is not allowed",
            "message": "You passed an incorrect type when attempting to verify dictionary structure",
            "value": f"{_type}",
            "allowed": str(types_allowed),
        }

    if _type == "content_single":




# ---------------------------------------- #
# -------- END OF GENERAL TOOLS  --------- #
# ---------------------------------------- #