The `docmost-helper` stdio MCP is the consuming model's only Docmost surface. It owns all local
replica file IO and runs the sync against the server. The model never calls the server directly
and never uses the operator `/mcp` surface (see the MCP Server page). This page is the full tool
and workflow reference; the on-disk files it manages are described on the Replica System page.

## Tools

### Reads

| Tool | Purpose |
| --- | --- |
| `list_spaces()` | List all Docmost spaces. |
| `get_space(space_id)` | Get one space. |
| `get_space_tree(space_id)` | Get the nested page hierarchy. |
| `list_pages(space_id)` | Flat list of pages in a space. |
| `get_page(space_id, page_id)` | One page with its markdown content. |

### Sync (the primary path)

| Tool | Purpose |
| --- | --- |
| `sync_space(space_id)` | Reconcile a whole space in one pass. |
| `sync_page(space_id, page_id)` | Reconcile a single page. |
| `sync_page_tree(space_id, parent_page_id)` | Reconcile a parent page and all its descendants. |
| `resync_space(space_id)` | Occasional whole-space variant: re-render every page on the server, then reconcile (see "Whole-space resync" below). |

### Resolution (only when a sync asks for it)

| Tool | Purpose |
| --- | --- |
| `resolve_conflict(space_id, page_id, merged_content)` | Apply the final merged markdown for a conflicted page. |
| `confirm_deletion(space_id, page_id, direction)` | Apply a deletion: `remote` deletes the remote page and drops the local copy; `local` accepts a remote deletion by dropping the local copy. |

### Low-level escape hatches (not the normal path)

| Tool | Purpose |
| --- | --- |
| `create_page` / `update_page` / `delete_page` / `move_page` | Direct single-page operations. |
| `create_space` / `delete_space` | Direct space operations (`delete_space` is irreversible). |
| `push_pages(space_id, local_paths)` | Push specific local pages; check `applied=False` / `action='drifted'` for clashes. |
| `pull_pages(space_id, page_ids?, local_paths?)` | Pull remote pages into the local replica. |
| `accept_remote(space_id, page_id, local_path)` | Overwrite a local page with the current remote version. |
| `stash_page` / `get_stash` / `clear_stash` | Snapshot local content during manual conflict handling. |

Normal work uses only the read tools and the three sync tools (plus resolution when prompted).
The rest exist for manual override.

## The reconcile workflow

1. Edit `page.md` locally, and/or move page directories to restructure the hierarchy (the helper
   derives a page's parent from its directory nesting, so moving a directory re-parents the page).
2. Call `sync_space(space_id)` (or `sync_page` / `sync_page_tree`) with only the id.
3. The helper builds the current local page set and the last-synced tree, sends them to the
   server's reconcile brain, and applies the result locally in one pass: it pushes your edits,
   creates local-only pages, pulls remote changes, materializes new remote pages, applies
   moves/re-parents, and realigns each page's sync base.
4. Act only on what the result flags for a decision (conflicts, deletions).

A clean sync needs no force and surfaces no conflicts.

## Whole-space resync

`resync_space(space_id)` is an occasional variant of `sync_space` for when every page must be
brought into sync regardless of whether its content changed. It first asks the server to re-render
EVERY page in the space from Docmost's current stored content (bypassing the observer's
"updated-at" gate that normally skips unchanged pages), which re-anchors each page's head to the
current rendering. It then runs the SAME two-way reconcile as `sync_space`.

Use it after the server's markdown rendering was changed - so pages that were never re-edited still
pick up the corrected rendering - or to recover from suspected drift. Because the renderer change
does not touch Docmost's stored content, a plain `sync_space` would classify those pages as already
synced and never re-render them; `resync_space` is what propagates a rendering change.

It is two-way safe: a page whose only difference is the re-render heals as a pull (its local
`page.md` is rewritten to the corrected rendering, no content surfaced); a page that also has
un-pushed local edits surfaces as a `conflicts[]` entry for a decision. It never force-pushes, so
it cannot send stale local content over a newer remote. The result is the normal sync summary plus
`reanchored_count` (pages whose server-side render changed this run). Prefer plain `sync_space` for
everyday work.

## Response shape

A sync returns a compact summary, not page bodies:

| Field | Meaning |
| --- | --- |
| `synced_count` | Pages that were ALREADY in sync this run (unchanged). |
| `applied_count` / `applied[]` | Pages changed this run - metadata only. The page content is written straight to the local replica files, NOT returned, so a clean sync never floods the model's context. |
| `conflicts[]` | Pages where both sides changed since the recorded base. Each carries `remote_content`, `local_content`, and a line diff for a decision. |
| `deletion_confirmations[]` | Deletions awaiting confirmation, each with a `direction`. |
| `errors[]` | Per-page failures. |
| `reanchored_count` | `resync_space` only: how many pages the server re-rendered to a changed result this run. |

To confirm a change happened, check `applied_count` / `errors[]` - NOT `synced_count`. Only
failures and decisions (`conflicts`, `errors`) carry page content; cleanly applied pages do not.

## Conflict and deletion handling

- Conflict: inspect the `remote_content` / `local_content` / diff, then call
  `resolve_conflict(space_id, page_id, merged_content)` with the final merged markdown. Ask the
  user when the right merge is unclear. Never force.
- Deletion: the helper never deletes on its own. Call
  `confirm_deletion(space_id, page_id, direction)` only after the deletion is understood; ask the
  user if it is unexpected.

## Content conventions

- All content is markdown. The page title is a separate field, not part of the body.
- On a NEW local-only page, a leading `# H1` is lifted into the page title and stripped from the
  body, so Docmost never renders the title plus a duplicate heading. A tracked page keeps its
  recorded title and full body.
- Use plain ASCII punctuation (no Unicode em-dashes, curly quotes, or ellipsis characters).
- After a sync, a page's local `page.md` settles to Docmost's canonical rendering of the content.
  The rendering is structure-preserving (nested lists, tables, task lists, callouts, code, and the
  like round-trip faithfully); what can differ from exactly what was typed are canonical-form
  choices that match Docmost's own serializer - `-` bullets, ATX `#` headings, fenced code,
  marker-width indent per nested-list level (two spaces under a bullet, three under an ordered item),
  `:::type` callouts. See the Data Models page (revision hash) for how this rendering is produced.

## IDs

All `space_id`, `page_id`, and `parent_page_id` values passed to tools must come from live tool
responses in the current session (`list_spaces`, `list_pages`, `get_space_tree`), never from
memory or inference.

## Restarting the helper

The helper is a long-lived stdio subprocess of Claude Code; it does NOT pick up helper code changes
(anything under `helper/`) or MCP `env` changes (for example `DOCMOST_REPLICA_AUTOSYNC_ROOTS`) until
it is restarted. Claude cannot restart it from inside a session - you restart it: relaunch the
Claude Code CLI from the repo (with direnv active so `.envrc` and the MCP config load), or reconnect
MCP in a running session with `/mcp`. After a server rebuild, a `Session not found` message is stale
transport, not missing content - reconnect. The Developer Handbook has the full restart procedure,
the verification steps, and when a bridge rebuild is also needed.

## Relationship to the server

The helper reaches the server over its REST contract (reads and writes under `/v1` and
`/helper/v1`, reconcile/resolve/confirm-deletion under `/v1/spaces/{id}/...`, and batch/observe
under `/auto-mcp`); it never uses the operator `/mcp` surface. Working-copy discovery, the local
file layout, and ownership are on the Replica System page; the endpoint contracts are on the REST
API page.