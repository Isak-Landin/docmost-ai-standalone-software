import json
from typing import Any, Dict, Optional, List
from datetime import datetime
import uuid
from psycopg2.extras import register_uuid

import psycopg2
from psycopg2.extras import RealDictCursor

from datetime import datetime

import logging
logger = logging.getLogger(__name__)


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
    if type(_page_id) != uuid.UUID:
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








# ---------------------------------------- #
# --- END OF PAGES SPECIFIC FUNCTIONS ---- #
# ---------------------------------------- #


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
            logger.warning(f"An Error occurred during runtime " + f"str(e)")
            print("Other error when refactoring text content: ", e)
            continue

    return _reformated_text







if __name__ == "__main__":
    space_id = "019baa5f-2451-7287-8189-847a31a7e8ae"
    single_page_id = "019baa5f-4a6f-72f6-bca4-fab6e32025b3"
    """
    spaces = get_spaces()

    pages = get_pages_in_space(spaces)
    content = get_pages_content(pages)
    """


    file_path_prod = "../backend/schemas/docmost_db_schemas/single_page_content.json"
    file_path_dev = "schemas/docmost_db_schemas/single_page_content.json"
    json_dev = {}





    def convert_schema_to_key_value_relation_list(root: dict):
        """
        Returns a list where index d contains:
          [[key types at depth d], [value types at depth d]]
        Aggregates across all dictionaries that exist at that depth.
        """

        if not isinstance(root, dict):
            raise TypeError("root must be a dict")

        relational_list = []
        q = deque([(root, 0)])

        while q:
            dct, __depth = q.popleft()

            # Ensure relational_list has an entry for this depth
            while len(relational_list) <= __depth:
                relational_list.append([[], []])  # [key_types, value_types]

            key_types, value_types = relational_list[__depth]

            for k, v in dct.items():
                key_types.append(type(k))
                value_types.append(type(v))

                # Continue traversal into nested dicts (all branches)
                if isinstance(v, dict):
                    q.append((v, __depth + 1))

                # Optional: if you also want to traverse dicts inside lists/tuples/sets
                elif isinstance(v, (list, tuple, set)):
                    for item in v:
                        if isinstance(item, dict):
                            q.append((item, __depth + 1))

        return relational_list



    content = get_single_page_content(single_page_id)

    # ------------ RULES ------------ #
    with open(file_path_dev, "r") as f:
        json_dev = json.load(f)

    __levels = depth(content)
    __count_key_value_per_level = []
    schema_to_list_ = convert_schema_to_key_value_relation_list(json_dev)
    # -------- END OF RULES --------- #

    print(schema_to_list_)

