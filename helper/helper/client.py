from __future__ import annotations

import os
from typing import Any
from uuid import UUID

import httpx
from dotenv import load_dotenv

load_dotenv()

_BASE_URL: str | None = None


def _base() -> str:
    global _BASE_URL
    if _BASE_URL is None:
        url = os.getenv("DOCMOST_MCP_SERVER_URL", "").rstrip("/")
        if not url:
            raise RuntimeError(
                "DOCMOST_MCP_SERVER_URL is not set. "
                "Create helper/.env with DOCMOST_MCP_SERVER_URL=<server url>."
            )
        _BASE_URL = url
    return _BASE_URL


def _get(path: str, **params: Any) -> Any:
    with httpx.Client(base_url=_base(), timeout=30) as client:
        r = client.get(path, params={k: v for k, v in params.items() if v is not None})
        r.raise_for_status()
        return r.json()


def _post(path: str, body: dict[str, Any]) -> Any:
    with httpx.Client(base_url=_base(), timeout=30) as client:
        r = client.post(path, json=body)
        r.raise_for_status()
        return r.json()


def _put(path: str, body: dict[str, Any]) -> Any:
    with httpx.Client(base_url=_base(), timeout=30) as client:
        r = client.put(path, json=body)
        r.raise_for_status()
        return r.json()


def _delete(path: str) -> None:
    with httpx.Client(base_url=_base(), timeout=30) as client:
        r = client.delete(path)
        r.raise_for_status()


# ---------------------------------------------------------------------------
# Read operations
# ---------------------------------------------------------------------------

def list_spaces() -> list[dict]:
    return _get("/helper/v1/spaces")


def get_space(space_id: UUID) -> dict:
    return _get(f"/helper/v1/spaces/{space_id}")


def get_space_tree(space_id: UUID) -> dict:
    return _get(f"/helper/v1/spaces/{space_id}/tree")


def list_pages(space_id: UUID) -> list[dict]:
    return _get(f"/helper/v1/spaces/{space_id}/pages")


def get_page(space_id: UUID, page_id: UUID) -> dict:
    return _get(f"/helper/v1/spaces/{space_id}/pages/{page_id}")


# ---------------------------------------------------------------------------
# Write operations — spaces
# ---------------------------------------------------------------------------

def create_space(name: str, slug: str) -> dict:
    return _post("/helper/v1/spaces", {"name": name, "slug": slug})


def delete_space(space_id: UUID) -> None:
    _delete(f"/helper/v1/spaces/{space_id}")


# ---------------------------------------------------------------------------
# Write operations — pages
# ---------------------------------------------------------------------------

def create_page(
    space_id: UUID,
    title: str,
    content: str | None = None,
    parent_page_id: UUID | None = None,
) -> dict:
    body: dict[str, Any] = {"title": title}
    if content is not None:
        body["content"] = content
    if parent_page_id is not None:
        body["parent_page_id"] = str(parent_page_id)
    return _post(f"/helper/v1/spaces/{space_id}/pages", body)


def update_page(
    space_id: UUID,
    page_id: UUID,
    title: str | None = None,
    content: str | None = None,
    operation: str = "replace",
    base_revision_hash: str | None = None,
    force: bool = False,
) -> dict:
    body: dict[str, Any] = {"operation": operation, "force": force}
    if title is not None:
        body["title"] = title
    if content is not None:
        body["content"] = content
    if base_revision_hash is not None:
        body["base_revision_hash"] = base_revision_hash
    return _put(f"/helper/v1/spaces/{space_id}/pages/{page_id}", body)


def delete_page(space_id: UUID, page_id: UUID) -> None:
    _delete(f"/helper/v1/spaces/{space_id}/pages/{page_id}")


# ---------------------------------------------------------------------------
# Batch sync and observer
# ---------------------------------------------------------------------------

def batch_apply(space_id: UUID, pages: list[dict]) -> dict:
    return _post(f"/auto-mcp/spaces/{space_id}/pages/apply", {"pages": pages})


def observe(space_id: UUID) -> dict:
    return _post(f"/auto-mcp/spaces/{space_id}/observe", {})


# ---------------------------------------------------------------------------
# Snapshot operations
# ---------------------------------------------------------------------------

def create_snapshot(
    space_id: UUID,
    page_id: UUID,
    content: str,
    base_revision_hash: str | None = None,
    local_path: str | None = None,
) -> dict:
    body: dict[str, Any] = {"content": content}
    if base_revision_hash is not None:
        body["base_revision_hash"] = base_revision_hash
    if local_path is not None:
        body["local_path"] = local_path
    return _post(f"/helper/v1/spaces/{space_id}/pages/{page_id}/snapshots", body)


def get_snapshot(space_id: UUID, page_id: UUID, snapshot_id: str) -> dict:
    return _get(f"/helper/v1/spaces/{space_id}/pages/{page_id}/snapshots/{snapshot_id}")


def delete_snapshot(space_id: UUID, page_id: UUID, snapshot_id: str) -> None:
    _delete(f"/helper/v1/spaces/{space_id}/pages/{page_id}/snapshots/{snapshot_id}")
