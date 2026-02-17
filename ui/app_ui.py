import os
from typing import Any, Dict

import psycopg2
from psycopg2.extras import RealDictCursor
from flask import Flask, jsonify, request, send_from_directory

DB_HOST = os.getenv("DOCMOST_DB_HOST", "db")
DB_PORT = int(os.getenv("DOCMOST_DB_PORT", "5432"))
DB_NAME = os.getenv("DOCMOST_DB_NAME", "docmost")
DB_USER = os.getenv("DOCMOST_DB_USER", "docmost")
DB_PASS = os.getenv("DOCMOST_DB_PASSWORD", "STRONG_DB_PASSWORD")

UI_LISTEN_HOST = os.getenv("UI_LISTEN_HOST", "0.0.0.0")
UI_LISTEN_PORT = int(os.getenv("UI_LISTEN_PORT", "8090"))

app = Flask(__name__, static_folder="static", static_url_path="/static")


def _conn():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        cursor_factory=RealDictCursor,
    )


@app.get("/health")
def health():
    return jsonify({"ok": True})


@app.get("/")
def index():
    return send_from_directory("static", "index.html")


@app.get("/api/spaces")
def api_spaces():
    sql = """
        SELECT id, name, slug
        FROM public.spaces
        WHERE deleted_at IS NULL
        ORDER BY created_at ASC, id ASC
    """
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall() or []

    spaces = [
        {"id": str(r["id"]), "name": r.get("name") or "", "slug": r.get("slug") or ""}
        for r in rows
    ]
    return jsonify({"ok": True, "spaces": spaces})


@app.get("/api/spaces/<space_id>/pages")
def api_space_pages(space_id: str):
    sql = """
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
    """
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


@app.post("/api/chat")
def api_chat():
    # Placeholder: wire to your model workflow later.
    data = request.get_json(silent=True) or {}
    return jsonify(
        {
            "ok": True,
            "reply": "CHAT BACKEND NOT IMPLEMENTED YET",
            "echo": {
                "space": data.get("space"),
                "selected_pages": data.get("selected_pages", []),
                "message": data.get("message", ""),
            },
        }
    )


if __name__ == "__main__":
    app.run(host=UI_LISTEN_HOST, port=UI_LISTEN_PORT)
