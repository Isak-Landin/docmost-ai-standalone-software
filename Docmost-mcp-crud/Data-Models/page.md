# Data Models

All output models are defined in `app/models.py` using Pydantic v2. All models use `model_config = {"from_attributes": True}` to support ORM-style construction from database row dicts.

## SpaceOut

Returned by `list_spaces`, `get_space`.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Space UUID |
| `name` | str? | Display name |
| `description` | str? | Optional description |
| `slug` | str | URL-friendly identifier |
| `visibility` | str | `public` or `private` |
| `default_role` | str | Default member role |
| `creator_id` | UUID? | UUID of creating user |
| `workspace_id` | UUID | Parent workspace UUID |
| `created_at` | datetime | |
| `updated_at` | datetime | |

## SpaceSummaryOut

Embedded in tree and replica responses where full space detail is not needed.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Space UUID |
| `name` | str? | Display name |
| `slug` | str | URL-friendly identifier |

## PageOut

Returned by `list_pages`, `get_page`.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Page UUID |
| `slug_id` | str | Short URL-friendly identifier |
| `title` | str? | Page title |
| `icon` | str? | Emoji or icon identifier |
| `position` | str? | Sort position within parent |
| `parent_page_id` | UUID? | Parent page UUID, or null for root pages |
| `creator_id` | UUID? | UUID of creating user |
| `last_updated_by_id` | UUID? | UUID of last updating user |
| `space_id` | UUID | Space this page belongs to |
| `workspace_id` | UUID | Parent workspace UUID |
| `is_locked` | bool | Whether page is locked for editing |
| `content` | str? | Page content as markdown |
| `created_at` | datetime | |
| `updated_at` | datetime | |

## PageMetaOut

Returned by write routes (`create_page`, `update_page`). Same fields as `PageOut` but without `content` - content is not echoed back on write operations.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Page UUID |
| `slug_id` | str | Short URL-friendly identifier |
| `title` | str? | Page title |
| `icon` | str? | Emoji or icon identifier |
| `position` | str? | Sort position within parent |
| `parent_page_id` | UUID? | Parent page UUID |
| `creator_id` | UUID? | UUID of creating user |
| `last_updated_by_id` | UUID? | UUID of last updating user |
| `space_id` | UUID | Space this page belongs to |
| `workspace_id` | UUID | Parent workspace UUID |
| `is_locked` | bool | Whether page is locked for editing |
| `created_at` | datetime | |
| `updated_at` | datetime | |

## PageTreeNode

Used in `SpaceTreeOut` and recursively in tree responses.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Page UUID |
| `title` | str? | Page title |
| `slug_id` | str | Short URL-friendly identifier |
| `icon` | str? | Emoji or icon identifier |
| `parent_page_id` | UUID? | Parent page UUID |
| `position` | str? | Sort position |
| `has_children` | bool | Whether this node has child pages |
| `children` | list[PageTreeNode] | Recursively nested child nodes |

## SpaceTreeOut

Returned by `get_space_tree`.

| Field | Type | Description |
|---|---|---|
| `space` | SpaceSummaryOut | Space summary |
| `root_pages` | list[PageTreeNode] | Top-level pages with nested descendants |
| `orphan_pages` | list[PageTreeNode] | Pages whose parent is missing or unreachable |

## ReplicaStandardsOut

Returned by `get_replica_standards`. Contains all naming, layout, and sync policy strings as fields. See the Replica System page for what each policy means.

## ReplicaNameResolutionOut

Returned by `resolve_replica_directory_name`.

| Field | Type | Description |
|---|---|---|
| `input_title` | str | Original requested title |
| `slug_id` | str? | Slug identifier provided |
| `page_id` | UUID? | Page UUID provided |
| `sanitized_title` | str | Filesystem-safe form of the title |
| `local_dir_name` | str | Resolved final directory name |
| `collision_strategy` | str | Strategy used: `title`, `title_plus_slug_id`, `title_plus_short_page_id`, or `title_plus_numeric_fallback` |

## ReplicaTreeNode

Represents one page in the server-side replica tree. Returned nested in `ReplicaStructureOut`.

| Field | Type | Description |
|---|---|---|
| `id` | UUID | Remote page UUID |
| `title` | str? | Page title |
| `slug_id` | str | Short identifier |
| `parent_page_id` | UUID? | Parent page UUID |
| `local_dir_name` | str | Resolved directory name at this level |
| `local_dir_path` | str | Replica-relative directory path |
| `content_file_path` | str | Replica-relative path to `page.md` |
| `meta_file_path` | str | Replica-relative path to `_meta.json` |
| `children` | list[ReplicaTreeNode] | Nested child replicas |

## ReplicaStructureOut

Returned by `get_replica_structure`.

