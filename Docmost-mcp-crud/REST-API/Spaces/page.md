Space routes. Reads come directly from the Docmost database; writes go through the bridge write pipeline to the Docmost REST API. The helper-facing equivalents live under `/v1` and `/helper/v1`.

## `GET /spaces`

Returns all non-deleted spaces from the live Docmost database. Use this first to resolve a `space_id`. Errors: `503` if the database is unreachable.

## `GET /spaces/{space_id}`

Returns one space by UUID. Errors: `404` not found / deleted, `503` database.

## `GET /spaces/{space_id}/tree`

Returns the page hierarchy as a nested tree built from `parent_page_id`.

- `root_pages` - top-level pages (each with nested `children`)
- `orphan_pages` - pages whose parent is missing or unreachable
- `parent_page_id = null` means a top-level page
- pages are sorted by `position` then `created_at`; cycles are broken

Errors: `404`, `503`.

## `POST /spaces`

Creates a space (authentication is transparent).

| Field | Required | Description |
| --- | --- | --- |
| `name` | yes | display name |
| `slug` | yes | alphanumeric, no spaces or dashes (Docmost constraint) |
| `description` | no | optional |

Errors: `400` validation / slug taken, `401` credentials.

## `DELETE /spaces/{space_id}`

Permanently deletes a space and all its pages (irreversible). The bridge marks the space's known heads deleted and records the delete through its write pipeline. Errors: `401`, `404`.

## Helper surface

The helper calls the same operations under `/v1` (`/helper/v1`): `list_spaces`, `get_space`, `get_space_tree`, `create_space`, and `delete_space` (delete runs in `helper` caller mode through the bridge).