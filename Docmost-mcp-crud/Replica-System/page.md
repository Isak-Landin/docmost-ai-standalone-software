The replica is a local directory tree the helper maintains as the working copy of a Docmost
space. Docmost remains the long-term source of truth; the replica is how the model edits and
syncs. The helper tools that operate on it are described on the Helper page.

## Ownership

- The helper owns local replica file IO (`helper/helper/replica.py`).
- The model owns `page.md` content and the directory layout (move a page directory to re-parent).
- The server owns canonical path planning, comparison normalization, diffing, and safe Docmost
  writes.

The model never edits `_meta.json`; the helper writes it after every successful sync.

## Per-page layout

Every page is a directory containing:

| File | Owner | Holds |
| --- | --- | --- |
| `page.md` | helper + model | markdown content (no H1 title in the body - see "Titles" below) |
| `_meta.json` | helper | `id`, `title`, `slug_id`, `space_id`, `parent_page_id`, `position`, `icon` (only when set), `base_revision_hash`, `content_file_path`, `meta_file_path` |

Child pages are nested subdirectories under the parent page's directory. The helper derives a
page's parent from this directory nesting, so moving a directory re-parents the page on the next
sync. The canonical `_meta.json` is exactly the field set above - nothing else (for example there
is no `parent_local_dir_path`; parent is always derived from nesting).

## Replica root files

| File | Holds |
| --- | --- |
| `_replica.json` | space header: `space_id`, `slug`, `name` |
| `_tree.json` | the last-synced tree snapshot: per page `page_id`, `parent_page_id`, `position`, `icon`, `local_path`. Used as the reconcile baseline so a moved/edited page is detected on the next sync. |

## Working-copy discovery

When a sync tool is called with only an id, the helper resolves the replica root by scanning
`DOCMOST_REPLICA_BASE` (default: the helper's current working directory) for a `_replica.json`
whose `space_id` matches. Pass an explicit `local_root` to override. Because the default is the
working directory, the replica normally lives inside the project the model is working in. In this
repository the tracked replica of the service's own documentation space is `Docmost-mcp-crud/`.

## Titles (H1 handling)

The page title is a separate field, never an H1 in the stored body. For a NEW local-only page,
the helper lifts a leading `# H1` from `page.md` into the page title and strips it from the body,
so Docmost renders the title once (not a title plus a duplicate H1). Only a level-1 `#` heading is
lifted (not `##`), and only when the page has no recorded title yet; a tracked page keeps its recorded
title and its full body. After the sync, the local `page.md` is rewritten without the lifted H1.

## Sync (reconcile)

1. Edit `page.md` and/or move page directories.
2. Call `sync_space(space_id)` (or `sync_page` / `sync_page_tree`) with only the id.
3. The helper builds the local page set plus the last-synced `_tree.json`, calls the server's
  reconcile brain, and applies the result (push / create / pull / materialize / move). It writes
  canonical content into the local files and realigns each `_meta.json` `base_revision_hash` and
  the `_tree.json` snapshot.
4. Only `conflicts` and `deletion_confirmations` need a model decision (`resolve_conflict` /
  `confirm_deletion`).

The summary a sync returns is metadata-only for cleanly applied pages: page content is written to
the local files, not returned, so a clean sync does not flood the model's context. Only conflicts
(with `remote_content` / `local_content` / diff) and errors carry content. See the Helper page for
the full response shape.

`base_revision_hash` matters: when local and remote both differ and the recorded base is missing,
the engine classifies the page as conflicted rather than allowing a clean push. The helper keeps
the base aligned after every successful sync.

`resync_space(space_id)` is an occasional whole-space variant: it asks the server to re-render
every page from Docmost first (even pages whose content did not change), then runs the same
reconcile. Use it to bring every page into sync regardless of change - for example after a
server-side rendering change, which a plain `sync_space` would otherwise treat as already synced.
See the Helper page for details.

## Post-sync canonical form

After a sync, a page's local `page.md` settles to Docmost's canonical rendering of the content
(the same rendering the version hash is taken from). This rendering is structure-preserving: nested
lists, ordered lists, task lists, tables, callouts, code blocks, and inline marks round-trip
faithfully through Docmost's markdown parser. What can differ from exactly what was typed are
canonical-form choices that match Docmost's own serializer - `-` bullets, ATX `#` headings, fenced
code, two spaces of indent per nested-list level, and `:::type` callouts - plus position-aware
escaping of characters that would otherwise be re-read as structure. It is canonicalization, not
data loss. See the Data Models page (revision hash) for how it is produced.

## Low-level escape hatches

`push_pages`, `pull_pages`, `accept_remote`, and the stash tools (`stash_page` / `get_stash` /
`clear_stash`) remain for manual override. Normal work goes through the three sync tools.

## Server-side replica planners

The server also exposes replica structure / standards planners (`get_replica_structure`,
`get_replica_standards`, `resolve_replica_directory_name`) used by the operator `/mcp` surface and
the `/sync` routes. These plan canonical paths but perform no client file IO.