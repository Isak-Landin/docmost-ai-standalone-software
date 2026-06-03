Page routes are always space-scoped. Reads come from the Docmost database; writes go through the bridge write pipeline. The helper-facing equivalents live under `/v1` and `/helper/v1`.

## `GET /spaces/{space_id}/pages`

Returns all non-deleted pages in the space (no nesting). Errors: `404` space, `503` database.

## `GET /spaces/{space_id}/pages/{page_id}`

Returns one page with markdown content (rendered from Docmost's stored ProseMirror). The helper-facing read also includes `current_revision_hash` from the bridge head. Errors: `404` if the page does not exist, is deleted, or belongs to another space; `503` database.

## `POST /spaces/{space_id}/pages`

Creates a page. Provide `parent_page_id` to nest under an existing page.

| Field | Required | Description |
| --- | --- | --- |
| `title` | no | page title (a separate field, not an H1 in the body) |
| `content` | no | markdown |
| `parent_page_id` | no | parent page UUID |

The write records a bridge intent, calls Docmost, and finalizes the head from a canonical read-back. Errors: `400`, `401`, `404` parent.

## `PUT /spaces/{space_id}/pages/{page_id}`

Updates a page's title and/or content. `operation` is `replace` (default), `append`, or `prepend`. Prefer update over delete-and-recreate so Docmost preserves page history. Aligned callers (`helper` / `auto_sync`) must pass a matching `base_revision_hash` or the write is rejected `409`; the direct `crud` route does not require alignment. Errors: `400`, `401`, `404`, `409`.

## `DELETE /spaces/{space_id}/pages/{page_id}`

Soft-deletes a page (moves it to Docmost trash) and marks the bridge head deleted. Errors: `401`, `404`.

## Move (helper surface)

`POST /v1/spaces/{id}/pages/{page_id}/move` re-parents or reorders a page id-preservingly. `position` is a fractional-index string among the target siblings; pass `parent_page_id` to re-parent or omit to reorder. This is how a page is moved without losing its identity or history.

## Reconcile vs direct writes

In normal model work these page operations are not called directly. The model edits `page.md` and the directory layout, then the helper drives create / update / move through the reconcile brain. The direct routes remain for HTTP integrations and operator use.