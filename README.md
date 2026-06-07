# Docmost MCP

Docmost MCP lets an AI model running in **Claude Code** read and maintain a project's
**Docmost** documentation through a single MCP tool surface. The model never touches Docmost
directly: it edits a local copy of the pages and a helper syncs that copy to Docmost with
versioning, hierarchy tracking, and conflict handling.

In short, it solves **MCP consumption of Docmost for Claude Code models** - turning a Docmost
space into something a model can safely read from and write to.

## When and why to use it

Use it on any Claude Code project whose long-term documentation lives (or should live) in
Docmost. It lets the model treat Docmost as the project's documentation source - reading
existing docs and writing new ones - safely and reproducibly:

- The model works on local markdown files and calls one sync tool; it never makes raw writes
  to Docmost.
- Every change is versioned and reconciled, so concurrent edits surface as conflicts instead
  of silently overwriting.
- One running server can back many projects; each project syncs its own space.

If a project keeps its documentation only in the repo or elsewhere, you do not need this.

## Server and helper

The system has two halves:

- **Server** - runs as containers next to a live Docmost stack. It owns Docmost access and the
  version state, and exposes the REST endpoints the helper calls. It also runs a background
  worker that keeps version state current even for edits made directly in the Docmost UI.
- **Helper** (`helper/`) - a small client-side stdio MCP. It is the model's only Docmost
  surface. It owns the local copy of the pages (the "replica") and runs the sync.

```
Claude Code (model)  --stdio-->  docmost-helper  --REST-->  server  -->  Docmost
```

The server keeps its own database for version/sync state, separate from Docmost's database; it
never alters Docmost's schema. Full architecture, data model, and component reference live in
the Docmost documentation space (see "Deep documentation" below).

## Endpoints

The helper talks to the server over REST; you do not call these yourself, but for reference:

- **Reads** - spaces, page tree, pages, and page content (`/v1`, `/helper/v1`, and `/spaces`).
- **Writes** - create / update / move / delete page, create / delete space (`/v1`, `/spaces`).
- **Sync** - reconcile a scope, resolve a conflict, confirm a deletion
  (`/v1/spaces/{id}/reconcile`, `/resolve`, `/confirm-deletion`).
- **Automation** - batch apply and a one-shot observer pass (`/auto-mcp`).
- **Health / version** - liveness and the helper/server version handshake (`/health`,
  `/v1/contract`).
- **Operator MCP** - `/mcp` (streamable HTTP) for manual inspection only; it is not the model's
  surface and must not be registered for the model.

Interactive API docs are served at `/docs`. The full request/response contracts are in the
Docmost documentation, not here.

## Prerequisites

- A running Docmost with PostgreSQL. **Docmost v0.71.1 or later is required** for content writes
  (earlier versions silently discard page content).
- Docker and Docker Compose on the Docmost host.
- Network reach from this service to the Docmost database, and a separate PostgreSQL database
  for the server's own version state (provided by the bundled `bridge-db` service).

## Server setup

The server runs as three containers (`bridge-db`, `docmost-mcp`, `docmost-mcp-worker`) on the
same Docker network as Docmost.

1. Put the project on the Docmost host and copy the env file:

   ```bash
   git clone <repo-url> /opt/docmost-mcp && cd /opt/docmost-mcp
   cp env.example .env
   ```

2. Fill in `.env`:

   ```env
   # Docmost database (read path) - DOCMOST_DB_URL or the individual values
   DOCMOST_DB_URL=postgresql://docmost:STRONG_DB_PASSWORD@db:5432/docmost
   DOCMOST_DB_HOST=db
   DOCMOST_DB_PORT=5432
   DOCMOST_DB_NAME=docmost
   DOCMOST_DB_USER=docmost
   DOCMOST_DB_PASSWORD=STRONG_DB_PASSWORD

   # Server version-state database (the bridge-db service)
   BRIDGE_DB_URL=postgresql://docmost_bridge:STRONG_BRIDGE_DB_PASSWORD@bridge-db:5432/docmost_bridge
   BRIDGE_DB_HOST=bridge-db
   BRIDGE_DB_PORT=5432
   BRIDGE_DB_NAME=docmost_bridge
   BRIDGE_DB_USER=docmost_bridge
   BRIDGE_DB_PASSWORD=STRONG_BRIDGE_DB_PASSWORD

   # Docmost app (write path) - token kept in memory only
   DOCMOST_APP_URL=http://docmost:3000
   DOCMOST_USER_EMAIL=<docmost-user-email>
   DOCMOST_USER_PASSWORD=<docmost-user-password>

   # Shared Docker network with the Docmost stack
   DOCMOST_NETWORK_NAME=docmost_default

   # Bind + exposure
   LISTEN_HOST=0.0.0.0
   LISTEN_PORT=8099
   EXTERNAL_PORT=8099

   # Host headers the /mcp transport accepts (your reverse-proxy domain);
   # leave empty to disable DNS-rebinding protection (not for production)
   MCP_ALLOWED_HOSTS=mcp.yourdomain.com

   # Observer interval, logging
   WORKER_INTERVAL_SECONDS=15
   MODE=prod
   LOG_LEVEL=INFO
   ```

