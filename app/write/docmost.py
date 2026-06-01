"""Thin httpx wrapper around the Docmost REST write API.

All operations that mutate Docmost state live here.  The module:
- Reads DOCMOST_APP_URL from env via app.docmost_auth.auth.
- Uses app.docmost_auth.auth.get_token() for authentication, which logs
  in automatically on first call and keeps the token in memory.
- Retries once on HTTP 401 by invalidating the cached token and logging in
  again — transparent to callers.
- Accepts and returns markdown for all content fields.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import httpx

from app.docmost_auth.auth import auth_headers, invalidate_token


def _base_url() -> str:
    url = os.getenv("DOCMOST_APP_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("DOCMOST_APP_URL is not set")
    return url


def _post(path: str, payload: dict[str, Any]) -> dict[str, Any]:
    """POST to the Docmost API with automatic 401-retry.

    Unwraps the top-level ``data`` key that Docmost wraps all responses in.
    """
    url = f"{_base_url()}{path}"
    for attempt in range(2):
        response = httpx.post(url, json=payload, headers=auth_headers())
        if response.status_code == 401 and attempt == 0:
            invalidate_token()
            continue
        response.raise_for_status()
        body = response.json()
        return body.get("data", body)
    response.raise_for_status()
    return {}


# ---------------------------------------------------------------------------
# Space operations
# ---------------------------------------------------------------------------


def create_space(name: str, slug: str, description: Optional[str] = None) -> dict[str, Any]:
    """Create a new Docmost space.

    Args:
        name: Display name. 2–100 characters.
        slug: URL identifier. 2–100 alphanumeric characters.
        description: Optional plain-text description.

    Returns:
        The created space object as returned by Docmost.
    """
    payload: dict[str, Any] = {"name": name, "slug": slug}
    if description is not None:
        payload["description"] = description
    return _post("/api/spaces/create", payload)


def delete_space(space_id: str) -> dict[str, Any]:
    """Permanently delete a space and all its contents.

    Args:
        space_id: UUID string of the space to delete.

    Returns:
        Docmost response (typically {"message": "Space deleted successfully"}).
    """
    return _post("/api/spaces/delete", {"spaceId": space_id})


# ---------------------------------------------------------------------------
# Page operations
# ---------------------------------------------------------------------------


def create_page(
    space_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    parent_page_id: Optional[str] = None,
) -> dict[str, Any]:
    """Create a new page in a space, optionally with full markdown content.

    If *content* is provided, Docmost parses it as markdown → ProseMirror JSON
    in a single atomic write (no follow-up update needed).
    If *parent_page_id* is given, the page is created as a child of that page.

    Args:
        space_id: UUID of the target space.
        title: Page title (optional — defaults to empty in Docmost).
        content: Markdown text for the page body (optional).
        parent_page_id: UUID of the parent page for nested creation (optional).

    Returns:
        The created page object as returned by Docmost.
    """
    payload: dict[str, Any] = {"spaceId": space_id}
    if title is not None:
        payload["title"] = title
    if content is not None:
        payload["content"] = content
        payload["format"] = "markdown"
    if parent_page_id is not None:
        payload["parentPageId"] = parent_page_id
    return _post("/api/pages/create", payload)


def update_page(
    page_id: str,
    title: Optional[str] = None,
    content: Optional[str] = None,
    operation: str = "replace",
    icon: Optional[str] = None,
) -> dict[str, Any]:
    """Update an existing page's title and/or content.

    Prefer *update* over delete+create so the page retains its history.

    Args:
        page_id: UUID of the page to update.
        title: New title (optional — unchanged if omitted).
        content: Markdown content (optional — unchanged if omitted).
        operation: How content is applied: "replace" (default), "append", or "prepend".

    Returns:
        The updated page object as returned by Docmost.
    """
    payload: dict[str, Any] = {"pageId": page_id}
    if title is not None:
        payload["title"] = title
    if icon is not None:
        payload["icon"] = icon
    if content is not None:
        payload["content"] = content
        payload["format"] = "markdown"
        payload["operation"] = operation
    return _post("/api/pages/update", payload)


def move_page(
    page_id: str,
    position: str,
    parent_page_id: Optional[str] = None,
) -> dict[str, Any]:
    """Move/re-parent a page via Docmost's true move endpoint (id-preserving).

    Args:
        page_id: UUID of the page to move.
        position: Fractional-index position string (5-12 chars) among the target siblings.
        parent_page_id: New parent page UUID, or None to keep the current parent (reorder only).

    Returns:
        The moved page object as returned by Docmost.
    """
    payload: dict[str, Any] = {"pageId": page_id, "position": position}
    if parent_page_id is not None:
        payload["parentPageId"] = parent_page_id
    return _post("/api/pages/move", payload)


def delete_page(page_id: str) -> dict[str, Any]:
    """Delete (soft-delete) a page.

    Args:
        page_id: UUID of the page to delete.

    Returns:
        Docmost response (typically {"message": "Page deleted successfully"}).
    """
    return _post("/api/pages/delete", {"pageId": page_id})


def get_page_info(page_id: str) -> dict[str, Any]:
    """Fetch a page with its raw ProseMirror JSON content from Docmost REST.

    Uses ``POST /api/pages/info`` with ``includeContent=true``.
    Docmost returns ``content`` as a ProseMirror JSON object — callers are
    responsible for converting it to the desired output format.

    Args:
        page_id: UUID of the page to fetch.

    Returns:
        The page object with ``content`` as a ProseMirror JSON dict.
    """
    return _post("/api/pages/info", {"pageId": page_id, "includeContent": True})
