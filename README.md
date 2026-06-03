# Docmost MCP

Docmost MCP is a bridge between a live Docmost deployment and an MCP-consuming model
(Claude Code). It reads Docmost content directly from Docmost's PostgreSQL database, writes
through Docmost's REST API, and keeps its own separate "bridge" PostgreSQL database for
version and sync state. On top of that it exposes a REST API, a set of helper-facing routes,
and an operator MCP endpoint.

The system has two halves:

- **Server** (this repo) - runs as containers next to a live Docmost stack. It owns Docmost
  connectivity, bridge version truth, content normalization, the reconcile brain, the REST and
  helper-facing routes, and a background observer worker.
- **Helper** (`helper/`) - a small client-side stdio MCP. It is the consuming model's ONLY
  Docmost surface. It owns all local replica file IO and runs the automated reconcile by
  calling the server over REST.

## Two consumer surfaces (read this first)

There are two MCP-shaped surfaces, and they are not interchangeable:

| Surface | Who uses it | Transport | Role |
|---|---|---|---|
| **docmost-helper** | the model (Claude Code) | stdio | The model's only Docmost surface. Reconcile-first reads, writes, and sync. |
| **`/mcp`** | a human operator | streamable HTTP | Quiet inspection / emergency override only. NOT the model's workflow surface. |

The helper reaches the server over REST (`/v1`, `/helper/v1`, `/auto-mcp`) - never over `/mcp`.
Do not register the operator `/mcp` HTTP MCP for the model. The model talks to `docmost-helper`,
which talks to the server. See `helper/README.md` for helper registration.

## Architecture

```
  Claude Code (model)
        |
        |  stdio (mcp__docmost-helper__*)
        v
  docmost-helper  (helper/server.py)            <-- the model's surface; owns local replica IO
        |
        |  REST  /v1  /helper/v1  /auto-mcp
        v
  +-----------------------------------------------------------+
  |  docmost-mcp container  (FastAPI, app/main.py)            |
  |    REST reads            -> app/query/*                   |
  |    bridge writes         -> app/bridge/services/*         |
  |    helper CRUD + reconcile -> app/helper_api, app/reconcile|
  |    batch + observe       -> app/auto_mcp                  |
  |    legacy client sync    -> app/sync                      |
  |    operator /mcp         -> app/mcp_server                |
  +----------+---------------------------+--------------------+
             | psycopg2 (read)           | bridge state (psycopg2)
             v                           v
     Docmost PostgreSQL          bridge PostgreSQL (bridge-db)
             ^
             | Docmost REST API (writes: create / update / move / delete)
             |
  docmost-mcp-worker  (app/observer/worker.py)  <-- interval observer over ALL spaces
```

### Containers (`docker-compose.yml`)

| Service | Container | Purpose |
|---|---|---|
| `bridge-db` | `docmost-mcp-bridge-db` | PostgreSQL 16 holding bridge-owned version state |
| `docmost-mcp` | `docmost-mcp` | FastAPI app: REST + helper routes + operator `/mcp` |
| `docmost-mcp-worker` | `docmost-mcp-worker` | `app.observer.worker --loop`: folds direct-Docmost-UI edits into bridge state every `WORKER_INTERVAL_SECONDS` (default 15s) over every space |

### Two databases

- **Docmost PostgreSQL** - the live Docmost database. The bridge reads pages and spaces from
  it directly (`app/query/docmost.py`) and writes through Docmost's REST API
  (`app/write/docmost.py`). The bridge never alters the Docmost schema.
- **Bridge PostgreSQL** (`bridge-db`) - bridge-owned state: page heads, version history, write
  intents/receipts, observer checkpoints, and local-page snapshots. Schema is applied from
  `migrations/bridge/*.sql` on first use (`app/bridge/db/schema.py`).

### Module map

