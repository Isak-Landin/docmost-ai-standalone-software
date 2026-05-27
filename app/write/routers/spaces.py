from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.bridge.services.write_pipeline import delete_space_via_bridge
from app.models import DeletedOut, SpaceOut
from app.schemas.docmost_write import SpaceCreateIn
from app.write.docmost import create_space as docmost_create_space
from app.write.mappers import map_space

router = APIRouter(prefix="/spaces", tags=["spaces"])


@router.post(
    "",
    response_model=SpaceOut,
    status_code=201,
    summary="Create a space",
    description=(
        "Creates a new Docmost space. "
        "`slug` must be alphanumeric (no spaces or dashes), 2–100 characters. "
        "Authentication is handled transparently — no auth call is needed before this."
    ),
    responses={
        400: {"description": "Validation error or slug/name already taken."},
        401: {"description": "Docmost credentials invalid or DOCMOST_USER_* env vars missing."},
    },
)
def create_space(body: SpaceCreateIn):
    try:
        data = docmost_create_space(
            name=body.name,
            slug=body.slug,
            description=body.description,
        )
    except Exception as exc:
        _raise_for_docmost_error(exc)
    return map_space(data)


@router.delete(
    "/{space_id}",
    response_model=DeletedOut,
    summary="Delete a space",
    description=(
        "Permanently deletes a space and all its pages. This is irreversible. "
        "Authentication is handled transparently."
    ),
    responses={
        404: {"description": "Space not found."},
        401: {"description": "Docmost credentials invalid."},
    },
)
def delete_space(space_id: UUID):
    try:
        delete_space_via_bridge(space_id=space_id, caller_mode="crud")
    except Exception as exc:
        _raise_for_docmost_error(exc)
    return DeletedOut(deleted=True, id=str(space_id))


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