3. Start and verify:

   ```bash
   docker compose up -d --build
   docker compose ps
   curl http://<host>:8099/health      # {"ok": true} (process only)
   curl http://<host>:8099/spaces      # 200 with spaces, or 503 if the DB is unreachable
   ```

Behind a reverse proxy, terminate TLS, forward `/mcp` and the REST routes to the container, and
set `MCP_ALLOWED_HOSTS` to the proxied domain.

## Helper setup (Claude Code)

The helper is **not plug-and-play**: it runs from source in its own virtualenv and is wired into
Claude Code by absolute path. Do all of the following on the machine where Claude Code runs.

### 1. Create the helper virtualenv and configure it

```bash
cd helper
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
```

Edit `helper/.env`:

```env
# Required: base URL of the running server. The helper does a version handshake on start,
# so this must be set before the helper launches.
DOCMOST_MCP_SERVER_URL=https://your-server-host        # or http://host:8099

# Optional: directory under which the helper finds replicas by space id. If unset, the helper
# looks under its current working directory (normally the project root Claude Code launched it in).
DOCMOST_REPLICA_BASE=
```

### 2. Register the helper as a stdio MCP (absolute paths to THIS venv)

Claude Code launches the helper as a subprocess, so the entry must point at the venv's python and
`server.py` by **absolute path** - not `python` on PATH, not a relative path:

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

Put it in exactly **one** scope:

- **User / home scope** - `$CLAUDE_CONFIG_DIR/.claude.json` (falls back to `~/.claude.json`).
  Loads in every Claude Code session regardless of directory. Recommended when one helper serves
  many projects.
- **Project scope** - `.mcp.json` at a repo root. Loads only when Claude Code runs in that repo.

Register in one scope only - the same server in both scopes double-lists its tools. Do **not**
register the operator `/mcp` HTTP MCP for the model; the model uses `docmost-helper` only.
`claude.json.example` in this repo is a ready-to-copy entry.

### 3. Give the model instructions (`CLAUDE.md`)

Registering the helper exposes the tools; the model still needs short instructions telling it how
and when to use them. Put these in the consuming project's `CLAUDE.md` (this repo's `CLAUDE.md` is
a ready-to-copy template). Nothing is forced - include what fits the project - but a complete set
covers:

- **Surface:** the helper is the only Docmost surface; use it for all Docmost reads, writes, and
  sync (never the operator `/mcp`).
- **Local replica:** edit `page.md` files; move page directories to restructure; never edit
  `_meta.json` (helper-managed).
- **Workflow:** call `sync_space` / `sync_page` / `sync_page_tree` with an id; act on the
  `conflicts` / `deletion_confirmations` the result returns (`resolve_conflict` /
  `confirm_deletion`); ask the user when unclear.
- **Content rules:** markdown only; the page title is a separate field (a leading `# H1` on a new
  page is lifted into the title); plain ASCII punctuation.
- **IDs:** always from live tool responses, never from memory.
- **When to use Docmost:** treat it as the project's long-term documentation source and route
  documentation reads/writes through the helper. This "when to use Docmost" decision is
  project-specific and is deliberately different from how a generic, always-on tool is described -
  decide per project whether documentation belongs in Docmost.

### Local-environment checklist (none of this is plug-and-play)

- [ ] `helper/.venv` created and `requirements.txt` installed into it
- [ ] `helper/.env` filled, with `DOCMOST_MCP_SERVER_URL` set before first launch
- [ ] the MCP entry uses **absolute** paths to `helper/.venv/bin/python` and `helper/server.py`
- [ ] registered in exactly one Claude Code scope; the operator `/mcp` is not registered for the model
- [ ] `CLAUDE.md` instructions present in the consuming project
- [ ] `DOCMOST_REPLICA_BASE` set only if replicas live outside the project root

## Using it

1. Edit `page.md` locally and/or move page directories to restructure the hierarchy.
2. Call `sync_space(space_id)` (or `sync_page` / `sync_page_tree`) with only the id.
3. The helper syncs both ways and returns a short summary plus any conflicts or deletions that
   need a decision; resolve those with `resolve_conflict` / `confirm_deletion`.

## Updating and troubleshooting

```bash
docker compose up -d --build     # after code/dependency changes
docker compose restart           # restart without rebuilding
docker compose logs -f docmost-mcp docmost-mcp-worker
```

- **Health OK but reads fail** - `/health` is process-only; check the `.env` database settings
  and `DOCMOST_NETWORK_NAME`.
- **Page lookups fail** - always resolve a `space_id` first; lookups are space-scoped.
- **Helper can't find a replica** - it scans `DOCMOST_REPLICA_BASE` (default: its cwd) for a
  matching replica; pass an explicit `local_root` to override.

## Local non-Docker run

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8099
python -m app.observer.worker --loop   # worker, separately
```

Valid Docmost and version-state database connectivity is still required; a Docker-only hostname
like `db` will not resolve from a bare host run.

## Deep documentation

Full architecture, the version/reconcile model, the data model, per-endpoint contracts, the
helper tool reference, and deployment detail live in the **Docmost-MCP-Service** documentation
space in Docmost. This README is intentionally limited to setup, configuration, and usage.

## License

See `LICENSE`.
