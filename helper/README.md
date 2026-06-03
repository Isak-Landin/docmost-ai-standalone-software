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

## Registration in `.mcp.json`

Add to the repo-root `.mcp.json`:

```json
{
  "mcpServers": {
    "docmost-helper": {
      "type": "stdio",
      "command": "/absolute/path/to/docmost-mcp-server/helper/.venv/bin/python3",
      "args": ["/absolute/path/to/docmost-mcp-server/helper/server.py"]
    }
  }
}
```

The helper stdio server is additive — it loads alongside any other MCPs registered in `.mcp.json` or the Claude home config.

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
