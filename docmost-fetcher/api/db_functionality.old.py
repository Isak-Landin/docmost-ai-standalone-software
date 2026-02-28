import os
import psycopg2

from typing import Any, Dict, Optional

import uuid
from psycopg2.extras import RealDictCursor

from utils.schema_db_validation_management import validate_dict, refactor_content
import logging

logger = logging.getLogger(__name__)

DB_URL = os.environ.get("DB_URL", "")
DB_HOST = os.getenv("DOCMOST_DB_HOST", "db")
DB_PORT = int(os.getenv("DOCMOST_DB_PORT", "5432"))
DB_NAME = os.getenv("DOCMOST_DB_NAME", "docmost")
DB_USER = os.getenv("DOCMOST_DB_USER", "docmost")
DB_PASS = os.getenv("DOCMOST_DB_PASSWORD", "STRONG_DB_PASSWORD")

allowed_types = (
    "content_single",
    "content_multi",
    "page_single",
    "page_multi",
    "space_single",
    "space_multi",
)

def _conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor,
    )


def get_space(space_id: str) -> tuple[bool, dict[Any, Any]]:
    pass

def get_spaces(space_id: Optional[str] = None) -> tuple[bool, dict[Any, Any]]:
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


def get_page(page_id: str) -> tuple[bool, dict[Any, Any]]:
    pass

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


def get_content(_page_id: str) -> tuple[bool, dict[Any, Any]]:
    if type(_page_id) != uuid.UUID:
        try:
            _page_id = uuid.UUID(_page_id)
        except ValueError:
            return False, {
                "error": "Invalid page_id type",
                "message": "Encountered incorrect page_id key type in _page_id, expected str(uuid.UUID)",
                "value": f"{_page_id}",
            }

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
                            key: val for key, val in __meta.items()
                        }
                    }
                }

                output[__space_id][__page_id]["text_content"] = __content
                return output
            else:
                # TODO verify that we are not intending to build a replacement dict as empty output
                return None

def get_contents(
        pages_by_space: Optional[Dict[str, Any]] = None, *, space_id: Optional[str] = None,
) -> tuple[bool, dict[Any, Any]]:
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
            "content_updated_at": ...,
          }
        }
      }
    """
    if not pages_by_space:
        if not space_id:
            return False, {
                "error": "Missing input",
                "message": "Provide pages_by_space or space_id",
                "value": None,
            }

        spaces = get_spaces(space_id)
        if not spaces:
            logger.warning(f"No spaces found for {space_id}")
            return False, {
                "error": f"No spaces found for given space_id {space_id}",
                "message": "Provide space_id",
                "value": None,
            }

        pages_by_space = get_pages(spaces)

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
    # Before returning out, ensure the formatting of multi_pages_content are according to formatting expectations
    this_type = allowed_types[allowed_types.index("content_multi")]
    is_valid, is_valid_message = validate_dict(out, this_type)
    if is_valid:
        return True, out
    else:
        return False, {
            "error": "Invalid multi_content structure",
            "message": f"validate_dict has discarded the formatting as invalid {str(is_valid_message)}",
            "value": f"{out}",
        }



