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

LISTEN_HOST = os.getenv("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("LISTEN_PORT", "8099"))

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

@app.get("/get-content")
def http_get_content():
    space_id = request.args.get("space_id", "").strip()
    page_id = request.args.get("page_id", "").strip()
    if not space_id or not page_id:
        
    return jsonify(get_content(space_id=space_id, page_id=page_id))

@app.get("/health")
def health():
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(host=LISTEN_HOST, port=LISTEN_PORT)
