The service uses two PostgreSQL databases. It never alters the Docmost schema.

## Docmost database (read path)

Implemented in `app/query/db.py` and `app/query/docmost.py`. The bridge connects directly to the live Docmost database with `psycopg2` and a `RealDictCursor` (rows returned as dicts), runs read-only `SELECT` queries for spaces and pages, and renders page content from Docmost's stored ProseMirror JSON to markdown (`app/query/prosemirror.py`).

```python
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(...)
        rows = cur.fetchall()

```

`get_conn()` constructs the DSN, opens a connection, yields it, commits on success, rolls back and raises `DocmostConnectionError` on `psycopg2.OperationalError`, and always closes the connection. Routers and tools translate `DocmostConnectionError` into a `503` (REST) or a tool error.

Writes to Docmost do not go through this DB layer - they go through the Docmost REST API (`app/write/docmost.py`).

## Bridge database (version state)

Implemented under `app/bridge/db/`. A separate PostgreSQL database (the `bridge-db` service) holds all bridge-owned state. Its schema is applied from `migrations/bridge/*.sql` on first use by `app/bridge/db/schema.py` (`ensure_schema`, idempotent `CREATE TABLE IF NOT EXISTS` / `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`).

Tables (see the Data Models page for columns):

| Table | Holds |
| --- | --- |
| `page_versions` | append-only version history |
| `page_heads` | current head per page |
| `write_intents` | every attempted bridge write |
| `write_receipts` | pending write confirmations |
| `observer_checkpoints` | last-seen Docmost update + observed hash per page |
| `local_page_snapshots` | helper stash snapshots |

## Notes

- All database access is synchronous (`psycopg2`); there is no connection pool - each request opens and closes its own connection.
- Docmost reads are read-only; bridge writes commit normally.
- Deleted Docmost rows are excluded by `deleted_at IS NULL`; bridge deletions are tracked by the `is_deleted` flag on `page_heads`.