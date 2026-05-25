# Replica System

The replica system defines the deterministic **server-side** file layout for any Docmost space.
`app/query/replica.py` owns the naming and layout contract, while `app/sync/` owns replica
materialization, sync metadata, diffing, and pull/push orchestration.

## Purpose

The recommended usage pattern involves maintaining a **server-side replica** - a directory tree
that mirrors remote Docmost pages as local files. The replica system standardizes how this tree
is laid out so all clients agree on paths, while the sync engine reports drift and performs
pull/push operations against that same tree.

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
| `_sync.json` | Server-managed replica sync state |

## Per-page layout

Every page maps to a **directory** inside the replica tree:

| File | Description |
|---|---|
| `page.md` | Normalized plain-text content of the page |
| `_meta.json` | Page metadata: id, title, slug_id, parent_page_id, local paths |
| `_sync.json` | Server-managed page sync state, including last-known sync base |

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
| Replica exists, no newer local edits | Remote Docmost (materialize or refresh via `pull_replica`) |
| Local replica has newer edits | Replica content is ahead until the sync workflow resolves the state |
| Local and remote both changed | Neither side wins automatically; inspect `get_sync_diff` first |

## Editing policy

- Apply documentation edits to the **server-side replica**, not directly to remote Docmost
- Use `create_local_replica_page` to scaffold brand-new local-only pages so the server, not the client, owns `_meta.json` creation
- When local files are edited, use `get_sync_status` to report which replica files changed and which remote pages they correspond to
- Use `push_replica` and `pull_replica` as the primary sync workflow, and only use `force` after reviewing clashes

## Using the replica tools

| When | Use |
|---|---|
| Building or refreshing an existing remote space locally | `get_replica_structure(space_id)` |
| Creating a new local-only page not yet on remote | `create_local_replica_page(space_id, ...)` |
| Mapping a local file back to its remote page | Read `_meta.json` in the page directory |
| Discovering which pages are out of sync | `get_sync_status(space_id)` |
| Inspecting exact line-based clashes | `get_sync_diff(space_id, page_id?, local_path?)` |
| Refreshing local files from remote | `pull_replica(space_id, selection)` |
| Sending local changes to remote | `push_replica(space_id, selection)` |

## Implementation notes

- `_resolve_level_directory_names()` in `app/query/replica.py` resolves names for a full sibling group before assigning any, so collision detection is consistent
- The recursive `_build_replica_level()` walks the `PageTreeNode` tree from `get_space_tree()` and builds `ReplicaTreeNode` objects
- `app/query/replica.py` itself performs no I/O; `app/sync/storage.py` owns replica file writes, `_sync.json` bookkeeping, and canonical content materialization
