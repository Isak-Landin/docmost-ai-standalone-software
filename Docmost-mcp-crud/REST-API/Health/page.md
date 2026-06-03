## `GET /health`

Returns `{"ok": true}` when the service process is running and reachable.

This is a process-level liveness check only. It does not verify Docmost or bridge database connectivity. A reachable `/health` with failing reads means the process is up but a database is unreachable (read routes then return `503`).

```json
{"ok": true}

```

Implementation: `app/query/routers/health.py` returns a `JSONResponse` directly - no database call, no model validation.

## `GET /v1/health`

The helper-facing contract surface (`app/contract.py`) also exposes `GET /v1/health` returning `{"ok": true}`, alongside `GET /v1/contract` (the helper <-> server version handshake). The helper performs a best-effort `/v1/contract` check on startup and warns on stderr if the contract version differs.