# Pages

All page routes are scoped to a space. You must provide the `space_id` UUID.

Write routes (`POST` / `PUT` / `DELETE`) go through the bridge write pipeline, which records the
write in the bridge database around the remote Docmost REST call.

## `GET /spaces/{space_id}/pages`

Returns all non-deleted pages belonging to the given space, ordered by creation date.

### Path parameters

| Parameter | Type | Description |
|---|---|---|
| `space_id` | UUID | Space UUID from `GET /spaces` |

### Response model: `list[PageOut]`

### Errors

| Code | Reason |
|---|---|
| `404` | Space not found or deleted |
| `503` | Database connection failed |

---

## `GET /spaces/{space_id}/pages/{page_id}`

Returns a single page by UUID, scoped to the given space. Content is returned as markdown.

Returns `404` if the page does not exist, is deleted, or belongs to a different space.

### Path parameters

| Parameter | Type | Description |
|---|---|---|
| `space_id` | UUID | Space UUID |
| `page_id` | UUID | Page UUID from `GET /spaces/{space_id}/pages` |

### Response model: `PageOut`

### Errors

| Code | Reason |
|---|---|
| `404` | Space not found, or page not found in this space |
| `503` | Database connection failed |

---

## `POST /spaces/{space_id}/pages`

Creates a new page in the given space. Provide `parent_page_id` to create a child page nested under an existing page. Content is accepted as markdown. Authentication is handled transparently.

### Path parameters

| Parameter | Type | Description |
|---|---|---|
| `space_id` | UUID | Space UUID |

### Request body: `PageCreateIn`

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | no | Page title |
| `content` | string | no | Markdown content |
| `parent_page_id` | UUID | no | Parent page UUID for nesting |

### Response model: `PageMetaOut` (metadata only, content not echoed)

### Errors

| Code | Reason |
|---|---|
| `400` | Validation error or Docmost rejected the request |
| `401` | Docmost credentials invalid |
| `404` | Space or parent page not found |

---

## `PUT /spaces/{space_id}/pages/{page_id}`

Updates an existing page's title and/or content. Prefer this over delete+create to preserve Docmost page history.

### Path parameters

| Parameter | Type | Description |
|---|---|---|
| `space_id` | UUID | Space UUID |
| `page_id` | UUID | Page UUID |

### Request body: `PageUpdateIn`

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | string | no | New title (omit to leave unchanged) |
| `content` | string | no | Markdown content |
| `operation` | string | no | `replace` (default), `append`, or `prepend` |

### Response model: `PageMetaOut` (metadata only, content not echoed)

### Errors

| Code | Reason |
|---|---|
| `400` | Validation error or Docmost rejected the request |
| `401` | Docmost credentials invalid |
| `404` | Page not found |

---

## `DELETE /spaces/{space_id}/pages/{page_id}`

Soft-deletes a page (moves it to Docmost trash). Authentication is handled transparently.

### Path parameters

| Parameter | Type | Description |
|---|---|---|
| `space_id` | UUID | Space UUID |
| `page_id` | UUID | Page UUID |

### Response model: `DeletedOut`

### Errors

| Code | Reason |
|---|---|
| `401` | Docmost credentials invalid |
| `404` | Page not found |
