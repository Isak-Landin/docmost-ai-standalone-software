# Replica System

The replica system defines the deterministic local replica file layout for any Docmost space.
`app/query/replica.py` owns the naming and layout contract. `app/sync/service.py` compares
client-reported local page state against live Docmost pages, plans paths and diffs statelessly, and
applies remote writes through the bridge write pipeline.

## Purpose

The recommended usage pattern is local-first: maintain a replica in the working copy being edited.
The service can still use a default root at `./{space_name}-replica`, but callers may pass a
different `local_root` for a repo-local working copy. The replica system standardizes the tree
shape so all clients agree on paths, while the sync engine compares client-reported local page
state against live Docmost pages and performs safe remote writes through the Docmost write API.

## Replica root

```
./{space_name}-replica/
```

Example: space "tool-ai-gateway" → `./tool-ai-gateway-replica/`

The space name is sanitized before use:
- Invalid path characters (`< > : " / \ | ? * \x00-\x1f`) → replaced with `-`
- Whitespace runs → replaced with `-`
- Multi-dash runs → collapsed to single `-`
- Trailing dots or spaces → stripped
- Windows reserved names (`CON`, `NUL`, etc.) → prefixed with `_`

## Replica root files

| File | Description |
|---|---|
| `_replica.json` | Canonical replica-level metadata |
| `_tree.json` | Resolved tree snapshot used for the replica |

## Per-page layout

Every page maps to a **directory** inside the replica tree:

| File | Description |
|---|---|
| `page.md` | Normalized plain-text content of the page |
| `_meta.json` | Page metadata: id, title, slug_id, parent_page_id, local paths |

Child pages become nested subdirectories under the parent page's directory.

## Directory naming rules

Applied level-by-level, not globally:

1. **Base**: use the filesystem-safe page title as the directory name
2. **Sibling collision**: if two sibling pages resolve to the same base name, append `__{slug_id}` to every page in the collision set
3. **Fallback**: if `slug_id` is missing or still collides, append `__{short_page_id}` (first 8 characters of the page UUID)
4. **Numeric fallback**: if still colliding, append `__{short_page_id}-{n}` with incrementing `n`

## Source of truth rules

| Scenario | Source of truth |
|---|---|
| No local replica exists | Remote Docmost |
| Replica exists, no newer local edits | Remote Docmost (client materializes or refreshes via `pull_replica`) |
| Local replica has newer edits | Replica content is ahead until the sync workflow resolves the state |
| Local and remote both changed | Neither side wins automatically; inspect `get_sync_diff` first |

## Editing policy

- Apply documentation edits to the selected local working-copy replica, not directly to remote Docmost
- Use `create_local_replica_page(..., local_root?, existing_dir_names=...)` to get the canonical local-only scaffold plan, then write those files on the client
- When local files are edited, use `get_sync_status(..., pages=[...])` to report which replica files changed and which remote pages they correspond to
- Use `push_replica(..., pages=[...], local_root?)` and `pull_replica(..., pages=[...], local_root?)` as the primary sync workflow, and only use `force` after reviewing clashes
- If one working copy pushes before another, the stale working copy must pull or deliberately force after diff review

## Using the replica tools

| When | Use |
|---|---|
| Building or refreshing an existing remote space locally | `get_replica_structure(space_id, local_root?)` |
| Creating a new local-only page not yet on remote | `create_local_replica_page(space_id, ..., local_root?, existing_dir_names=...)` |
| Mapping a local file back to its remote page | Read `_meta.json` in the page directory |
| Discovering which pages are out of sync | `get_sync_status(space_id, SyncStatusIn(...))` |
| Inspecting exact line-based clashes | `get_sync_diff(space_id, SyncDiffIn(...))` |
| Refreshing local files from remote | `pull_replica(space_id, selection)` returns canonical remote snapshots for the client to write locally |
| Sending local changes to remote | `push_replica(space_id, selection)` writes the client-supplied page state to Docmost |

## Implementation notes

- `_resolve_level_directory_names()` in `app/query/replica.py` resolves names for a full sibling group before assigning any, so collision detection is consistent
- The recursive `_build_replica_level()` walks the `PageTreeNode` tree from `get_space_tree()` and builds `ReplicaTreeNode` objects
- `app/query/replica.py` performs no file I/O. The client writes local files; `app/sync/service.py` only plans paths, compares client-local page state to Docmost, and performs safe remote writes
