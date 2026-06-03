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

## Normal sync workflow (reconcile)

The model only initiates a sync; the helper does all versioning, diffing, and file IO.

1. Edit `page.md` locally and/or restructure the replica (move a page directory to re-parent).
2. Call `sync_space(space_id)` (or `sync_page(space_id, page_id)` /
   `sync_page_tree(space_id, parent_page_id)`) on `docmost-helper`. Pass only the id(s).
3. The helper builds the local page set + last-synced `_tree.json`, calls the server
   `POST /v1/spaces/{id}/reconcile`, and applies the result locally: it pushes local edits,
   creates local-only pages, pulls remote changes, materializes new remote pages, applies
   moves/re-parents, and aligns both the bridge version and the local `_meta.json`
   `base_revision_hash`. One pass, full fidelity (content, title, parent, position, icon).
4. The result returns `synced_count` + `applied`, plus only the items needing a decision:
   `conflicts` (each with `remote_content`, `local_content`, diff) and
   `deletion_confirmations`. A clean sync needs no force and surfaces no conflicts.

## Conflict + deletion resolution

When a sync returns `conflicts[]` or `deletion_confirmations[]`:

- Conflict (both sides changed since the recorded base): inspect `remote_content` /
  `local_content` / diff, then call
  `resolve_conflict(space_id, page_id, merged_content)`. The server pushes the merged
  content aligned to the current remote head (no force); the helper writes it locally and
  re-aligns the base. Ask the user if the right merge is unclear.
- Deletion: call `confirm_deletion(space_id, page_id, direction)` — `remote` soft-deletes the
  remote page and drops the local copy; `local` accepts a remote deletion by dropping the
  local copy. Sync never deletes on its own.

`stash_page` / `accept_remote` / `push_pages` / `pull_pages` remain as low-level escape
hatches for manual override; normal work goes through the three sync tools.

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
