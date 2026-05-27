from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.bridge.errors import BridgeConflictError, BridgeStateError
from app.bridge.services.write_pipeline import create_page_via_bridge, delete_page_via_bridge, update_page_via_bridge
from app.models import DeletedOut, PageMetaOut
from app.schemas.docmost_write import PageCreateIn, PageUpdateIn
from app.write.mappers import map_page_meta

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
        result = create_page_via_bridge(
            space_id=space_id,
            title=body.title,
            content=body.content,
            parent_page_id=body.parent_page_id,
            caller_mode="crud",
        )
        return map_page_meta(result.remote_page)
    except BridgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BridgeStateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        _raise_for_docmost_error(exc)


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
        result = update_page_via_bridge(
            page_id=page_id,
            title=body.title,
            content=body.content,
            operation=body.operation,
            caller_mode="crud",
            expected_space_id=space_id,
        )
        return map_page_meta(result.remote_page)
    except BridgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BridgeStateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        _raise_for_docmost_error(exc)


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
        delete_page_via_bridge(page_id=page_id, caller_mode="crud", expected_space_id=space_id)
    except BridgeConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except BridgeStateError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
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
