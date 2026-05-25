# Docmost Write API

This document covers how to programmatically create and update Docmost pages from this service.
It reflects findings from direct inspection of the running Docmost container's compiled source.

## Version requirement

**Docmost v0.71.1 or later is required for content writes to work.**

In older versions, `CreatePageDto` and `UpdatePageDto` did not declare `content` or `format`.
NestJS `ValidationPipe({ whitelist: true })` strips undeclared fields, so content was silently
discarded and pages were always created empty. From v0.71.1 both fields are declared and
fully supported. This was confirmed by direct container source inspection and live testing.

To check the Docmost version on your host:

```bash
docker exec docmost cat /app/apps/server/package.json | grep '"version"' | head -1
```

---

## Transport: REST, not WebSocket

The browser uses a WebSocket at `ws://<host>/collab` (Hocuspocus / Y.js CRDT protocol).
This produces the "lost connection" messages seen in the UI and requires speaking the binary
Hocuspocus protocol. We do not use this.

We use the **Docmost REST API** instead. The REST write endpoints live behind the same
authentication as the browser and internally handle all Y.js / collab bookkeeping themselves.
No knowledge of Y.js, Hocuspocus, or CRDT is required on our side.

---

## Authentication

The REST API requires a valid session cookie or `Authorization: Bearer <token>` header.

Obtain a token by calling:

```
POST http://<docmost-host>/api/auth/login
Content-Type: application/json

{
  "email": "<user email>",
  "password": "<user password>"
}
```

The response sets a **Set-Cookie: `authToken=<jwt>`** header.
The JSON body only contains `{"success": true, "status": 200}` - there is no token in the body.

Extract the `authToken` cookie value. This JWT can then be used in two equivalent ways:
- `Cookie: authToken=<jwt>` header, or
- `Authorization: Bearer <jwt>` header (verified working; preferred for non-browser clients).

Token type required: standard **ACCESS** JWT (not the internal COLLAB JWT used by the
WebSocket gateway - that is only used internally by the collab layer and is not needed here).

---

## Important: All Docmost API routes are POST

Every Docmost API endpoint uses `POST`, including listing/reading operations.
`GET /api/spaces` returns the SPA HTML (caught by the catch-all static file server).
`POST /api/spaces` returns JSON.  This applies to **all** Docmost API routes.

---

## Creating a page

`POST /api/pages/create`

Creates a new page with optional full content in a single request.
`create` is self-contained: it parses the content, builds the ProseMirror JSON,
generates the Y.js binary (`ydoc`), and writes everything to the database directly.
No follow-up `update` call is needed for a complete page.

### Request body

| Field         | Type   | Required | Description |
|---|---|---|---|
| `spaceId`     | UUID   | yes      | Target space UUID |
| `title`       | string | no       | Page title |
| `icon`        | string | no       | Emoji or icon identifier |
| `parentPageId`| UUID   | no       | Parent page UUID. Omit for a root-level page. |
| `content`     | string or object | no | Page body. Required if `format` is set. |
| `format`      | string | no (with content) | `markdown`, `html`, or `json` (ProseMirror JSON). |

### Content format notes

- `markdown` - converted markdown -> HTML -> ProseMirror JSON internally
- `html` - converted HTML -> ProseMirror JSON internally
- `json` - ProseMirror JSON passed through directly (validated before write)

### Example: create a complete page from markdown

```
POST /api/pages/create
Authorization: Bearer <token>
Content-Type: application/json

{
  "spaceId": "019cd304-f920-7b06-9894-4bf1e100541b",
  "title": "My Page",
  "parentPageId": "019cee70-f6db-7629-b2fc-0aa83fe6cb57",
  "content": "# My Page\n\nThis is the body.",
  "format": "markdown"
}
```

### What the server does internally

1. Validates `parentPageId` is in the same space (throws 404 if not)
2. Calls `parseProsemirrorContent(content, format)`:
   - markdown path: `markdownToHtml()` -> `htmlToJson()`
   - html path: `htmlToJson()`
   - json path: validates with `jsonToNode()`, throws 400 on invalid
3. Derives `textContent` (plain text) from ProseMirror JSON
4. Builds binary `ydoc` via `createYdocFromJson()` - this is what the collab layer
   would read if a browser later opens the page
5. Calls `pageRepo.insertPage()` - single direct DB write, no collab gateway involved
6. Queues `ADD_PAGE_WATCHERS` job (adds the creating user as a page watcher)

### Response

The created page object. Relevant fields:

