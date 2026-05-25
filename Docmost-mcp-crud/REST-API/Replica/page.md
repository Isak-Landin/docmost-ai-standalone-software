# Replica

The replica routes expose naming rules and deterministic local layouts for documentation replicas. They do not require a database connection (except `replica-structure`).

## `GET /replica/standards`

Returns the shared naming, layout, and sync rules for local documentation replicas.

Use this when a client needs to create or update local replica content without guessing the standard.

### Response model: `ReplicaStandardsOut`

No parameters. No errors.

---

## `GET /replica/resolve-directory-name`

Resolves the correct local directory name for a given page title under the current naming standard.

Use this when a client needs to inspect naming behavior without guessing. For actual local-only page creation, use `POST /spaces/{space_id}/sync/local-pages` so the server scaffolds the replica files.

### Query parameters

| Parameter | Type | Required | Description |
|---|---|---|---|
| `title` | string | yes | Page title to resolve |
| `slug_id` | string | no | Remote or planned slug identifier — used as collision suffix |
| `page_id` | UUID | no | Remote page UUID — used as fallback collision suffix |
| `existing_dir_names` | list[string] | no | Sibling directory names already in use at this level |

### Response model: `ReplicaNameResolutionOut`

### Collision resolution order

1. If the sanitized title is unique among siblings → use title as-is
2. If collision and `slug_id` is available → `{title}__{slug_id}`
3. If still colliding → `{title}__{short_page_id}` (first 8 chars of UUID)
4. If still colliding → `{title}__{short_page_id}-{n}` with incrementing `n`

---

## `GET /spaces/{space_id}/replica-structure`

Returns the full deterministic local replica layout for one space, including nested directory paths, content file paths, and metadata file paths for every page.

Use this instead of guessing how remote Docmost pages should be represented locally.

### Path parameters

| Parameter | Type | Description |
|---|---|---|
| `space_id` | UUID | Space UUID |

### Response model: `ReplicaStructureOut`

### Errors

| Code | Reason |
|---|---|
| `404` | Space not found or deleted |
| `503` | Database connection failed |

### Implementation

`app/query/replica.get_replica_structure()` calls `get_space_tree()` then walks the tree recursively, resolving directory names level-by-level using the collision logic above.
