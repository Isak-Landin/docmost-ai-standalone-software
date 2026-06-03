These routes expose the server-side replica planners: naming rules and deterministic local layouts. They plan canonical paths but perform no client file IO (the helper owns local IO). They are used by the operator `/mcp` surface and by the `/sync` routes.

## `GET /replica/standards`

Returns the shared naming, layout, and sync rules for local replicas (`ReplicaStandardsOut`). No parameters, no errors.

## `GET /replica/resolve-directory-name`

Resolves the correct local directory name for a page title under the current naming standard.

| Parameter | Required | Description |
| --- | --- | --- |
| `title` | yes | page title to resolve |
| `slug_id` | no | collision suffix |
| `page_id` | no | fallback collision suffix |
| `existing_dir_names` | no | sibling names already in use |

Collision order: sanitized title, then `{title}__{slug_id}`, then `{title}__{short_page_id}`, then a numeric fallback. No spaces are allowed in any local directory or file name.

## `GET /spaces/{space_id}/replica-structure`

Returns the full deterministic local layout for one space - nested directory paths, `page.md` paths, and `_meta.json` paths for every page. Errors: `404` space, `503` database.

## Relationship to the helper replica

The helper (`helper/helper/replica.py`) owns the actual on-disk replica: `page.md`, `_meta.json`, `_replica.json`, and `_tree.json`, plus discovery by `_replica.json` space id under `DOCMOST_REPLICA_BASE`. These server planners describe canonical naming; the helper is what writes and tracks the files during the reconcile flow. See the Replica System page.