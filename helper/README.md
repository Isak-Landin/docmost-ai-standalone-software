# Docmost Helper

Client-side stdio MCP server and the consuming model's ONLY Docmost surface (never the server-side `/mcp`). It owns all local replica file IO and runs the automated reconcile: the model passes one id to `sync_space` / `sync_page` / `sync_page_tree` and the helper does everything — diffing, version alignment, push/pull/create/move — surfacing only conflicts and deletions for a decision.

## Setup

```bash
cd helper
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env
# Edit .env — set DOCMOST_MCP_SERVER_URL to the running server base URL
```

## Registration with Claude Code

The helper is a **stdio** MCP. Register it in either of Claude Code's two MCP scopes — the
entry is identical, only the location differs:

- **User / home scope** (`$CLAUDE_CONFIG_DIR/.claude.json` → `mcpServers`, falling back to
  `~/.claude.json`). A home-scoped entry loads in **every** session regardless of directory, so
  the model always has the Docmost surface. *This is how the live environment is set up* (see the
  "MCP & skills setup" page in the `Docmost-MCP-Service` space for the exact files).
- **Project scope** (`.mcp.json` at the repo root). A project-scoped entry loads **only** when
  Claude Code runs in that directory.

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

Use **absolute** paths to this repo's helper venv and `server.py` — then a home-scoped entry
works from any directory. After (re)starting Claude Code (or reconnecting via `/mcp`), the model
sees the tools as `mcp__docmost-helper__*`. On startup the helper performs a best-effort
`/v1/contract` handshake and warns on stderr if the server's contract version differs.

The helper is additive — it loads alongside any other MCPs in either scope. Keep the scopes
**disjoint** (do not register the same MCP in both repo and home) to avoid duplicate tool listings.

## Using it from Claude

The model uses the helper for **all** Docmost reads, writes, and sync — never the server-side
`/mcp` HTTP surface (that is a quiet operator/inspection fallback). Normal flow: edit `page.md`
locally (and/or move page directories to restructure), then call `sync_space(space_id)` (or
`sync_page` / `sync_page_tree`) with only the id. The helper reconciles everything; the model
only acts on the `conflicts` / `deletion_confirmations` a sync returns (via `resolve_conflict` /
`confirm_deletion`), and asks the user if a resolution is unclear. See "Sync model" below.

## Environment

| Variable | Required | Description |
|---|---|---|
| `DOCMOST_MCP_SERVER_URL` | Yes | Base URL of the running docmost-mcp server |

The helper reads `.env` from the `helper/` directory at startup via `python-dotenv`.

## Sync model (reconcile)

The model only initiates a sync; the helper + server do all versioning, diffing, and file IO.

- `sync_space(space_id)` / `sync_page(space_id, page_id)` / `sync_page_tree(space_id, parent_page_id)`
  build the local page set + last-synced `_tree.json`, call `POST /v1/spaces/{id}/reconcile`, apply the
  result to local files, and return `synced_count` + `applied` plus only the items needing a decision:
  `conflicts` (with remote/local content + diff) and `deletion_confirmations`. A clean sync needs no force.
- `resolve_conflict(space_id, page_id, merged_content)` pushes the merge aligned to the current remote
  head (no force) and re-aligns the local base.
- `confirm_deletion(space_id, page_id, direction)` applies a confirmed deletion (`remote` | `local`).
- The model expresses structure by editing `page.md` and moving page directories; it never edits
  `_meta.json` (helper-owned) and never forces. `create/update/delete/move_page`, `push_pages`,
  `pull_pages`, and the stash tools remain as low-level escape hatches.

Working-copy discovery: pass only an id; the helper resolves the local replica via `_replica.json`
(`space_id` match) under `DOCMOST_REPLICA_BASE`, or use an explicit `local_root`.

## Contracts

- Reconcile + resolution: `POST /v1/spaces/{id}/reconcile`, `POST /v1/spaces/{id}/pages/{pid}/resolve`,
  `POST /v1/spaces/{id}/pages/{pid}/confirm-deletion` — the helper's primary sync path
- Route prefixes on server: `/v1/` (canonical) and `/helper/v1/` (back-compat) — do not change without updating `client.py`
- Batch sync escape hatch: `/auto-mcp/spaces/{space_id}/pages/apply` — existing server surface, do not retire
- `DOCMOST_MCP_SERVER_URL` env var name is locked — matches this README and `.env.example`
