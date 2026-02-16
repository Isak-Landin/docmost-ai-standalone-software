import os
from typing import Any, Dict

import psycopg
from psycopg.extras import RealDictCursor
from flask import Flask, request, jsonify

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


def get_all_spaces_pages() -> Dict[str, Any]:
    sql_spaces = """
        SELECT
            id,
            name,
        FROM spaces
    """
    with _conn() as c:
        with c.cursor() as cur:
            cur.execute(sql)
            rows = cur.fetchall()

    if not rows:
        return {"ok": False, "error": "not_found"}

    spaces = {}
    increment = 0
    for row in rows:
	space = {
		"id": str(row["id"]),
		"name": str(row["name"]),
		}

	spaces[increment] = space
	increment += 1

    return {
	"ok": True,
	"spaces": spaces,
    }
