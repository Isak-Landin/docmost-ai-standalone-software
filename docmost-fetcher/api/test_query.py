from typing import Any, Dict, Optional
from datetime import datetime
import uuid
from psycopg2.extras import register_uuid

import psycopg2
from psycopg2.extras import RealDictCursor


DB_URL = "postgresql://docmost:STRONG_DB_PASSWORD@64.112.126.69:54327/docmost"

register_uuid()

def _conn():
    return psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)


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


def get_pages_in_space(spaces_dict: Dict[str, Any]) -> Dict[str, Any]:
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


def get_pages_content(
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

        pages_by_space = get_pages_in_space(spaces)
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
                

                # DOING BUG TESTING WITH LIMITED OUTDATA
                LIMITER = 0
                for pid, meta in pages.items():
                    row = content_by_id.get(pid)
                    out[sid][pid] = dict(meta)
                    if row:
                        title = row["title"]
                        print("Name of file: " + title)
                        text_content = row.get("text_content")

                        refactored_text_content = refactor_content_extras(text_content)
                        print("refactored_text_content: " + refactored_text_content)

                        out[sid][pid]["text_content"] = refactored_text_content
                        out[sid][pid]["content_updated_at"] = row.get("updated_at")
                    else:
                        out[sid][pid]["text_content"] = None
                        out[sid][pid]["content_updated_at"] = None

                    LIMITER += 1
                    if LIMITER == 3:
                        break

    return out

def refactor_content_extras(_text_content):
    _last_char = ""
    _reformated_text = ""
    for char in _text_content:
        if char == "\n":
            pass
        elif char == "+":
            pass

        if char == "\n" and _last_char == "\n":
            continue
        _last_char = char
        _reformated_text += char

    return _reformated_text

if __name__ == "__main__":
    space_id = "019baa5f-2451-7287-8189-847a31a7e8ae"

    spaces = get_spaces()

    pages = get_pages_in_space(spaces)

    content = get_pages_content(pages)