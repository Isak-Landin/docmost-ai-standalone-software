from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models import DeletedOut, SpaceCreateIn, SpaceOut
from app.write.docmost import create_space as docmost_create_space
from app.write.docmost import delete_space as docmost_delete_space

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
    return _map_space(data)


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
        docmost_delete_space(str(space_id))
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


def _map_space(data: dict) -> SpaceOut:
    """Map a Docmost space response dict to SpaceOut."""
    from datetime import datetime, timezone

    return SpaceOut(
        id=data["id"],
        name=data.get("name"),
        description=data.get("description"),
        slug=data["slug"],
        visibility=data.get("visibility", "private"),
        default_role=data.get("defaultRole", "writer"),
        creator_id=data.get("creatorId"),
        workspace_id=data["workspaceId"],
        created_at=data.get("createdAt") or datetime.now(timezone.utc),
        updated_at=data.get("updatedAt") or datetime.now(timezone.utc),
    )
