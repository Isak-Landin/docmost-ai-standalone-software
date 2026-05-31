# Database Layer

The service uses two separate PostgreSQL databases:

1. **Docmost read database** - the live Docmost database, accessed read-only for list and tree queries.
2. **Bridge state database** - a separate database owned by this service for version and sync state.

## Docmost read database (`app/query/db.py`)

Provides a single context manager for acquiring and releasing connections to the Docmost
PostgreSQL database.

```python
with get_conn() as conn:
    with conn.cursor() as cur:
        cur.execute(...)
        rows = cur.fetchall()
```

`get_conn()`:
1. Constructs the DSN from env vars (see [Configuration](../Configuration/page.md); `DOCMOST_DB_URL` takes priority)
2. Opens a `psycopg2` connection with `RealDictCursor` (rows returned as dicts)
3. Yields the connection
4. On success: commits the transaction
5. On `OperationalError`: rolls back and raises `DocmostConnectionError`
6. On any other exception: rolls back and re-raises
7. Always closes the connection in the `finally` block

### Scope and cursor type

- Access to the Docmost database is **read-only** (`SELECT`). The service never writes to the Docmost
  database directly - all Docmost writes go through the Docmost REST API.
- Single-page content is **not** read from the database; it is fetched via Docmost REST and converted
  from ProseMirror JSON to markdown. The list and tree queries use the database.
- `RealDictCursor` returns rows as `dict` objects so they can be passed directly to Pydantic models.

### Error type

| Exception | Raised when |
|---|---|
| `DocmostConnectionError` | `psycopg2.OperationalError` occurs (connection refused, bad credentials, network failure) |

Routers and MCP tools catch `DocmostConnectionError` and convert it to a `503` HTTP error or a
`ToolError` respectively.

## Bridge state database (`app/bridge/db/connection.py`)

A separate PostgreSQL database, configured independently (see the `BRIDGE_DB_*` variables in
[Configuration](../Configuration/page.md)). It uses its own `get_conn()` context manager with the
same commit/rollback/close semantics, and raises `BridgeConnectionError` when its configuration is
missing or the database is unreachable.

The bridge schema is applied on first use by executing the SQL files in `migrations/bridge/`. This
database holds the bridge-owned version and sync state and is read and written by the service.

## Notes

- All database access is synchronous (`psycopg2`).
- There is no connection pool; each request opens and closes its own connection.
