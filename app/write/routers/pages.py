from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models import DeletedOut, PageCreateIn, PageMetaOut, PageUpdateIn
from app.write.docmost import create_page as docmost_create_page
from app.write.docmost import delete_page as docmost_delete_page
from app.write.docmost import get_page_info
from app.write.docmost import update_page as docmost_update_page

router = APIRouter(prefix="/spaces/{space_id}/pages", tags=["pages"])


@router.post(
    "",
    response_model=PageMetaOut,
    status_code=201,
    summary="Create a page",
    description=(
        "Creates a new page in the given space. "
        "Provide `parent_page_id` to create a child page nested under an existing page — "
        "arbitrarily deep hierarchies are supported. "
        "Content is accepted as **markdown** and converted server-side. "
        "Returns page identity and metadata. Content is not echoed back. "
        "Authentication is handled transparently."
    ),
    responses={
        400: {"description": "Validation error or Docmost rejected the request."},
        401: {"description": "Docmost credentials invalid."},
        404: {"description": "Space or parent page not found."},
    },
)
def create_page(space_id: UUID, body: PageCreateIn):
    try:
        data = docmost_create_page(
            space_id=str(space_id),
            title=body.title,
            content=body.content,
            parent_page_id=str(body.parent_page_id) if body.parent_page_id else None,
        )
    except Exception as exc:
        _raise_for_docmost_error(exc)

    page = data.get("page", data)
    page_id = page.get("id")
    if not page_id:
        raise HTTPException(status_code=502, detail=f"Docmost create did not return a page id. Response: {data}")

    return _map_page_meta(page)


@router.put(
    "/{page_id}",
    response_model=PageMetaOut,
    summary="Update a page",
    description=(
        "Updates an existing page's title and/or content. "
        "Content is accepted as **markdown**. "
        "Use `operation='replace'` (default) to overwrite, `'append'` to add after existing "
        "content, or `'prepend'` to add before. "
        "Prefer update over delete+create — Docmost preserves page history on update. "
        "Returns page identity and metadata. Content is not echoed back. "
        "Authentication is handled transparently."
    ),
    responses={
        400: {"description": "Validation error or Docmost rejected the request."},
        401: {"description": "Docmost credentials invalid."},
        404: {"description": "Page not found."},
    },
)
def update_page(space_id: UUID, page_id: UUID, body: PageUpdateIn):
    try:
        docmost_update_page(
            page_id=str(page_id),
            title=body.title,
            content=body.content,
            operation=body.operation,
        )
    except Exception as exc:
        _raise_for_docmost_error(exc)

    try:
        full = get_page_info(str(page_id))
    except Exception as exc:
        _raise_for_docmost_error(exc)

    return _map_page_meta(full.get("page", full))


@router.delete(
    "/{page_id}",
    response_model=DeletedOut,
    summary="Delete a page",
    description=(
        "Soft-deletes a page (moves to trash in Docmost). "
        "Authentication is handled transparently."
    ),
    responses={
        401: {"description": "Docmost credentials invalid."},
        404: {"description": "Page not found."},
    },
)
def delete_page(space_id: UUID, page_id: UUID):
    try:
        docmost_delete_page(str(page_id))
    except Exception as exc:
        _raise_for_docmost_error(exc)
    return DeletedOut(deleted=True, id=str(page_id))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _raise_for_docmost_error(exc: Exception) -> None:
    import httpx

    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        try:
            detail = exc.response.json()
        except Exception:
            detail = exc.response.text
        raise HTTPException(status_code=status, detail=detail) from exc
    raise HTTPException(status_code=502, detail=str(exc)) from exc


def _map_page_meta(page: dict) -> PageMetaOut:
    """Map a Docmost page response dict to PageMetaOut (no content)."""
    from datetime import datetime, timezone

    return PageMetaOut(
        id=page["id"],
        slug_id=page.get("slugId") or page.get("slug_id") or "",
        title=page.get("title"),
        icon=page.get("icon"),
        position=page.get("position"),
        parent_page_id=page.get("parentPageId") or page.get("parent_page_id"),
        creator_id=page.get("creatorId") or page.get("creator_id"),
        last_updated_by_id=page.get("lastUpdatedById") or page.get("last_updated_by_id"),
        space_id=page.get("spaceId") or page.get("space_id"),
        workspace_id=page.get("workspaceId") or page.get("workspace_id"),
        is_locked=page.get("isLocked") or page.get("is_locked") or False,
        created_at=page.get("createdAt") or page.get("created_at") or datetime.now(timezone.utc),
        updated_at=page.get("updatedAt") or page.get("updated_at") or datetime.now(timezone.utc),
    )
