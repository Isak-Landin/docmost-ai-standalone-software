# REST API

The REST API is served by FastAPI at the root of the service.

## Route summary

### Read routes

| Method | Path | Router module | Description |
|---|---|---|---|
| `GET` | `/health` | `app/query/routers/health.py` | Process health check |
| `GET` | `/spaces` | `app/query/routers/spaces.py` | List all non-deleted spaces |
| `GET` | `/spaces/{space_id}` | `app/query/routers/spaces.py` | Get one space |
| `GET` | `/spaces/{space_id}/tree` | `app/query/routers/spaces.py` | Get nested page tree for a space |
| `GET` | `/spaces/{space_id}/pages` | `app/query/routers/pages.py` | List all pages in a space |
| `GET` | `/spaces/{space_id}/pages/{page_id}` | `app/query/routers/pages.py` | Get one page in its space |
| `GET` | `/spaces/{space_id}/replica-structure` | `app/query/routers/replica.py` | Get deterministic local replica layout for a space |
| `GET` | `/replica/standards` | `app/query/routers/replica.py` | Get local replica naming, structure, and sync rules |
| `GET` | `/replica/resolve-directory-name` | `app/query/routers/replica.py` | Resolve local directory name for a page title |
| `POST` | `/spaces/{space_id}/sync/status` | `app/sync/routers.py` | Get sync status from client-reported local page state |
| `POST` | `/spaces/{space_id}/sync/diff` | `app/sync/routers.py` | Get line-based local-vs-remote diff hunks from client-reported local page state |

### Write routes

| Method | Path | Router module | Description |
|---|---|---|---|
| `POST` | `/spaces` | `app/write/routers/spaces.py` | Create a new space |
| `DELETE` | `/spaces/{space_id}` | `app/write/routers/spaces.py` | Permanently delete a space |
| `POST` | `/spaces/{space_id}/pages` | `app/write/routers/pages.py` | Create a new page |
| `PUT` | `/spaces/{space_id}/pages/{page_id}` | `app/write/routers/pages.py` | Update page title and/or content |
| `DELETE` | `/spaces/{space_id}/pages/{page_id}` | `app/write/routers/pages.py` | Soft-delete a page |
| `POST` | `/spaces/{space_id}/sync/pull` | `app/sync/routers.py` | Return canonical remote snapshots the client should write locally |
| `POST` | `/spaces/{space_id}/sync/push` | `app/sync/routers.py` | Push selected client-local page changes back to remote Docmost |
| `POST` | `/spaces/{space_id}/sync/local-pages` | `app/sync/routers.py` | Return the canonical local-only page scaffold plan for the client to write locally |

### Automation routes (`/auto-mcp`)

Lower-context routes used by automation, backed by the bridge write pipeline.

| Method | Path | Router module | Description |
|---|---|---|---|
| `POST` | `/auto-mcp/spaces/{space_id}/pages/apply` | `app/auto_mcp/routers.py` | Apply a batch of page create/update operations; returns applied and drifted pages |
| `POST` | `/auto-mcp/spaces/{space_id}/observe` | `app/auto_mcp/routers.py` | Run one observer pass for the space and record results |

### Helper routes (`/helper/v1`)

A helper-facing surface for reads, writes, and local page snapshots, also backed by the bridge.

| Method | Path | Description |
|---|---|---|
| `GET` | `/helper/v1/spaces`, `/spaces/{id}`, `/spaces/{id}/tree`, `/spaces/{id}/pages`, `/spaces/{id}/pages/{page_id}` | Reads (page reads include the current bridge revision hash) |
| `POST` / `DELETE` | `/helper/v1/spaces`, `/helper/v1/spaces/{id}` | Create / delete a space |
| `POST` / `PUT` / `DELETE` | `/helper/v1/spaces/{id}/pages`, `/helper/v1/spaces/{id}/pages/{page_id}` | Create / update / delete a page |
| `POST` / `GET` / `DELETE` | `/helper/v1/spaces/{id}/pages/{page_id}/snapshots[/{snapshot_id}]` | Create / read / delete a local page snapshot |

## Shared HTTP error codes

| Code | Meaning |
|---|---|
| `400` | Validation error or Docmost rejected the request |
| `401` | Docmost credentials invalid |
| `409` | Bridge conflict - an aligned write did not match the current bridge head |
| `502` | Upstream Docmost REST or sync orchestration failed |
| `404` | Space or page not found (deleted or never existed) |
| `503` | Docmost database connection failed |

## Lookup flow

The API is intentionally **space-first**:

1. Call `GET /spaces` to get the UUID of the target space
2. Use that UUID as `space_id` in all further calls
3. Use `GET /spaces/{space_id}/tree` for the full nested hierarchy
4. Use `GET /spaces/{space_id}/pages` for the flat page list
5. Use `GET /spaces/{space_id}/pages/{page_id}` only once you have the page UUID

Page lookup is not global. Pages are always scoped to a space.

## Sync flow

The sync API is status-first and one-way per operation:

1. Choose the working copy first. Pass `local_root` when the active local replica is not the default `./{space_name}-replica`.
2. Call `POST /spaces/{space_id}/sync/status` first and pass the current local page state in the request body.
3. Call `POST /spaces/{space_id}/sync/diff` before any force pull or force push decision.
4. Call `POST /spaces/{space_id}/sync/local-pages` to get the canonical scaffold for a brand-new local-only page before it exists on remote.
5. Call `POST /spaces/{space_id}/sync/pull` to get the canonical remote snapshots the client should write locally.
6. Call `POST /spaces/{space_id}/sync/push` to write selected client-local page changes back to remote Docmost.
7. Do not expect pull to auto-push first, or push to auto-pull first. Follow `recommended_next_action` when an operation is blocked.

`POST /spaces/{space_id}/sync/status`, `POST /spaces/{space_id}/sync/diff`, `POST /spaces/{space_id}/sync/pull`, and `POST /spaces/{space_id}/sync/push` all operate on client-reported local page state.

A typical request body for pull or push is:

```json
{
  "local_root": "",
  "pages": [],
  "page_ids": [],
  "local_paths": [],
  "force": false
}
```

- `pages` is the client-local page set being compared or pushed
- leave `page_ids` and `local_paths` empty to operate on the whole selected working copy
- use `page_ids` for tracked remote pages inside that working copy
- use `local_paths` for local-only pages that do not have a remote UUID yet
- use `local_root` whenever the working copy is not the default replica root
- set `force` only after reviewing the diff for a conflicting page

## Interactive docs

FastAPI auto-generates OpenAPI docs. Available at `/docs` and `/redoc` when the service is running.
