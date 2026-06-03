The REST API and helper-facing routes are served by FastAPI. The `/mcp` endpoint is the operator surface only (see the MCP Server page). All page content is markdown in and out; the page title is a separate parameter.

## Read routes (direct Docmost DB)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/health` | process liveness only |
| `GET` | `/spaces` | list non-deleted spaces |
| `GET` | `/spaces/{space_id}` | get one space |
| `GET` | `/spaces/{space_id}/tree` | nested page tree |
| `GET` | `/spaces/{space_id}/pages` | flat page list |
| `GET` | `/spaces/{space_id}/pages/{page_id}` | one page with markdown content |
| `GET` | `/spaces/{space_id}/replica-structure` | server-side replica layout |
| `GET` | `/replica/standards` | replica naming / structure / sync rules |
| `GET` | `/replica/resolve-directory-name` | resolve a local directory name for a title |

## Direct write routes (bridge pipeline, crud mode)

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/spaces` | create a space |
| `DELETE` | `/spaces/{space_id}` | permanently delete a space and its pages |
| `POST` | `/spaces/{space_id}/pages` | create a page (`parent_page_id` for a child) |
| `PUT` | `/spaces/{space_id}/pages/{page_id}` | update title and/or content (`replace` / `append` / `prepend`) |
| `DELETE` | `/spaces/{space_id}/pages/{page_id}` | soft-delete a page |

## Helper-facing routes (under `/v1` and `/helper/v1`)

| Method | Path | Description |
| --- | --- | --- |
| `GET` | `/v1/contract` | helper <-> server contract version + capabilities |
| `GET` | `/v1/health` | process health |
| `GET` | `/v1/spaces[...]`, `/v1/spaces/{id}/pages[...]` | reads (page carries `current_revision_hash`) |
| `POST` / `DELETE` | `/v1/spaces[...]` | create / delete space (helper mode) |
| `POST` / `PUT` / `DELETE` | `/v1/spaces/{id}/pages[...]` | create / update / delete page (helper mode) |
| `POST` | `/v1/spaces/{id}/pages/{pid}/move` | move / re-parent a page (id-preserving) |
| `POST` / `GET` / `DELETE` | `/v1/spaces/{id}/pages/{pid}/snapshots[...]` | local-page snapshots (stash) |
| `POST` | `/v1/spaces/{id}/reconcile` | classify + apply a scoped reconcile (four buckets) |
| `POST` | `/v1/spaces/{id}/pages/{pid}/resolve` | resolve a conflict aligned to the current remote head |
| `POST` | `/v1/spaces/{id}/pages/{pid}/confirm-deletion` | apply a confirmed deletion (`remote` / `local`) |

## Automation + legacy sync routes

| Method | Path | Description |
| --- | --- | --- |
| `POST` | `/auto-mcp/spaces/{space_id}/pages/apply` | batch create / update through the bridge pipeline |
| `POST` | `/auto-mcp/spaces/{space_id}/observe` | run one observer pass for a space |
| `POST` | `/spaces/{space_id}/sync/status` | client-state sync status |
| `POST` | `/spaces/{space_id}/sync/diff` | client-state diff hunks |
| `POST` | `/spaces/{space_id}/sync/local-pages` | plan a new local-only page |
| `POST` | `/spaces/{space_id}/sync/pull` | pull remote into a client working copy |
| `POST` | `/spaces/{space_id}/sync/push` | push a client working copy to remote |

## Shared HTTP error codes

| Code | Meaning |
| --- | --- |
| `400` | validation error or Docmost rejected the request |
| `401` | Docmost credentials invalid |
| `404` | space or page not found |
| `409` | bridge head mismatch / conflict (aligned writes) |
| `502` | bridge or Docmost write failure |
| `503` | Docmost database connection failed |

## Child pages

The Health, Spaces, Pages, and Replica child pages document the individual read and write routes in detail. Interactive OpenAPI docs are at `/docs` and `/redoc`.