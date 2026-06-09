The system is a server bridge plus a client-side helper. The model talks only to the helper; the helper talks to the server over REST; the server talks to Docmost and to its own bridge database.

## Layer overview

```
  Claude Code (model)
        |  stdio (mcp__docmost-helper__*)
        v
  docmost-helper  (helper/server.py)        owns local replica file IO
        |  REST  /v1  /helper/v1  /auto-mcp
        v
  docmost-mcp container  (FastAPI, app/main.py)
    REST reads              -> app/query/*
    bridge writes           -> app/bridge/services/*
    helper CRUD + reconcile -> app/helper_api, app/reconcile
    batch + observe         -> app/auto_mcp
    legacy client sync      -> app/sync
    operator /mcp           -> app/mcp_server
        |  psycopg2 (read)          |  bridge state (psycopg2)
        v                           v
  Docmost PostgreSQL          bridge PostgreSQL (bridge-db)
        ^  Docmost REST API (writes)
        |
  docmost-mcp-worker  (app/observer/worker.py)   interval observer over ALL spaces

```

## Containers

| Service | Container | Purpose |
| --- | --- | --- |
| `bridge-db` | `docmost-mcp-bridge-db` | PostgreSQL 16 holding bridge-owned version state |
| `docmost-mcp` | `docmost-mcp` | FastAPI app: REST + helper routes + operator `/mcp` |
| `docmost-mcp-worker` | `docmost-mcp-worker` | `app.observer.worker --loop`, observes every space on an interval |

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| `app/main.py` | App factory, router registration, `/mcp` mount, MCP session lifespan |
| `app/query/docmost.py` | Direct Docmost DB reads; ProseMirror -> markdown render |
| `app/query/prosemirror.py` | Deterministic ProseMirror-JSON to markdown renderer; faithful inverse of Docmost's `marked` ingest (structure-preserving, position-aware escaping) |
| `app/query/db.py` | Docmost DB connection / DSN, `DocmostConnectionError` |
| `app/query/replica.py` | Server-side replica structure / standards (operator + `/sync`) |
| `app/write/docmost.py` | Docmost REST write client |
| `app/bridge/services/write_pipeline.py` | All bridge writes: intents / receipts, canonical finalize, rollback |
| `app/bridge/services/canonical.py` | The single revision-hash derivation point |
| `app/bridge/services/versioning.py` | `revision_hash`, head-alignment checks, snapshots |
| `app/bridge/services/observer.py` | Folds external / manual Docmost edits into bridge state; `force_rerender` (used by `resync_space`) re-anchors every head by re-rendering, bypassing the updated-at gate |
| `app/bridge/services/bootstrap.py` | `ensure_space_bootstrapped` backfill |
| `app/bridge/repositories/` | Bridge tables access layer |
| `app/reconcile/` | Three-way classification brain + reconcile / resolve / confirm-deletion |
| `app/helper_api/` | Helper-facing CRUD + snapshot routes (`/v1`, `/helper/v1`) |
| `app/auto_mcp/` | Batch apply + observe (`/auto-mcp`) |
| `app/sync/` | Legacy client-state sync routes |
| `app/contract.py` | `/v1/contract` handshake, `/v1/health` |
| `app/observer/worker.py` | Interval observer loop over all spaces |
| `app/mcp_server.py` | Operator `/mcp` surface + operator-only instructions |

## Request flows

- Read (REST or helper): router -> `app/query/docmost.py` -> Docmost DB -> ProseMirror rendered to markdown -> Pydantic model.
- Write (helper / auto-mcp / direct CRUD): all converge on `app/bridge/services/write_pipeline.py`, which records a write intent, calls the Docmost REST API, finalizes the head from a canonical Docmost read-back, and confirms the intent. Caller mode `helper` / `auto_sync` requires head alignment; `crud` does not.
- Reconcile: the helper posts the local page set plus the last-synced tree to `app/reconcile`; the brain classifies each page three-way and applies clean one-sided changes, returning four buckets.
- Observe: the worker calls `observe_space` for each space, confirming pending bridge writes and recording outside changes. `resync_space` calls the same `observe_space` with `force_rerender=True` to re-render and re-anchor every page before reconciling.

## Networking

All three containers join the external Docker network named by `DOCMOST_NETWORK_NAME` (default `docmost_default`), the same network as the Docmost stack. The Docmost PostgreSQL container is reachable at `DOCMOST_DB_HOST`; the Docmost web app at `DOCMOST_APP_URL`. The API is published on `EXTERNAL_PORT` (default 8099).