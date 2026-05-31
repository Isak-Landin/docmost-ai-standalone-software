# Docmost MCP Server — Claude Code instructions

## Helper-first for all Docmost operations

Use **docmost-helper** (stdio MCP) for all Docmost reads, writes, and sync operations.
Do not call the server-side `docmost-mcp` HTTP MCP directly during normal workflows.
The server MCP is available for manual inspection and bridge state queries only.

The helper calls the server via REST (`/helper/v1/` and `/auto-mcp/`). Never instruct
the helper to call `/mcp`.

## Setup requirement

`DOCMOST_MCP_SERVER_URL` must be set in `helper/.env` before starting the helper.
Copy `helper/.env.example` to `helper/.env` if the file does not exist.

## Local replica ownership

- `page.md` — owned by the helper and the model. Edit locally, push via helper.
- `_meta.json` — owned by the helper. Do not edit manually.

Full `_meta.json` schema (written by helper after each push/pull):

```json
{
  "id": "<page UUID or null for local-only pages>",
  "title": "<page title>",
  "slug_id": "<remote slug or null>",
  "parent_page_id": "<UUID or null>",
  "parent_local_dir_path": "<relative path to parent dir or null>",
  "space_id": "<space UUID>",
  "content_file_path": "<absolute path to page.md>",
  "meta_file_path": "<absolute path to _meta.json>",
  "base_revision_hash": "<last successful sync hash or null>",
  "active_snapshot": {
    "snapshot_id": "<UUID>",
    "base_revision_hash": "<hash at snapshot time>"
  }
}
```

`base_revision_hash` is updated by the helper after every successful push or pull.
`active_snapshot` is written by `stash_page` and cleared by `clear_stash` or auto-expiry.

## Normal push workflow

1. Edit `page.md` locally.
2. Call `push_pages(space_id, local_paths=[...])` on `docmost-helper`.
3. Helper reads local files, calls server bridge pipeline, updates `_meta.json`.
4. If any pages drift: proceed to conflict resolution.

## Conflict resolution workflow

When `push_pages` returns pages with `action="drifted"`:

1. `stash_page(space_id, page_id, local_path)` — saves local content server-side, returns `snapshot_id`.
2. `accept_remote(space_id, page_id, local_path)` — overwrites local with remote, updates `_meta.json`.
3. `get_stash(space_id, page_id, snapshot_id)` — retrieves pre-overwrite content for comparison.
4. Read new local `page.md` (now the remote version).
5. Write merged content to `page.md`.
6. `push_pages` for the resolved page.
7. `clear_stash(space_id, page_id, snapshot_id)` — mark snapshot consumed.

## IDs

All `space_id`, `page_id`, and `parent_page_id` values must come from live MCP tool
responses in the current session. Never use IDs from memory, `_meta.json`, or inference
when calling MCP write tools — always resolve from `list_spaces` or `list_pages` first.

Exception: `_meta.json` `id` field is valid for push operations (it was written by the
helper from a prior live response).

## Content rules

- All content is markdown. Never pass ProseMirror JSON.
- Page title is a separate parameter — do not include as `# Heading` in content body.
- Use plain ASCII punctuation — no Unicode em-dashes, curly quotes, or ellipsis characters.
