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
| `GET` | `/spaces/{space_id}/sync/status` | `app/sync/routers.py` | Get server-side replica sync status for a space |
| `GET` | `/spaces/{space_id}/sync/diff` | `app/sync/routers.py` | Get line-based local-vs-remote diff hunks |

### Write routes

| Method | Path | Router module | Description |
|---|---|---|---|
| `POST` | `/spaces` | `app/write/routers/spaces.py` | Create a new space |
| `DELETE` | `/spaces/{space_id}` | `app/write/routers/spaces.py` | Permanently delete a space |
| `POST` | `/spaces/{space_id}/pages` | `app/write/routers/pages.py` | Create a new page |
| `PUT` | `/spaces/{space_id}/pages/{page_id}` | `app/write/routers/pages.py` | Update page title and/or content |
| `DELETE` | `/spaces/{space_id}/pages/{page_id}` | `app/write/routers/pages.py` | Soft-delete a page |
| `POST` | `/spaces/{space_id}/sync/pull` | `app/sync/routers.py` | Pull remote Docmost content into the server-side replica |
| `POST` | `/spaces/{space_id}/sync/push` | `app/sync/routers.py` | Push server-side replica changes back to remote Docmost |

## Shared HTTP error codes

| Code | Meaning |
|---|---|
| `400` | Validation error or Docmost rejected the request |
| `401` | Docmost credentials invalid |
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

1. Call `GET /spaces/{space_id}/sync/status` first to classify each page as synced, local-ahead, remote-ahead, conflicting, local-only, or remote-only.
2. Call `GET /spaces/{space_id}/sync/diff` before any force pull or force push decision.
3. Call `POST /spaces/{space_id}/sync/pull` to materialize or refresh the server-side replica from remote Docmost.
4. Call `POST /spaces/{space_id}/sync/push` to write server-side replica changes back to remote Docmost.
5. Do not expect pull to auto-push first, or push to auto-pull first. Follow `recommended_next_action` when an operation is blocked.

Both `POST /spaces/{space_id}/sync/pull` and `POST /spaces/{space_id}/sync/push` accept the same JSON body:

```json
{
  "page_ids": [],
  "local_paths": [],
  "force": false
}
```

- leave `page_ids` and `local_paths` empty to operate on the whole space
- use `page_ids` for tracked remote pages
- use `local_paths` for local-only pages that do not have a remote UUID yet
- set `force` only after reviewing the diff for a conflicting page

## Interactive docs

FastAPI auto-generates OpenAPI docs. Available at `/docs` and `/redoc` when the service is running.
