# Architecture

## Layer overview

```
MCP client / REST client
        │
        │  HTTPS / MCP over streamable HTTP  (remote machine)
        ▼
┌──────────────────────────────────────────────────────────────┐
│  docmost-mcp container  (same server as Docmost)             │
│                                                              │
│  FastAPI app  (app/main.py)                                  │
│    ├── /health              → app/query/routers/health.py    │
│    ├── /spaces/* (read)     → app/query/routers/*            │
│    ├── /replica/*           → app/query/routers/replica.py   │
│    ├── /spaces/*/sync/*     → app/sync/routers.py            │
│    ├── /spaces/* (write)    → app/write/routers/*            │
│    ├── /auto-mcp/*          → app/auto_mcp/routers.py        │
│    ├── /helper/v1/*         → app/helper_api/routers.py      │
│    └── /mcp                 → FastMCP sub-app (mcp_server.py) │
│                                                              │
│  Read path     (app/query/)                                  │
│    └── space/page/tree queries, prosemirror→markdown         │
│  Write path    (app/bridge/services/write_pipeline.py)       │
│    └── records bridge state, then calls Docmost REST         │
│  Sync engine   (app/sync/service.py)                         │
│    └── local-vs-remote classification, diff, pull, push      │
│  Bridge state  (app/bridge/, bridge PostgreSQL)              │
│    └── page heads, version history, write intents/receipts,  │
│        observer checkpoints, local page snapshots            │
└───────┬───────────────────────────────────┬──────────────────┘
        │  TCP / PostgreSQL (read)           │  HTTPS REST (write + single-page read)
        ▼                                    ▼
  Docmost PostgreSQL container         Docmost REST API
```

## How it integrates with Docmost

Docmost is separate upstream software. This service does not modify it. It reads Docmost's
PostgreSQL database directly for list and tree queries, and uses Docmost's own REST API for
single-page content reads and for all writes. The bridge keeps its own separate PostgreSQL
database for version and sync state.

## Module responsibilities

| Module | Responsibility |
|---|---|
| `app/main.py` | FastAPI app factory, router registration, MCP session lifespan |
| `app/mcp_server.py` | FastMCP instance, MCP tool definitions, transport security config |
| `app/models.py` | Public Pydantic input/output models (spaces, pages, replica, sync) |
| `app/schemas/` | REST write and auto-mcp request/response schemas |
| `app/query/db.py` | Docmost read-database DSN construction and `get_conn()` context manager |
| `app/query/docmost.py` | SQL queries for spaces and pages, tree builder, error types |
| `app/query/replica.py` | Replica naming standard, directory-name resolver, replica structure builder |
| `app/query/prosemirror.py` | ProseMirror JSON to markdown conversion |
| `app/query/routers/*` | Read routes: health, spaces, pages, replica |
| `app/docmost_auth/auth.py` | Docmost REST login and in-memory token handling |
| `app/write/docmost.py` | Docmost REST client for create, update, delete operations |
| `app/write/mappers.py` | Maps Docmost REST / bridge results to output models |
| `app/write/routers/*` | Write routes: spaces, pages |
| `app/bridge/db/` | Bridge-database connection and schema bootstrap |
| `app/bridge/repositories/*` | Bridge state access: heads, versions, write intents/receipts, checkpoints, snapshots |
| `app/bridge/services/write_pipeline.py` | Records bridge state around each remote Docmost write |
| `app/bridge/services/*` | Normalization, revision hashing, diffing, bootstrap, observer, reconciliation |
| `app/sync/service.py` | Local-vs-remote sync classification, diff, pull, and push planning |
| `app/sync/routers.py` | Sync routes: status, diff, local-pages, pull, push |
| `app/auto_mcp/routers.py` | Automation routes: batch page apply, observe pass |
| `app/helper_api/routers.py` | Helper-facing REST routes (`/helper/v1`) for reads, writes, and snapshots |
| `app/observer/worker.py` | CLI entrypoint to run one observer pass for a space |

## Request flow (REST read)

1. FastAPI router handler receives the request
2. Read handlers call `app/query/docmost.py` (or `app/query/replica.py` for replica routes)
3. `docmost.py` opens a Docmost-DB connection via `app/query/db.get_conn()`, runs SQL, closes it
4. Single-page content is fetched via Docmost REST and converted from ProseMirror JSON to markdown
5. Row/response data is mapped to Pydantic models and returned as JSON

## Request flow (write)

1. A write handler (REST, MCP tool, sync push, or helper route) calls the bridge write pipeline
2. The pipeline records the intended write in the bridge database
3. It calls `app/write/docmost.py`, which authenticates and forwards to the Docmost REST API
4. On success it records the resulting version and head in the bridge database; on failure it compensates
5. The result is mapped to an output model and returned

## Networking

The container must share a Docker network with Docmost (`docmost_default` by default). The Docmost
PostgreSQL container is reachable inside that network at the hostname set by `DOCMOST_DB_HOST`, and
the Docmost web app at `DOCMOST_APP_URL`. The bridge database runs as its own service on the same
network. The MCP/REST endpoint is exposed externally via `EXTERNAL_PORT` (default 8099).
