import os
from typing import Any, Dict

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, request, jsonify

DB_HOST = os.getenv("DOCMOST_DB_HOST", "db")
DB_PORT = int(os.getenv("DOCMOST_DB_PORT", "5432"))
DB_NAME = os.getenv("DOCMOST_DB_NAME", "docmost")
DB_USER = os.getenv("DOCMOST_DB_USER", "docmost")
DB_PASS = os.getenv("DOCMOST_DB_PASSWORD", "STRONG_DB_PASSWORD")

LISTEN_HOST = os.getenv("UI_LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("UI_LISTEN_PORT", "8099"))

spaces_path = os.getenv("SPACES_PATH", "/api/spaces")

app = Flask(__name__)

def _conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor,
    )


def get_content(space_id: str, page_id: str) -> Dict[str, Any]:
    sql = """
        SELECT
            id,
            space_id,
            title,
            text_content,
            content,
            updated_at,
            deleted_at
        FROM public.pages
        WHERE id = %(page_id)s AND space_id = %(space_id)s
        LIMIT 1
    """
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, {"page_id": page_id, "space_id": space_id})
            row = cur.fetchone()

    if not row:
        return {"ok": False, "error": "not_found"}

    return {
        "ok": True,
        "page": {
            "id": str(row["id"]),
            "space_id": str(row["space_id"]),
            "title": row.get("title"),
            "updated_at": row["updated_at"].isoformat() if row.get("updated_at") else None,
            "deleted_at": row["deleted_at"].isoformat() if row.get("deleted_at") else None,
            "text_content": row.get("text_content") or "",
            "content": row.get("content") or {},
        },
    }



@app.get("/")
def http_home_list_spaces():
    return jsonify(spaces())

@app.get("/get-content")
def http_get_content():
    space_id = request.args.get("space_id", "").strip()
    page_id = request.args.get("page_id", "").strip()
    if not space_id or not page_id:
        return jsonify({"ok": True})
    return jsonify(get_content(space_id=space_id, page_id=page_id))

"""def get_all_spaces() -> Dict[str, Any]:
    sql_spaces = '''
        SELECT
            id,
            name
        FROM public.spaces
        WHERE deleted_at IS NULL
        ORDER BY created_at ASC
    '''

    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql_spaces)
            rows = cur.fetchall()

    if not rows:
        return {"ok": True, "spaces": []}

    spaces = []
    for row in rows:
        spaces.append({
            "id": str(row["id"]),
            "name": row["name"],
        })

    return {
        "ok": True,
        "spaces": spaces,
    }"""

@app.get("/health")
def health():
    return jsonify({"ok": True})

"""
@app.get("/api/spaces")
def spaces():
    spaces_response = request.get(SPACES_ALL_ENDPOINT)

    reponse = {
        "ok": True,
        "spaces": spaces_response.json() if spaces_response.status_code == 200 else [],
    }
    return jsonify(reponse)


@app.get("/api/spaces/<space_id>/pages")
def api_space_pages(space_id: str):
    sql = '''
        SELECT
            id,
            space_id,
            slug_id,
            title,
            parent_page_id,
            updated_at
        FROM public.pages
        WHERE space_id = %(space_id)s
          AND deleted_at IS NULL
        ORDER BY parent_page_id NULLS FIRST,
                 title ASC NULLS LAST,
                 id ASC
    '''
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql, {"space_id": space_id})
            rows = cur.fetchall() or []

    pages = []
    for r in rows:
        pages.append(
            {
                "id": str(r["id"]),
                "space_id": str(r["space_id"]),
                "slug_id": r.get("slug_id") or "",
                "title": r.get("title") or "",
                "parent_page_id": str(r["parent_page_id"])
                if r.get("parent_page_id")
                else None,
                "updated_at": r["updated_at"].isoformat() if r.get("updated_at") else None,
            }
        )

    return jsonify({"ok": True, "pages": pages})
"""

if __name__ == "__main__":
    app.run(host=LISTEN_HOST, port=LISTEN_PORT)
