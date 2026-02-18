import os
import psycopg2
from psycopg2.extras import RealDictCursor
from flask import jsonify

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

def test_query():
    space_id = id
    sql = """
    SELECT id, name
    FROM public.spaces
    WHERE deleted_at IS NULL
    ORDER BY created_at ASC
    """

    with _conn() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        print(rows)
        for row in rows:
            print(row["id"])
            print(row["name"])

if __name__ == '__main__':
    test_query()