| Path | Responsibility |
|---|---|
| `app/main.py` | FastAPI app factory, router registration, `/mcp` mount, MCP session lifespan |
| `app/query/docmost.py` | Direct Docmost DB reads (spaces, pages, tree); ProseMirror -> markdown render |
| `app/query/prosemirror.py` | Deterministic ProseMirror-JSON to markdown renderer (strips volatile node ids) |
| `app/query/db.py` | Docmost DB connection / DSN, `DocmostConnectionError` |
| `app/query/replica.py` | Server-side replica structure/standards (operator + `/sync` routes) |
| `app/query/routers/` | REST read routes: health, spaces, pages, replica |
| `app/write/docmost.py` | Docmost REST write client (create/update/move/delete page, create/delete space) |
| `app/write/routers/` | Direct REST write routes (`crud` caller mode) |
| `app/bridge/db/` | Bridge DB connection + schema bootstrap |
| `app/bridge/repositories/` | Bridge tables: page_heads, page_versions, write_intents, write_receipts, observer_checkpoints, snapshots |
| `app/bridge/services/write_pipeline.py` | All bridge writes: intents/receipts, canonical finalize, compensating rollback |
| `app/bridge/services/canonical.py` | The single revision-hash derivation point (Docmost read-back) |
| `app/bridge/services/versioning.py` | `revision_hash`, head-alignment checks, snapshots |
| `app/bridge/services/observer.py` | Folds external/manual Docmost edits into bridge state |
| `app/bridge/services/bootstrap.py` | `ensure_space_bootstrapped` - backfills existing spaces |
| `app/reconcile/` | The reconcile brain: three-way classification + `/reconcile`, `/resolve`, `/confirm-deletion` |
| `app/helper_api/` | Helper-facing CRUD + snapshot routes (`/v1`, `/helper/v1`) |
| `app/auto_mcp/` | Batch apply + observe routes (`/auto-mcp`) |
| `app/sync/` | Legacy client-state sync routes (`/spaces/{id}/sync/*`) |
| `app/contract.py` | `/v1/contract` version handshake, `/v1/health` |
| `app/observer/worker.py` | Interval observer loop over all spaces |
| `app/mcp_server.py` | Operator `/mcp` FastMCP surface + operator-only instructions |
| `migrations/bridge/*.sql` | Bridge database schema |
| `helper/server.py` | Helper stdio MCP tool definitions (the model's surface) |
| `helper/helper/client.py` | REST client to the server |
| `helper/helper/sync.py` | Helper reconcile pipeline + low-level escape hatches |
| `helper/helper/replica.py` | Local replica file IO, `_replica.json` discovery by space id |

## The bridge version model

Every page the bridge knows about has a **head** (`page_heads`) carrying a
`current_revision_hash`, plus an append-only `page_versions` history. The revision hash is:

```
revision_hash = sha256( canonical_title + "\n---\n" + canonical_content )
```

It is **bridge-internal** - it is never stored in Docmost. It is derived at exactly one place,
`app/bridge/services/canonical.py`, always from Docmost's stored content read back and rendered
to markdown (ProseMirror -> markdown, with volatile node ids stripped). Because every surface
(helper push, direct CRUD, the worker/observer, and direct Docmost-UI edits) ends up as the same
stored Docmost content and is hashed the same way, a write-origin head and an observe-origin head
for the same content are identical. There is no input-vs-rendered drift.

Writes go through `app/bridge/services/write_pipeline.py` in one of three caller modes:

- `helper` / `auto_sync` - require head alignment (an expected base revision hash) so a stale
  client cannot clobber a newer head.
- `crud` - no alignment requirement; used by the direct `/spaces/*` REST write routes.

The **worker** (`docmost-mcp-worker`) runs `observe_space` over every space on an interval. It
confirms pending bridge writes and records any change made outside the bridge (for example a
manual edit in the Docmost UI) as a new version with source `external_observer`. This means the
bridge tracks versions for all spaces whether or not a model has ever touched them, and a space
that already has content is backfilled on first contact.

## Normal workflow: reconcile

The model only initiates a sync; the helper plus the server reconcile brain do all versioning,
diffing, and file IO.

1. Edit `page.md` locally and/or restructure the replica (move a page directory to re-parent).
2. Call `sync_space(space_id)` (or `sync_page` / `sync_page_tree`) on `docmost-helper` with only
   the id(s).
3. The helper builds the local page set plus the last-synced `_tree.json`, calls
   `POST /v1/spaces/{id}/reconcile`, and applies the result locally: pushes local edits, creates
   local-only pages, pulls remote changes, materializes new remote pages, applies moves/re-parents,
   and aligns both the bridge head and the local `_meta.json` base revision hash.
4. The result returns `synced_count` plus `applied`, and only the items needing a decision:
   `conflicts` (each with `remote_content`, `local_content`, diff) and `deletion_confirmations`.
   - Conflict: inspect, then `resolve_conflict(space_id, page_id, merged_content)` (pushed aligned
     to the current remote head, no force).
   - Deletion: `confirm_deletion(space_id, page_id, direction)` (`remote` soft-deletes the remote
     page and drops the local copy; `local` accepts a remote deletion).

A clean sync needs no force and surfaces no conflicts. Classification is three-way (local vs
last-synced tree vs bridge head) across content, structure (parent/position/icon), and existence.

## Local replica (helper-owned)

The replica is a local directory tree the helper maintains; Docmost remains the long-term source
of truth. Each page is a directory containing:

- `page.md` - markdown content (owned by the helper and the model; edit locally, push via helper)
- `_meta.json` - page identity + sync base (owned by the helper; do not edit by hand)

The replica root also holds `_replica.json` (space header: `space_id`, `slug`, `name`) and
`_tree.json` (the last-synced tree snapshot). The helper resolves which replica to use by
scanning for a `_replica.json` whose `space_id` matches, under `DOCMOST_REPLICA_BASE` (default:
the helper's current working directory). Pass an explicit `local_root` to override.

In this repository the tracked replica of the service's own documentation space lives at
`Docmost-mcp-crud/`.

## REST surface

The REST API and helper-facing routes are served by FastAPI. The `/mcp` endpoint is the operator
surface only.

### Read routes (direct Docmost DB)

| Method | Path | Description |
|---|---|---|
| `GET` | `/health` | process liveness only (does not check the database) |
| `GET` | `/spaces` | list non-deleted spaces |
| `GET` | `/spaces/{space_id}` | get one space |
| `GET` | `/spaces/{space_id}/tree` | nested page tree |
| `GET` | `/spaces/{space_id}/pages` | flat page list |
| `GET` | `/spaces/{space_id}/pages/{page_id}` | one page with markdown content |
| `GET` | `/spaces/{space_id}/replica-structure` | server-side replica layout for a space |
| `GET` | `/replica/standards` | replica naming/structure/sync rules |
| `GET` | `/replica/resolve-directory-name` | resolve a local directory name for a title |

### Direct write routes (bridge pipeline, `crud` mode)

| Method | Path | Description |
|---|---|---|
| `POST` | `/spaces` | create a space |
| `DELETE` | `/spaces/{space_id}` | permanently delete a space and its pages |
| `POST` | `/spaces/{space_id}/pages` | create a page (add `parent_page_id` for a child) |
| `PUT` | `/spaces/{space_id}/pages/{page_id}` | update title and/or content (`replace`/`append`/`prepend`) |
| `DELETE` | `/spaces/{space_id}/pages/{page_id}` | soft-delete a page |

### Helper-facing routes (served under both `/v1` and `/helper/v1`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/v1/contract` | helper <-> server contract version + capabilities |
| `GET` | `/v1/health` | process health |
| `GET` | `/v1/spaces`, `/v1/spaces/{id}`, `/v1/spaces/{id}/tree` | reads |
| `GET` | `/v1/spaces/{id}/pages`, `/v1/spaces/{id}/pages/{pid}` | reads (page carries `current_revision_hash`) |
| `POST`/`DELETE` | `/v1/spaces`, `/v1/spaces/{id}` | create / delete space (`helper` mode) |
| `POST`/`PUT`/`DELETE` | `/v1/spaces/{id}/pages[...]` | create / update / delete page (`helper` mode) |
| `POST` | `/v1/spaces/{id}/pages/{pid}/move` | move / re-parent a page (id-preserving) |
| `POST`/`GET`/`DELETE` | `/v1/spaces/{id}/pages/{pid}/snapshots[...]` | local-page snapshots (stash) |
| `POST` | `/v1/spaces/{space_id}/reconcile` | classify + apply a scoped bidirectional reconcile (four buckets) |
| `POST` | `/v1/spaces/{id}/pages/{pid}/resolve` | resolve a conflict aligned to the current remote head |
| `POST` | `/v1/spaces/{id}/pages/{pid}/confirm-deletion` | apply a confirmed deletion (`remote`/`local`) |

### Automation + legacy sync routes

| Method | Path | Description |
|---|---|---|
| `POST` | `/auto-mcp/spaces/{space_id}/pages/apply` | batch create/update through the bridge pipeline |
| `POST` | `/auto-mcp/spaces/{space_id}/observe` | run one observer pass for a space |
| `POST` | `/spaces/{space_id}/sync/status` | client-state sync status |
| `POST` | `/spaces/{space_id}/sync/diff` | client-state diff hunks |
| `POST` | `/spaces/{space_id}/sync/local-pages` | plan a new local-only page |
| `POST` | `/spaces/{space_id}/sync/pull` | pull remote into a client working copy |
| `POST` | `/spaces/{space_id}/sync/push` | push a client working copy to remote |

All page content is markdown in and markdown out. The page title is a separate parameter - never
an H1 in the body. Use plain ASCII punctuation.

## Prerequisites

- A running Docmost environment with PostgreSQL. **Docmost v0.71.1 or later is required** for
  content write operations (older versions silently discard the `content` field).
- Docker and Docker Compose on the server that hosts Docmost.
- Network access from this service to the live Docmost PostgreSQL container.
- A separate PostgreSQL database for bridge-owned state (provided by the `bridge-db` service).

> **Checking your Docmost version**
>
> ```bash
> docker exec docmost cat /app/apps/server/package.json | grep '"version"' | head -1
> ```
>
> Docmost upgrades are non-destructive (data lives in PostgreSQL):
>
> ```bash
> docker compose pull docmost && docker compose up -d docmost
> ```

## Server setup

The server runs as three containers joined to the same external Docker network as Docmost.

### 1. Place the project on the Docmost host

```bash
git clone <repo-url> /opt/docmost-mcp && cd /opt/docmost-mcp
```

### 2. Confirm the shared Docker network

This project joins the external network named by `DOCMOST_NETWORK_NAME` (default
`docmost_default`). Find your Docmost network:

```bash
docker network ls | grep docmost
```

### 3. Create `.env`

```bash
cp env.example .env
```

Fill in the values:

```env
# Docmost database (read path). Use DOCMOST_DB_URL or the individual values.
DOCMOST_DB_URL=postgresql://docmost:STRONG_DB_PASSWORD@db:5432/docmost
DOCMOST_DB_HOST=db
DOCMOST_DB_PORT=5432
DOCMOST_DB_NAME=docmost
DOCMOST_DB_USER=docmost
DOCMOST_DB_PASSWORD=STRONG_DB_PASSWORD

# Bridge-owned state database (the bridge-db service)
BRIDGE_DB_URL=postgresql://docmost_bridge:STRONG_BRIDGE_DB_PASSWORD@bridge-db:5432/docmost_bridge
BRIDGE_DB_HOST=bridge-db
BRIDGE_DB_PORT=5432
BRIDGE_DB_NAME=docmost_bridge
BRIDGE_DB_USER=docmost_bridge
BRIDGE_DB_PASSWORD=STRONG_BRIDGE_DB_PASSWORD

# Docmost application (write path). Token is held in memory only.
DOCMOST_APP_URL=http://docmost:3000
DOCMOST_USER_EMAIL=<docmost-user-email>
DOCMOST_USER_PASSWORD=<docmost-user-password>

# Docker network shared with the Docmost stack
DOCMOST_NETWORK_NAME=docmost_default

# Bind + exposure
LISTEN_HOST=0.0.0.0
LISTEN_PORT=8099
EXTERNAL_PORT=8099

# MCP transport: Host headers the /mcp transport accepts (reverse proxy domain).
# Leave empty to disable DNS-rebinding protection (not recommended for production).
MCP_ALLOWED_HOSTS=mcp.yourdomain.com

# Worker observe interval (seconds)
WORKER_INTERVAL_SECONDS=15

MODE=prod
LOG_LEVEL=INFO
```

### 4. Build and start

```bash
docker compose up -d --build
```

This builds and starts `bridge-db`, `docmost-mcp`, and `docmost-mcp-worker`, attaches them to the
external Docmost network, and publishes the API on `EXTERNAL_PORT`.

### 5. Verify

```bash
docker compose ps
curl http://<host>:8099/health          # -> {"ok": true}  (process only)
curl http://<host>:8099/spaces          # -> 200 with spaces, or 503 if the DB is unreachable
```

- REST docs: `http://<host>:8099/docs`
- Operator MCP endpoint: `http://<host>:8099/mcp` (or `https://<host>/mcp` behind a proxy)

If the Docmost database is unreachable, read routes return `503` with
`{"detail":"Docmost database connection failed"}`.

### Behind a reverse proxy

Terminate TLS, expose a stable hostname, and forward `/mcp` plus the REST routes to the
container. Set `MCP_ALLOWED_HOSTS` to the proxied domain.

## Helper setup (the model's surface)

The helper runs on the machine where Claude Code runs. It does not host the bridge; it connects
to the already-running server and manages the local replica.

```bash
cd helper
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Set DOCMOST_MCP_SERVER_URL in helper/.env to the running server base URL.
# Optionally set DOCMOST_REPLICA_BASE to the directory that holds your replica(s).
```

Register `docmost-helper` as a **stdio** MCP in exactly one Claude Code scope:

- **User / home scope** (`$CLAUDE_CONFIG_DIR/.claude.json`, falling back to `~/.claude.json`):
  loads in every session. This is how the live environment is set up.
- **Project scope** (`.mcp.json` at a repo root): loads only in that directory.

```json
{
  "mcpServers": {
    "docmost-helper": {
      "type": "stdio",
      "command": "/absolute/path/to/docmost-mcp-server/helper/.venv/bin/python",
      "args": ["/absolute/path/to/docmost-mcp-server/helper/server.py"]
    }
  }
}
```

Keep the scopes disjoint (do not register the same MCP in both home and project). **Do not
register the operator `/mcp` HTTP MCP for the model** - the model uses `docmost-helper` only. The
included `claude.json.example` shows the correct helper-stdio registration. See `helper/README.md`
for the full helper reference.

## Data model

### Docmost (read directly; never altered by the bridge)

- `spaces`: `id, name, description, slug, visibility, default_role, creator_id, workspace_id, created_at, updated_at`
- `pages`: `id, slug_id, title, icon, position, parent_page_id, creator_id, last_updated_by_id, space_id, workspace_id, is_locked, content, created_at, updated_at` (rows with `deleted_at IS NULL`)

### Bridge (owned by this service; `migrations/bridge/*.sql`)

| Table | Purpose |
|---|---|
| `page_versions` | append-only version history (`revision_hash`, title, content, structural fields, `source`) |
| `page_heads` | current head per page (`current_revision_hash`, content, parent, position, icon, `is_deleted`) |
| `write_intents` | every attempted bridge write (action, caller_mode, status, target hash) |
| `write_receipts` | pending write confirmations matched by the observer |
| `observer_checkpoints` | last seen Docmost `updated_at` + observed hash per page |
| `local_page_snapshots` | helper stash snapshots for conflict resolution |

## Updating the running service

```bash
docker compose up -d --build     # rebuild after code/dependency changes
docker compose restart           # restart without rebuilding
docker compose logs -f docmost-mcp docmost-mcp-worker
```

## Troubleshooting

- **Health OK but reads fail** - `/health` is process-only. Check `.env` DB credentials, the
  Docmost DB hostname on the shared network, and `DOCMOST_NETWORK_NAME`.
- **`/mcp` "Session not found" after a restart** - streamable-HTTP sessions reset on restart;
  open a fresh session.
- **Page lookups fail** - resolve `space_id` first; page lookup is always space-scoped.
- **Helper can't find a replica** - it scans `DOCMOST_REPLICA_BASE` (default: the helper's cwd)
  for a `_replica.json` whose `space_id` matches. Pass an explicit `local_root` to override.
- **Worker not recording manual edits** - check `docmost-mcp-worker` logs; it observes every
  space on `WORKER_INTERVAL_SECONDS`.

## Local non-Docker run

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8099
# worker, separately:
python -m app.observer.worker --loop
```

You still need valid Docmost and bridge database connectivity through the env vars; a
Docker-only hostname such as `db` will not resolve from a bare host run.

## License

See `LICENSE`.
