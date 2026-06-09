Docmost MCP is a bridge between a live Docmost deployment and an MCP-consuming model (Claude Code). It reads Docmost content directly from Docmost's PostgreSQL database, writes through Docmost's REST API, and keeps its own separate "bridge" PostgreSQL database for version and sync state.

## Two halves

- Server (this repository) - runs as containers next to a live Docmost stack. It owns Docmost connectivity, bridge version truth, content normalization, the reconcile brain, the REST and helper-facing routes, and a background observer worker.
- Helper (`helper/`) - a small client-side stdio MCP. It is the consuming model's only Docmost surface. It owns all local replica file IO and runs the automated reconcile by calling the server over REST.

## Two consumer surfaces

- docmost-helper (stdio) - the model surface. Reconcile-first reads, writes, and sync.
- `/mcp` (HTTP) - a quiet operator / inspection fallback only. It is NOT the model's workflow surface.

The helper reaches the server over REST (`/v1`, `/helper/v1`, `/auto-mcp`), never over `/mcp`.

## Key characteristics

- Bridge-owned versioning - a separate PostgreSQL database tracks a head plus version history per page, independent of Docmost.
- Single hash derivation - the revision hash is computed at exactly one place from Docmost's read-back content, so every surface agrees on it.
- Faithful markdown round-trip - the ProseMirror-to-markdown renderer is the inverse of Docmost's `marked` ingest, so nested lists, tables, task lists, callouts, and code round-trip structurally; escaping is position-aware so ordinary prose is not over-escaped.
- Space-scoped - pages are always queried within a space; there is no global page lookup.
- Markdown in and out - the page title is a separate field, never an H1 in the body.
- Worker observer - a background loop folds direct-Docmost-UI edits into bridge state for every space, whether or not a model has ever touched them.

## Tech stack

| Component | Technology |
| --- | --- |
| Web framework | FastAPI |
| Operator MCP layer | `mcp` library (`FastMCP`) at `/mcp` |
| Databases | Docmost PostgreSQL (read) + bridge PostgreSQL (version state), via `psycopg2` |
| Writes to Docmost | Docmost REST API via `httpx` |
| Models | Pydantic v2 |
| Runtime | Python 3.12 |
| Deployment | Docker / Docker Compose (three services) |

## Entry point

`app/main.py` creates the FastAPI app, registers the read / write / helper / reconcile / auto-mcp / sync routers, and mounts the operator `/mcp` sub-app.