| Field | Type | Description |
|---|---|---|
| `space` | SpaceSummaryOut | Space summary |
| `replica_root` | str | Replica root directory path |
| `replica_meta_file_path` | str | Path to `_replica.json` |
| `tree_cache_file_path` | str | Path to `_tree.json` |
| `standards` | ReplicaStandardsOut | Embedded standards |
| `root_pages` | list[ReplicaTreeNode] | Root-level replica nodes |
| `orphan_pages` | list[ReplicaTreeNode] | Orphan replica nodes |

## LocalReplicaPageCreateIn

Used by `create_local_replica_page`.

| Field | Type | Description |
|---|---|---|
| `title` | str | Title for the new local-only page |
| `content` | str | Initial markdown content written to `page.md` |
| `parent_page_id` | UUID? | Optional remote parent page UUID |
| `parent_local_path` | str? | Optional parent local content-file path or page directory path for nesting under an existing local-only page |

## LocalReplicaPageOut

Returned by `create_local_replica_page`.

Key fields:

| Field | Type | Description |
|---|---|---|
| `replica_root` | str | Replica root relative to the configured base |
| `title` | str | Title of the scaffolded page |
| `parent_page_id` | UUID? | Resolved remote parent page UUID when already known |
| `parent_local_path` | str? | Resolved parent local directory path when nested |
| `local_dir_path` | str | Local directory for the new page |
| `content_file_path` | str | Path to the new `page.md` |
| `meta_file_path` | str | Path to the new `_meta.json` |
| `sync_state` | literal | Always `local_only_page` for a newly scaffolded local page |
| `recommended_next_action` | literal | Always `push_replica` once local edits are ready |
| `naming` | ReplicaNameResolutionOut | Naming decision used for the new directory |

## SyncSelectionIn

Used by `pull_replica` and `push_replica` to target all pages or a subset.

| Field | Type | Description |
|---|---|---|
| `page_ids` | list[UUID] | Optional remote page UUIDs to target |
| `local_paths` | list[str] | Optional server-side replica paths to target, useful for local-only pages |
| `force` | bool | Whether the operation should force its source of truth when conflicts exist |

## PageSyncStatusOut

Returned inside `SpaceSyncStatusOut.pages`.

Key fields:

| Field | Type | Description |
|---|---|---|
| `page_id` | UUID? | Remote page UUID when the page exists remotely |
| `title` | str? | Best-known title |
| `sync_state` | literal | `synced`, `local_only_change`, `remote_only_change`, `conflicted`, `remote_only_page`, `local_only_page`, `remote_deleted`, or `local_missing` |
| `summary` | str | Human-readable state summary |
| `local_path` | str? | Replica-relative path to `page.md` |
| `remote_exists` | bool | Whether the page exists in Docmost |
| `local_exists` | bool | Whether the local content file exists |
| `local_changed` | bool | Whether local content differs from the last sync base |
| `remote_changed` | bool | Whether remote content differs from the last sync base |
| `has_conflicts` | bool | Whether both sides changed |
| `recommended_action` | literal | Next recommended tool or action |
| `allowed_actions` | list[str] | Allowed next-step actions for automation |

## SpaceSyncStatusOut

Returned by `get_sync_status`.

| Field | Type | Description |
|---|---|---|
| `space` | SpaceSummaryOut | Space summary |
| `replica_root` | str | Replica root relative to the configured base |
| `replica_root_abs_path` | str | Absolute server-side replica path |
| `replica_exists` | bool | Whether the replica exists on disk |
| `pipeline_expectations` | list[str] | Status-first sync workflow guidance |
| `counts` | SyncStatusCountsOut | Count of pages in each sync state |
| `pages` | list[PageSyncStatusOut] | Per-page sync state |

## SyncDiffHunkOut and SpaceSyncDiffOut

`get_sync_diff` returns `SpaceSyncDiffOut`, which contains one `PageSyncDiffOut` per selected page.
Each page diff contains `SyncDiffHunkOut` entries with:

- hunk kind: `replace`, `insert`, or `delete`
- local and remote start/end line numbers
- the local lines and remote lines participating in the hunk

## SyncOperationResultOut and SyncOperationOut

`pull_replica` and `push_replica` return `SyncOperationOut`.

| Field | Type | Description |
|---|---|---|
| `operation` | literal | `pull` or `push` |
| `force` | bool | Whether the operation forced its source of truth |
| `applied_count` | int | Number of pages actually changed |
| `skipped_count` | int | Number of pages skipped |
| `conflict_count` | int | Number of pages that returned conflict hunks |
| `results` | list[SyncOperationResultOut] | Per-page operation results |

Each `SyncOperationResultOut` includes:

- `sync_state_before` - the page state before the operation
- `action` - the action taken or attempted
- `applied` - whether the operation changed state
- `message` - human-readable outcome
- `recommended_next_action` - the next step to follow when the operation was blocked or skipped
- `conflicts` - returned hunks when the operation could not proceed safely