```json
{
  "id": "<uuid>",
  "slugId": "<short id>",
  "title": "...",
  "spaceId": "...",
  "parentPageId": "...",
  "creatorId": "...",
  "content": { ... },
  "createdAt": "...",
  "updatedAt": "..."
}
```

---

## Updating a page

`POST /api/pages/update`

Updates title, icon, and/or content of an existing page.
When content is provided, this routes through the Hocuspocus collab gateway internally
(via `collaborationGateway.handleYjsEvent('updatePageContent', ...)`) to update the
live Y.js document alongside the DB - ensuring consistency if the page is open in a
browser at the same time.

### Request body

| Field       | Type   | Required | Description |
|---|---|---|---|
| `pageId`    | UUID   | yes      | Target page UUID |
| `title`     | string | no       | New title |
| `icon`      | string | no       | New icon |
| `content`   | string or object | no | New body content. Requires `operation` and `format`. |
| `operation` | string | with content | `replace`, `append`, or `prepend` |
| `format`    | string | with content | `markdown`, `html`, or `json` |

### Example: replace page body from markdown

```
POST /api/pages/update
Authorization: Bearer <token>
Content-Type: application/json

{
  "pageId": "019cd305-07a5-75e3-a85a-4b22a8b29fdd",
  "content": "# Updated\n\nNew content here.",
  "operation": "replace",
  "format": "markdown"
}
```

### What the server does internally (content path)

1. Calls `parseProsemirrorContent(content, format)` - same conversion as `create`
2. Calls `collaborationGateway.handleYjsEvent('updatePageContent', 'page.<pageId>', { operation, prosemirrorJson, user })`
3. Inside the collab handler, `operation` determines how the new JSON is merged into the Y.js doc:
   - `replace` - replaces the entire document content
   - `append` - appends nodes after existing content
   - `prepend` - inserts nodes before existing content
4. `PersistenceExtension.onStoreDocument()` is triggered (debounced 10-45 s) and writes:
   - `pages.content` (ProseMirror JSON)
   - `pages.ydoc` (binary Y.js state)
   - `pages.textContent` (plain text)
   - `pages.lastUpdatedById`
   - `pages.contributorIds`
5. After store, queues: AI indexing, page history snapshot, mention notifications

### Note on debounce

The collab gateway debounces persistence by **10 s** (up to **45 s max**). A page update
via REST may not be readable from the DB immediately. If we need to read back the content
right after writing, add a short wait or read from the REST response instead.

---

## When to use create vs update

| Goal | Endpoint |
|---|---|
| Create a new page with full content | `POST /api/pages/create` with `content` + `format` |
| Create an empty page (fill later) | `POST /api/pages/create` without content |
| Replace/append/prepend content on an existing page | `POST /api/pages/update` with `operation` + `content` + `format` |
| Rename a page or change its icon only | `POST /api/pages/update` with `title` / `icon`, no content |

For our use case (syncing the server-side replica -> remote Docmost), these endpoints are the
low-level building blocks used by the higher-level sync workflow:

1. use `POST /spaces/{space_id}/sync/local-pages` to scaffold a brand-new local-only page in the server-side replica
2. use replica status/diff tooling to determine whether the page is local-only, remote-only, or conflicting
3. let `push_replica` call `POST /api/pages/create` when a local-only replica page needs to become a new remote page
4. retain the returned `id` for future `POST /api/pages/update` calls when the page already exists remotely
5. only bypass the higher-level sync workflow when you intentionally need direct per-page control

---

## Error responses

| HTTP code | Reason |
|---|---|
| 400 | Invalid content format (ProseMirror validation failed) |
| 401 | Not authenticated |
| 403 | No permission to write to this space |
| 404 | Space, parent page, or target page not found |

---

## Source locations (inside Docmost container)

| Component | Path |
|---|---|
| Page REST controller | `/app/apps/server/dist/core/page/page.controller.js` |
| Page service (create/update logic) | `/app/apps/server/dist/core/page/services/page.service.js` |
| Content parser (`parseProsemirrorContent`) | same as above |
| Collab gateway (Y.js event handler) | `/app/apps/server/dist/collaboration/collaboration.gateway.js` |
| Collab handler (updatePageContent event) | `/app/apps/server/dist/collaboration/collaboration.handler.js` |
| Persistence extension (DB writes) | `/app/apps/server/dist/collaboration/extensions/persistence.extension.js` |
| CreatePageDto | `/app/apps/server/dist/core/page/dto/create-page.dto.js` |
| UpdatePageDto | `/app/apps/server/dist/core/page/dto/update-page.dto.js` |
