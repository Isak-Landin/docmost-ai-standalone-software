The replica is a local directory tree the helper maintains as the working copy of a Docmost space. Docmost remains the long-term source of truth; the replica is how the model edits and syncs.

## Ownership

- The helper owns local replica file IO (`helper/helper/replica.py`).
- The model owns `page.md` content and the directory layout (move a page directory to re-parent).
- The server owns canonical path planning, comparison normalization, diffing, and safe Docmost writes.

The model never edits `_meta.json`; the helper writes it after every successful sync.

## Per-page layout

Every page is a directory containing:

| File | Owner | Holds |
| --- | --- | --- |
| `page.md` | helper + model | markdown content (no H1 title in the body) |
| `_meta.json` | helper | `id`, `title`, `slug_id`, `space_id`, `parent_page_id`, `position`, `icon`, `base_revision_hash`, file paths |

Child pages are nested subdirectories under the parent page's directory. The helper derives a page's parent from this directory nesting, so moving a directory re-parents the page on the next sync.

## Replica root files

| File | Holds |
| --- | --- |
| `_replica.json` | space header: `space_id`, `slug`, `name` |
| `_tree.json` | the last-synced tree snapshot (per-page id, parent, position, icon) used as the reconcile baseline |

## Working-copy discovery

When a sync tool is called with only an id, the helper resolves the replica root by scanning `DOCMOST_REPLICA_BASE` (default: the helper's current working directory) for a `_replica.json` whose `space_id` matches. Pass an explicit `local_root` to override. In this repository the replica of the service's own documentation space is tracked at `Docmost-mcp-crud/`.

## Sync (reconcile)

1. Edit `page.md` and/or move page directories.
2. Call `sync_space(space_id)` (or `sync_page` / `sync_page_tree`) with only the id.
3. The helper builds the local page set plus `_tree.json`, calls the server reconcile brain, applies the result (push / create / pull / move / materialize), and realigns each `_meta.json` `base_revision_hash` and the `_tree.json` snapshot.
4. Only `conflicts` and `deletion_confirmations` need a model decision (`resolve_conflict` / `confirm_deletion`).

`base_revision_hash` matters: when local and remote differ and the base is missing, the engine classifies the page as conflicted rather than allowing a clean push. The helper keeps it aligned after every successful sync.

## Low-level escape hatches

`push_pages`, `pull_pages`, `accept_remote`, and the stash tools (`stash_page` / `get_stash` / `clear_stash`) remain for manual override. Normal work goes through the three sync tools.

## Server-side replica planners

The server also exposes replica structure / standards planners (`get_replica_structure`, `get_replica_standards`, `resolve_replica_directory_name`) used by the operator `/mcp` surface and the `/sync` routes. These plan canonical paths but perform no client IO.